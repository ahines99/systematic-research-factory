"""The workflow state machine (RSF-022, RSF-042 to RSF-045; ADR-0005).

* Status transitions are validated against ``RUN_TRANSITIONS``.
* Each step's result is persisted before the next step starts.
* A completed step is never executed again for the same run: resuming reuses its stored
  artifact (idempotency key = experiment + step + prior artifacts).
* Transient failures are retried with backoff inside a timeout; validation and policy
  errors are not retried. Every attempt, retry and transition is audited.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import anyio

from ..domain.errors import (
    BudgetExceededError,
    ConflictError,
    DomainError,
    ErrorCode,
    NotFoundError,
    StepTimeoutError,
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


def idempotency_key(experiment_id: str, step: str, prior: Sequence[str]) -> str:
    return content_id("idem", {"experiment_id": experiment_id, "step": step, "prior": list(prior)}, length=32)


class WorkflowEngine:
    def __init__(self, services: Services, steps: Sequence[Step]):
        self.services = services
        self.steps = list(steps)

    # ----------------------------------------------------------------- lifecycle

    def create_run(
        self, experiment_id: str, requested_by: str, project_type: str = "systematic_research"
    ) -> WorkflowRun:
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

    # ----------------------------------------------------------------- execution

    async def advance(self, run_id: str, actor: str) -> WorkflowRun:
        """Run (or resume) a workflow until it completes, fails, or needs a human."""
        run = self.get_run(run_id)
        if run.status.terminal:
            return run
        record = self.services.ledger.get(run.experiment_id)
        run = self._transition(run, RunStatus.RUNNING, actor)
        bind(run_id=run_id, experiment_id=run.experiment_id)
        try:
            return await self._advance(run, record, actor)
        finally:
            unbind("run_id", "experiment_id", "step")

    async def _advance(self, run: WorkflowRun, record: Any, actor: str) -> WorkflowRun:
        run_id = run.run_id
        artifacts: dict[str, str] = {}
        prior: list[str] = []

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
                continue

            run = self._transition(run, RunStatus.RUNNING, actor, current_step=step.name)
            bind(step=step.name)
            ctx = StepContext(run=run, record=record, services=self.services, artifacts=dict(artifacts))
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
        services = self.services
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
                error_code=outcome.reason_code if outcome.status is not StepStatus.COMPLETED else None,
                error_message=outcome.reason if outcome.status is not StepStatus.COMPLETED else None,
                created_at=now,
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
