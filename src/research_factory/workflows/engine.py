"""The workflow state machine (RSF-022, RSF-042 to RSF-045; ADR-0005).

* Status transitions are validated against ``RUN_TRANSITIONS``.
* One worker at a time: ``advance`` takes a lease on the run (compare-and-set) and renews it
  before each step. A crashed worker's lease expires and another worker can resume.
* Each step's result is persisted before the next step starts.
* A completed step is never executed again for the same run: resuming reuses its stored
  artifact (idempotency key = experiment + step + prior artifacts).
* Re-executing a step that previously paused or failed supersedes that attempt's findings,
  so the committee gate only sees findings from each step's current result.
* Transient failures (including database and storage outages) are retried with backoff
  inside a timeout; validation and policy errors are not retried. Anything unexpected
  pauses the run for review instead of leaving it stuck. Everything is audited.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from contextlib import suppress
from contextvars import ContextVar
from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import anyio
from sqlalchemy.exc import DBAPIError, OperationalError

from ..config import StatisticalThresholds
from ..domain.errors import (
    BudgetExceededError,
    ConflictError,
    DomainError,
    ErrorCode,
    NotFoundError,
    StepTimeoutError,
    UpstreamUnavailableError,
)
from ..domain.identity import content_id
from ..domain.project_models import (
    RUN_TRANSITIONS,
    ApprovalDecision,
    RunStatus,
    StepResult,
    StepStatus,
    WorkflowRun,
)
from ..observability import bind, get_logger, unbind
from .base import Step, StepContext, StepOutcome
from .execution import execution_manifest, runtime_identity

if TYPE_CHECKING:
    from ..services.container import Services

log = get_logger(__name__)

# Errors that pause the run for a human (resumable) rather than failing it.
PAUSE_CODES = {
    ErrorCode.NEEDS_EVIDENCE,
    ErrorCode.UPSTREAM_UNAVAILABLE,
    ErrorCode.TIMEOUT,
    ErrorCode.BUDGET_EXCEEDED,
}


def _infrastructure_errors() -> tuple[type[BaseException], ...]:
    """Exceptions that mean a dependency (database, storage, network) is unavailable."""
    errors: list[type[BaseException]] = [OperationalError, DBAPIError, ConnectionError, TimeoutError, OSError]
    try:
        from botocore.exceptions import BotoCoreError, ClientError

        errors += [BotoCoreError, ClientError]
    except ImportError:  # the s3 extra is optional
        pass
    return tuple(errors)


INFRASTRUCTURE_ERRORS = _infrastructure_errors()


def idempotency_key(experiment_id: str, step: str, prior: Sequence[str]) -> str:
    return content_id("idem", {"experiment_id": experiment_id, "step": step, "prior": list(prior)}, length=32)


class WorkflowEngine:
    def __init__(self, services: Services, steps: Sequence[Step], *, manifest: dict[str, Any] | None = None):
        self.services = services
        self.steps = list(steps)
        self.manifest = manifest
        self._owner: ContextVar[str | None] = ContextVar("workflow_owner", default=None)

    # ----------------------------------------------------------------- lifecycle

    def create_run(
        self, experiment_id: str, requested_by: str, project_type: str = "systematic_research"
    ) -> WorkflowRun:
        with self.services.repos.transaction():
            return self._create_run(experiment_id, requested_by, project_type)

    def _create_run(self, experiment_id: str, requested_by: str, project_type: str) -> WorkflowRun:
        record = self.services.ledger.get(experiment_id)
        now = self.services.clock.now()
        run = WorkflowRun(
            run_id=f"run_{uuid.uuid4().hex[:20]}",
            experiment_id=record.experiment_id,
            project_type=project_type,
            status=RunStatus.PENDING,
            requested_by=requested_by,
            created_at=now,
            updated_at=now,
            execution_manifest=self.manifest or execution_manifest(self.services.settings),
        )
        self.services.repos.runs.add(run)
        self.services.audit.append(
            run_id=run.run_id,
            step="run",
            event_type="run_created",
            actor=requested_by,
            payload={
                "experiment_id": experiment_id,
                "trial_number": record.trial_number,
                "project_type": project_type,
            },
        )
        return run

    async def start(
        self, experiment_id: str, requested_by: str, project_type: str = "systematic_research"
    ) -> WorkflowRun:
        run = self.create_run(experiment_id, requested_by, project_type)
        return await self.advance(run.run_id, actor=requested_by)

    def _transition(
        self,
        run: WorkflowRun,
        status: RunStatus,
        actor: str,
        *,
        reason: str | None = None,
        current_step: str | None = None,
        decision: ApprovalDecision | None = None,
    ) -> WorkflowRun:
        with self.services.repos.transaction(
            run_id=run.run_id, owner=self._owner.get(), now=self.services.clock.now()
        ):
            return self._transition_locked(
                run, status, actor, reason=reason, current_step=current_step, decision=decision
            )

    def _transition_locked(
        self,
        run: WorkflowRun,
        status: RunStatus,
        actor: str,
        *,
        reason: str | None = None,
        current_step: str | None = None,
        decision: ApprovalDecision | None = None,
    ) -> WorkflowRun:
        if status != run.status and status not in RUN_TRANSITIONS[run.status]:
            raise ConflictError(f"invalid transition {run.status} -> {status}")
        updated = run.model_copy(
            update={
                "status": status,
                "status_reason": reason,
                "current_step": current_step if current_step is not None else run.current_step,
                "decision": decision if decision is not None else run.decision,
                "updated_at": self.services.clock.now(),
            }
        )
        self.services.repos.runs.update(updated, expected_status=run.status)
        if status != run.status:
            self.services.audit.append(
                run_id=run.run_id,
                step=updated.current_step or "run",
                event_type="run_status_changed",
                actor=actor,
                payload={"from": str(run.status), "to": str(status), "reason": reason},
            )
        return updated

    def get_run(self, run_id: str) -> WorkflowRun:
        run = self.services.repos.runs.get(run_id)
        if run is None:
            raise NotFoundError(f"run {run_id} not found")
        return run

    def cancel(self, run_id: str, actor: str, reason: str) -> WorkflowRun:
        """End a paused run for good (e.g. a run paused on its budget that should not continue)."""
        run = self.get_run(run_id)
        if run.status is not RunStatus.NEEDS_REVIEW:
            raise ConflictError(f"only a paused run can be cancelled; this one is {run.status}")
        owner = f"worker_{uuid.uuid4().hex}"
        if not self.services.repos.runs.claim(run_id, owner, self.services.clock.now(), self._lease_until()):
            raise ConflictError("this run is being advanced by another worker")
        token = self._owner.set(owner)
        try:
            return self._transition(run, RunStatus.FAILED, actor, reason=f"CANCELLED by {actor}: {reason}")
        finally:
            self._owner.reset(token)
            self.services.repos.runs.release(run_id, owner)

    # ----------------------------------------------------------------- execution

    def _lease_until(self) -> Any:
        return self.services.clock.now() + timedelta(seconds=self.services.settings.lease_seconds)

    async def advance(self, run_id: str, actor: str) -> WorkflowRun:
        """Run (or resume) a workflow until it completes, fails, or needs a human."""
        run = self.get_run(run_id)
        if run.status.terminal:
            return run
        recorded_runtime = run.execution_manifest.get("runtime")
        if recorded_runtime and recorded_runtime != runtime_identity():
            raise ConflictError("resume requires the run's recorded code/dependency/platform runtime")
        owner = f"worker_{uuid.uuid4().hex}"
        if not self.services.repos.runs.claim(run_id, owner, self.services.clock.now(), self._lease_until()):
            raise ConflictError("this run is being advanced by another worker; try again when it pauses")
        token = self._owner.set(owner)
        bind(run_id=run_id, experiment_id=run.experiment_id)
        try:
            record = self.services.ledger.get(run.experiment_id)
            run = self._transition(self.get_run(run_id), RunStatus.RUNNING, actor)
            with self.services.repos.fenced(run_id, owner, self.services.clock.now):
                return await self._advance_with_heartbeat(run, record, actor, owner)
        except anyio.get_cancelled_exc_class() as exc:
            with suppress(ConflictError):
                self._pause_after_error(run_id, actor, exc)
            raise
        except DomainError as exc:
            # A validation/context conflict while we still own the run must be
            # resumable; a fenced-out worker must not write even a pause event.
            with suppress(ConflictError):
                self._pause_after_error(run_id, actor, exc)
            raise
        except Exception as exc:  # anything unexpected outside a step: pause, never leave it "running"
            log.exception("engine_error", error_type=type(exc).__name__)
            return self._pause_after_error(run_id, actor, exc)
        finally:
            self._owner.reset(token)
            try:
                self.services.repos.runs.release(run_id, owner)
            finally:
                unbind("run_id", "experiment_id", "step")

    async def _advance_with_heartbeat(
        self, run: WorkflowRun, record: Any, actor: str, owner: str
    ) -> WorkflowRun:
        result: WorkflowRun | None = None
        failure: BaseException | None = None
        lost = False
        async with anyio.create_task_group() as group:

            async def heartbeat() -> None:
                nonlocal lost
                while True:
                    await anyio.sleep(max(0.001, self.services.settings.lease_seconds / 3))
                    try:
                        renewed = self.services.repos.runs.renew(run.run_id, owner, self._lease_until())
                    except Exception:
                        renewed = False
                    if not renewed:
                        lost = True
                        group.cancel_scope.cancel()
                        return

            group.start_soon(heartbeat)
            try:
                result = await self._advance(run, record, actor, owner)
            except BaseException as exc:
                failure = exc
            finally:
                group.cancel_scope.cancel()
        if lost:
            raise ConflictError("the run's lease was lost; this worker stopped without committing")
        if failure is not None:
            raise failure
        assert result is not None
        return result

    def _pause_after_error(self, run_id: str, actor: str, exc: BaseException) -> WorkflowRun:
        with self.services.repos.transaction(
            run_id=run_id, owner=self._owner.get(), now=self.services.clock.now()
        ):
            return self._pause_error_locked(run_id, actor, exc)

    def _pause_error_locked(self, run_id: str, actor: str, exc: BaseException) -> WorkflowRun:
        infra = isinstance(exc, INFRASTRUCTURE_ERRORS)
        code = (
            "CANCELLED"
            if not isinstance(exc, Exception)
            else ("UPSTREAM_UNAVAILABLE" if infra else "INTERNAL")
        )
        self.services.audit.append(
            run_id=run_id,
            step="run",
            event_type="engine_error",
            actor=actor,
            payload={"error_type": type(exc).__name__},
        )
        current = self.get_run(run_id)
        if current.status is RunStatus.RUNNING:
            return self._transition_locked(
                current,
                RunStatus.NEEDS_REVIEW,
                actor,
                reason=f"{code}: the run stopped unexpectedly ({type(exc).__name__}); resume to retry",
            )
        return current

    async def _advance(self, run: WorkflowRun, record: Any, actor: str, owner: str) -> WorkflowRun:
        run_id = run.run_id
        artifacts: dict[str, str] = {}
        prior: list[str] = []
        manifest = run.execution_manifest
        settings = self.services.settings
        if manifest.get("thresholds"):
            settings = settings.model_copy(
                update={"thresholds": StatisticalThresholds.model_validate(manifest["thresholds"])}
            )
        execution_services = replace(
            self.services, settings=settings, pinned_snapshots=dict(manifest.get("snapshots", {}))
        )

        for step in self.steps:
            key = idempotency_key(run.experiment_id, step.name, prior)
            existing = self.services.repos.steps.get(run_id, step.name)
            if existing is not None and existing.status is StepStatus.COMPLETED:
                if existing.idempotency_key != key:
                    raise ConflictError(f"stored result for {step.name} does not match its inputs")
                if existing.artifact_evidence_id:
                    artifacts[step.name] = existing.artifact_evidence_id
                    prior.append(existing.artifact_evidence_id)
                self.services.audit.append(
                    run_id=run_id,
                    step=step.name,
                    event_type="step_reused",
                    actor=actor,
                    payload={"idempotency_key": key},
                )
                fail_run = existing.fail_run
                decision = existing.run_decision
                if not run.execution_manifest and existing.artifact_evidence_id:
                    # Migration cannot inspect the external blob store. Recover known
                    # legacy terminal effects from the durable artifact at resume time.
                    document = self.services.evidence.load_json(existing.artifact_evidence_id)
                    if step.name == "Leakage audit":
                        fail_run = fail_run or bool(document.get("blocking"))
                    if document.get("format") == "rsf-committee-decision/1" and document.get("decision"):
                        decision = ApprovalDecision(document["decision"])
                if fail_run:
                    return self._transition(
                        run,
                        RunStatus.FAILED,
                        actor,
                        reason=existing.error_message or f"{step.name} failed",
                        current_step=step.name,
                    )
                if decision is not None:
                    run = run.model_copy(update={"decision": decision})
                continue

            if not self.services.repos.runs.renew(run_id, owner, self._lease_until()):
                raise ConflictError("the run's lease was taken over by another worker")
            run = self._transition(run, RunStatus.RUNNING, actor, current_step=step.name)
            bind(step=step.name)
            ctx = StepContext(run=run, record=record, services=execution_services, artifacts=dict(artifacts))
            outcome, attempts = await self._execute(step, ctx, actor)
            artifact_id = self._persist(run, step, key, outcome, attempts, actor)

            if outcome.status is StepStatus.FAILED or outcome.fail_run:
                return self._transition(
                    run,
                    RunStatus.FAILED,
                    actor,
                    reason=outcome.reason or f"{step.name} failed",
                    current_step=step.name,
                )
            if outcome.status is StepStatus.NEEDS_REVIEW:
                return self._transition(
                    run,
                    RunStatus.NEEDS_REVIEW,
                    actor,
                    reason=f"{outcome.reason_code or 'REVIEW'}: {outcome.reason or 'human review required'}",
                    current_step=step.name,
                )
            if artifact_id:
                artifacts[step.name] = artifact_id
                prior.append(artifact_id)
            if outcome.run_decision is not None:
                run = run.model_copy(update={"decision": ApprovalDecision(outcome.run_decision)})

        return self._transition(
            run, RunStatus.COMPLETE, actor, reason="workflow complete", decision=run.decision
        )

    async def _execute(self, step: Step, ctx: StepContext, actor: str) -> tuple[StepOutcome, int]:
        policy = self.services.settings.retry
        attempt = 0
        while True:
            attempt += 1
            ctx.attempt = attempt
            self.services.audit.append(
                run_id=ctx.run.run_id,
                step=step.name,
                event_type="step_started",
                actor=actor,
                payload={"attempt": attempt},
            )
            try:
                with anyio.fail_after(policy.timeout_seconds):
                    return await step.execute(ctx), attempt
            except TimeoutError:
                error: DomainError = StepTimeoutError(f"{step.name} exceeded {policy.timeout_seconds}s")
            except BudgetExceededError as exc:
                return (
                    StepOutcome(StepStatus.NEEDS_REVIEW, reason=exc.message, reason_code=str(exc.code)),
                    attempt,
                )
            except DomainError as exc:
                error = exc
            except INFRASTRUCTURE_ERRORS as exc:  # database, storage or network trouble: retryable
                error = UpstreamUnavailableError(f"a dependency was unavailable ({type(exc).__name__})")
            except Exception as exc:  # unexpected: fail closed without leaking internals
                log.exception("step_crashed", run_id=ctx.run.run_id, step=step.name)
                self.services.audit.append(
                    run_id=ctx.run.run_id,
                    step=step.name,
                    event_type="step_crashed",
                    actor=actor,
                    payload={"error_type": type(exc).__name__},
                )
                return StepOutcome(
                    StepStatus.FAILED, reason="internal error", reason_code="INTERNAL"
                ), attempt

            if error.retryable and attempt < policy.max_attempts:
                delay = min(policy.base_delay_seconds * 2 ** (attempt - 1), policy.max_delay_seconds)
                self.services.audit.append(
                    run_id=ctx.run.run_id,
                    step=step.name,
                    event_type="step_retry",
                    actor=actor,
                    payload={
                        "attempt": attempt,
                        "code": str(error.code),
                        "message": error.message,
                        "delay_s": delay,
                    },
                )
                await anyio.sleep(delay)
                continue
            if error.code in PAUSE_CODES:
                return StepOutcome(
                    StepStatus.NEEDS_REVIEW, reason=error.message, reason_code=str(error.code)
                ), attempt
            return StepOutcome(StepStatus.FAILED, reason=error.message, reason_code=str(error.code)), attempt

    def _persist(
        self, run: WorkflowRun, step: Step, key: str, outcome: StepOutcome, attempts: int, actor: str
    ) -> str | None:
        with self.services.repos.transaction(
            run_id=run.run_id,
            owner=self._owner.get(),
            now=self.services.clock.now(),
            guard_ledger=outcome.gate_context is not None,
        ):
            return self._persist_locked(run, step, key, outcome, attempts, actor)

    def _persist_locked(
        self, run: WorkflowRun, step: Step, key: str, outcome: StepOutcome, attempts: int, actor: str
    ) -> str | None:
        services = self.services
        if outcome.gate_context is not None and outcome.gate_context != services.approvals.context(
            run.run_id
        ):
            raise ConflictError(
                "the committee review inputs changed before the checkpoint; resume to review again"
            )
        superseded = services.repos.findings.supersede_step(run.run_id, step.name, services.clock.now())
        if superseded:
            services.audit.append(
                run_id=run.run_id,
                step=step.name,
                event_type="findings_superseded",
                actor=actor,
                payload={"count": superseded},
            )
        artifact_id: str | None = None
        if outcome.artifact is not None:
            ref = services.evidence.record_json(
                outcome.artifact,
                source_uri=f"rsf://experiments/{run.experiment_id}/steps/{step.slug}",
                source_type=f"artifact:{step.slug}",
                run_id=run.run_id,
                step=step.name,
            )
            artifact_id = ref.evidence_id
        for evidence_id in outcome.evidence_ids:
            services.repos.evidence.link(run.run_id, evidence_id, step.name)
        now = services.clock.now()
        for finding in outcome.findings:
            services.repos.findings.add(run.run_id, finding, now)
        services.repos.steps.save(
            StepResult(
                run_id=run.run_id,
                step=step.name,
                status=outcome.status,
                idempotency_key=key,
                artifact_evidence_id=artifact_id,
                attempts=attempts,
                error_code=outcome.reason_code
                if outcome.status is not StepStatus.COMPLETED or outcome.fail_run
                else None,
                error_message=outcome.reason
                if outcome.status is not StepStatus.COMPLETED or outcome.fail_run
                else None,
                created_at=now,
                fail_run=outcome.fail_run,
                run_decision=ApprovalDecision(outcome.run_decision) if outcome.run_decision else None,
                gate_context=outcome.gate_context,
            )
        )
        log.info(
            "step_finished",
            status=str(outcome.status),
            attempts=attempts,
            reason_code=outcome.reason_code,
            artifact_evidence_id=artifact_id,
            findings=len(outcome.findings),
            **{
                k: v
                for k, v in outcome.audit.items()
                if k in ("model", "input_tokens", "output_tokens", "cost_usd")
            },
        )
        services.audit.append(
            run_id=run.run_id,
            step=step.name,
            event_type=f"step_{outcome.status}",
            actor=actor,
            payload={
                "attempts": attempts,
                "idempotency_key": key,
                "artifact_evidence_id": artifact_id,
                "findings": [f.finding_id for f in outcome.findings],
                "reason_code": outcome.reason_code,
                **outcome.audit,
            },
        )
        return artifact_id
