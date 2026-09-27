"""Repository interfaces (Protocols) and their SQL implementation.

The same SQL implementation serves SQLite (development, tests, in-memory) and PostgreSQL
(deployed). Services depend only on the Protocols.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Protocol, cast

from sqlalchemy import Connection, Engine, Table, and_, func, insert, literal, or_, select, update
from sqlalchemy.exc import IntegrityError

from ..domain.errors import ConflictError, NotFoundError
from ..domain.models import AuditEvent, Confidence, EvidenceRef, Finding, Severity
from ..domain.project_models import (
    ApprovalDecision,
    ApprovalRecord,
    Experiment,
    ExperimentRecord,
    RunStatus,
    StepResult,
    StepStatus,
    WorkflowRun,
)
from . import schema as s

# --------------------------------------------------------------------------- protocols


class ExperimentRepository(Protocol):
    def add(self, record: ExperimentRecord) -> None: ...
    def get(self, experiment_id: str) -> ExperimentRecord | None: ...
    def count_in_family(self, research_family: str) -> int: ...
    def list_family(self, research_family: str) -> list[ExperimentRecord]: ...
    def list_all(self) -> list[ExperimentRecord]: ...
    def record_result(
        self, experiment_id: str, sharpe_per_period: float, n_obs: int, at: datetime
    ) -> None: ...
    def family_sharpes(
        self, research_family: str, *, max_trial: int | None = None, recorded_before: datetime | None = None
    ) -> list[float]: ...


class RunRepository(Protocol):
    def add(self, run: WorkflowRun) -> None: ...
    def get(self, run_id: str) -> WorkflowRun | None: ...
    def update(self, run: WorkflowRun, *, expected_status: RunStatus) -> None: ...
    def list(
        self, limit: int = 50, requested_by: str | None = None, requested_by_in: Sequence[str] | None = None
    ) -> list[WorkflowRun]: ...
    def count_created_since(self, requested_by: str, since: datetime) -> int: ...
    def claim(self, run_id: str, owner: str, now: datetime, expires_at: datetime) -> bool: ...
    def release(self, run_id: str, owner: str) -> None: ...
    def renew(self, run_id: str, owner: str, expires_at: datetime) -> bool: ...


class StepResultRepository(Protocol):
    def save(self, result: StepResult) -> None: ...
    def get(self, run_id: str, step: str) -> StepResult | None: ...
    def list(self, run_id: str) -> list[StepResult]: ...


class EvidenceRepository(Protocol):
    def add(self, ref: EvidenceRef) -> None: ...
    def get(self, evidence_id: str) -> EvidenceRef | None: ...
    def link(self, run_id: str, evidence_id: str, step: str) -> None: ...
    def list_for_run(self, run_id: str) -> list[tuple[str, EvidenceRef]]: ...


class FindingRepository(Protocol):
    def add(self, run_id: str, finding: Finding, created_at: datetime) -> None: ...
    def list_for_run(self, run_id: str, include_superseded: bool = False) -> list[Finding]: ...
    def supersede_step(self, run_id: str, step: str, at: datetime) -> int: ...


class AuditRepository(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent: ...
    def list(
        self, run_id: str | None = None, limit: int = 10_000, after_event_id: int = 0
    ) -> list[AuditEvent]: ...


class ApprovalRepository(Protocol):
    def add(self, record: ApprovalRecord) -> None: ...
    def list_for_run(self, run_id: str) -> list[ApprovalRecord]: ...


class ApiKeyRepository(Protocol):
    def add(self, key_id: str, key_hash: str, owner: str, role: str, created_at: datetime) -> None: ...
    def find_by_hash(self, key_hash: str) -> dict[str, Any] | None: ...
    def revoke(self, key_id: str, at: datetime) -> None: ...
    def list(self) -> list[dict[str, Any]]: ...


class UsageRepository(Protocol):
    def add(
        self,
        *,
        run_id: str | None,
        step: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        created_at: datetime,
    ) -> None: ...
    def cost_since(self, since: datetime) -> float: ...
    def totals_for_run(self, run_id: str) -> tuple[int, float]: ...


# --------------------------------------------------------------------------- SQL impl


def insert_ignore(conn: Connection, table: Table, values: dict[str, Any], keys: Sequence[str]) -> bool:
    """Insert a row unless one with the same key exists. Returns True if a row was inserted.

    Uses ON CONFLICT DO NOTHING, so concurrent writers never raise IntegrityError.
    """
    if conn.dialect.name == "postgresql":
        from sqlalchemy.dialects import postgresql

        stmt: Any = (
            postgresql.insert(table)
            .values(**values)
            .on_conflict_do_nothing(index_elements=list(keys) or None)
        )
    else:
        from sqlalchemy.dialects import sqlite

        stmt = sqlite.insert(table).values(**values).on_conflict_do_nothing(index_elements=list(keys) or None)
    # psycopg may report -1 for INSERT rowcount; RETURNING distinguishes an
    # inserted row from ON CONFLICT DO NOTHING on both supported databases.
    return conn.execute(stmt.returning(literal(1))).scalar_one_or_none() is not None


class SqlExperimentRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def add(self, record: ExperimentRecord) -> None:
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    update(s.research_guard)
                    .where(s.research_guard.c.guard_id == 1)
                    .values(revision=s.research_guard.c.revision + 1)
                )
                inserted = insert_ignore(
                    conn,
                    s.experiments,
                    dict(
                        experiment_id=record.experiment_id,
                        research_family=record.research_family,
                        trial_number=record.trial_number,
                        document=record.experiment.model_dump(mode="json", exclude={"experiment_id"}),
                        created_by=record.created_by,
                        created_at=record.created_at,
                    ),
                    (),
                )
                if not inserted:
                    raise ConflictError("experiment or trial number already exists")
        except IntegrityError as exc:
            raise ConflictError("experiment or trial number already exists") from exc

    def _row(self, row: Any, sharpe: float | None) -> ExperimentRecord:
        return ExperimentRecord(
            experiment_id=row.experiment_id,
            research_family=row.research_family,
            trial_number=row.trial_number,
            experiment=Experiment.model_validate(row.document),
            created_by=row.created_by,
            created_at=row.created_at,
            sharpe_per_period=sharpe,
        )

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        q = (
            select(s.experiments, s.trial_results.c.sharpe_per_period)
            .select_from(s.experiments.outerjoin(s.trial_results))
            .where(s.experiments.c.experiment_id == experiment_id)
        )
        with self.engine.connect() as conn:
            row = conn.execute(q).first()
        return self._row(row, row.sharpe_per_period) if row else None

    def count_in_family(self, research_family: str) -> int:
        q = (
            select(func.count())
            .select_from(s.experiments)
            .where(s.experiments.c.research_family == research_family)
        )
        with self.engine.connect() as conn:
            return int(conn.execute(q).scalar_one())

    def list_family(self, research_family: str) -> list[ExperimentRecord]:
        q = (
            select(s.experiments, s.trial_results.c.sharpe_per_period)
            .select_from(s.experiments.outerjoin(s.trial_results))
            .where(s.experiments.c.research_family == research_family)
            .order_by(s.experiments.c.trial_number)
        )
        with self.engine.connect() as conn:
            return [self._row(r, r.sharpe_per_period) for r in conn.execute(q)]

    def list_all(self) -> list[ExperimentRecord]:
        q = (
            select(s.experiments, s.trial_results.c.sharpe_per_period)
            .select_from(s.experiments.outerjoin(s.trial_results))
            .order_by(s.experiments.c.created_at, s.experiments.c.experiment_id)
        )
        with self.engine.connect() as conn:
            return [self._row(r, r.sharpe_per_period) for r in conn.execute(q)]

    def record_result(self, experiment_id: str, sharpe_per_period: float, n_obs: int, at: datetime) -> None:
        with self.engine.begin() as conn:
            if insert_ignore(
                conn,
                s.trial_results,
                {
                    "experiment_id": experiment_id,
                    "sharpe_per_period": sharpe_per_period,
                    "n_obs": n_obs,
                    "recorded_at": at,
                },
                ("experiment_id",),
            ):
                return
            existing = conn.execute(
                select(s.trial_results).where(s.trial_results.c.experiment_id == experiment_id)
            ).first()
            if existing is not None:
                if abs(existing.sharpe_per_period - sharpe_per_period) > 1e-12 or existing.n_obs != n_obs:
                    raise ConflictError("a different result is already recorded for this experiment")
                return

    def family_sharpes(
        self, research_family: str, *, max_trial: int | None = None, recorded_before: datetime | None = None
    ) -> list[float]:
        q = (
            select(s.trial_results.c.sharpe_per_period)
            .select_from(s.trial_results.join(s.experiments))
            .where(s.experiments.c.research_family == research_family)
            .order_by(s.experiments.c.trial_number)
        )
        if max_trial is not None:
            q = q.where(s.experiments.c.trial_number <= max_trial)
        if recorded_before is not None:
            q = q.where(s.trial_results.c.recorded_at <= recorded_before)
        with self.engine.connect() as conn:
            return [float(v) for v in conn.execute(q).scalars()]


def _run_from_row(row: Any) -> WorkflowRun:
    return WorkflowRun(
        run_id=row.run_id,
        experiment_id=row.experiment_id,
        project_type=row.project_type,
        status=RunStatus(row.status),
        current_step=row.current_step,
        requested_by=row.requested_by,
        decision=ApprovalDecision(row.decision) if row.decision else None,
        status_reason=row.status_reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
        execution_manifest=row.execution_manifest,
    )


class SqlRunRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def add(self, run: WorkflowRun) -> None:
        with self.engine.begin() as conn:
            conn.execute(insert(s.workflow_runs).values(**run.model_dump(mode="python")))

    def get(self, run_id: str) -> WorkflowRun | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(s.workflow_runs).where(s.workflow_runs.c.run_id == run_id)).first()
        return _run_from_row(row) if row else None

    def update(self, run: WorkflowRun, *, expected_status: RunStatus) -> None:
        """Compare-and-set on status so concurrent writers cannot silently clobber each other."""
        values = run.model_dump(
            mode="python", exclude={"run_id", "experiment_id", "created_at", "requested_by"}
        )
        with self.engine.begin() as conn:
            result = conn.execute(
                update(s.workflow_runs)
                .where(
                    and_(
                        s.workflow_runs.c.run_id == run.run_id,
                        s.workflow_runs.c.status == str(expected_status),
                    )
                )
                .values(**values)
            )
        if result.rowcount != 1:
            raise ConflictError(f"run {run.run_id} is no longer in status {expected_status}")

    def list(
        self, limit: int = 50, requested_by: str | None = None, requested_by_in: Sequence[str] | None = None
    ) -> list[WorkflowRun]:
        q = select(s.workflow_runs).order_by(s.workflow_runs.c.created_at.desc()).limit(limit)
        if requested_by is not None:
            q = q.where(s.workflow_runs.c.requested_by == requested_by)
        if requested_by_in is not None:
            q = q.where(s.workflow_runs.c.requested_by.in_(list(requested_by_in)))
        with self.engine.connect() as conn:
            return [_run_from_row(r) for r in conn.execute(q)]

    def claim(self, run_id: str, owner: str, now: datetime, expires_at: datetime) -> bool:
        return _claim(self.engine, run_id, owner, now, expires_at)

    def renew(self, run_id: str, owner: str, expires_at: datetime) -> bool:
        with self.engine.begin() as conn:
            result = conn.execute(
                update(s.workflow_runs)
                .where(and_(s.workflow_runs.c.run_id == run_id, s.workflow_runs.c.lease_owner == owner))
                .values(lease_expires_at=expires_at)
            )
        return result.rowcount == 1

    def release(self, run_id: str, owner: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(s.workflow_runs)
                .where(and_(s.workflow_runs.c.run_id == run_id, s.workflow_runs.c.lease_owner == owner))
                .values(lease_owner=None, lease_expires_at=None)
            )

    def count_created_since(self, requested_by: str, since: datetime) -> int:
        q = (
            select(func.count())
            .select_from(s.workflow_runs)
            .where(
                and_(s.workflow_runs.c.requested_by == requested_by, s.workflow_runs.c.created_at >= since)
            )
        )
        with self.engine.connect() as conn:
            return int(conn.execute(q).scalar_one())


def _claimable(now: datetime) -> Any:
    """Not terminal, and no live lease held by another worker (an expired lease can be taken over)."""
    runs = s.workflow_runs.c
    return and_(
        runs.status.in_([str(RunStatus.PENDING), str(RunStatus.NEEDS_REVIEW), str(RunStatus.RUNNING)]),
        or_(runs.lease_owner.is_(None), runs.lease_expires_at.is_(None), runs.lease_expires_at < now),
    )


def _claim(engine: Engine, run_id: str, owner: str, now: datetime, expires_at: datetime) -> bool:
    """Atomically take the run's lease. Fails if another worker holds a live lease."""
    with engine.begin() as conn:
        result = conn.execute(
            update(s.workflow_runs)
            .where(and_(s.workflow_runs.c.run_id == run_id, _claimable(now)))
            .values(lease_owner=owner, lease_expires_at=expires_at)
        )
    return result.rowcount == 1


class SqlStepResultRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def save(self, result: StepResult) -> None:
        """Insert, or replace a non-completed result. Completed results are immutable."""
        values = result.model_dump(mode="python")
        values["status"] = str(result.status)
        with self.engine.begin() as conn:
            if insert_ignore(conn, s.step_results, values, ("run_id", "step")):
                return
            existing = conn.execute(
                select(s.step_results).where(
                    and_(s.step_results.c.run_id == result.run_id, s.step_results.c.step == result.step)
                )
            ).first()
            assert existing is not None
            if existing.status == StepStatus.COMPLETED:
                raise ConflictError(f"step {result.step} of run {result.run_id} is already completed")
            changed = conn.execute(
                update(s.step_results)
                .where(
                    and_(
                        s.step_results.c.run_id == result.run_id,
                        s.step_results.c.step == result.step,
                        s.step_results.c.status != str(StepStatus.COMPLETED),
                    )
                )
                .values(**values)
            )
            if changed.rowcount != 1:
                raise ConflictError(f"step {result.step} was concurrently completed")

    @staticmethod
    def _row(row: Any) -> StepResult:
        return StepResult(
            run_id=row.run_id,
            step=row.step,
            status=StepStatus(row.status),
            idempotency_key=row.idempotency_key,
            artifact_evidence_id=row.artifact_evidence_id,
            attempts=row.attempts,
            error_code=row.error_code,
            error_message=row.error_message,
            created_at=row.created_at,
            fail_run=row.fail_run,
            run_decision=ApprovalDecision(row.run_decision) if row.run_decision else None,
            gate_context=row.gate_context,
        )

    def get(self, run_id: str, step: str) -> StepResult | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(s.step_results).where(
                    and_(s.step_results.c.run_id == run_id, s.step_results.c.step == step)
                )
            ).first()
        return self._row(row) if row else None

    def list(self, run_id: str) -> list[StepResult]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(s.step_results)
                .where(s.step_results.c.run_id == run_id)
                .order_by(s.step_results.c.created_at)
            )
            return [self._row(r) for r in rows]


def _evidence_from_row(row: Any) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=row.evidence_id,
        source_uri=row.source_uri,
        source_type=row.source_type,
        content_hash=row.content_hash,
        retrieved_at=row.retrieved_at,
        as_of=row.as_of,
        metadata=row.metadata,
    )


class SqlEvidenceRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def add(self, ref: EvidenceRef) -> None:
        """Idempotent: re-adding the same evidence ID is a no-op."""
        with self.engine.begin() as conn:
            if insert_ignore(
                conn,
                s.evidence,
                {
                    "evidence_id": ref.evidence_id,
                    "content_hash": ref.content_hash,
                    "source_uri": ref.source_uri,
                    "source_type": ref.source_type,
                    "as_of": ref.as_of,
                    "retrieved_at": ref.retrieved_at,
                    "metadata": ref.metadata,
                },
                ("evidence_id",),
            ):
                return
            exists = conn.execute(
                select(s.evidence.c.content_hash).where(s.evidence.c.evidence_id == ref.evidence_id)
            ).first()
            if exists is not None:
                if exists.content_hash != ref.content_hash:
                    raise ConflictError("evidence ID collision with different content")
                return

    def get(self, evidence_id: str) -> EvidenceRef | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(s.evidence).where(s.evidence.c.evidence_id == evidence_id)).first()
        return _evidence_from_row(row) if row else None

    def link(self, run_id: str, evidence_id: str, step: str) -> None:
        with self.engine.begin() as conn:
            insert_ignore(
                conn,
                s.run_evidence,
                {"run_id": run_id, "evidence_id": evidence_id, "step": step},
                ("run_id", "evidence_id", "step"),
            )

    def list_for_run(self, run_id: str) -> list[tuple[str, EvidenceRef]]:
        q = (
            select(s.run_evidence.c.step, s.evidence)
            .select_from(s.run_evidence.join(s.evidence))
            .where(s.run_evidence.c.run_id == run_id)
            .order_by(s.evidence.c.retrieved_at, s.evidence.c.evidence_id)
        )
        with self.engine.connect() as conn:
            return [(r.step, _evidence_from_row(r)) for r in conn.execute(q)]


class SqlFindingRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def add(self, run_id: str, finding: Finding, created_at: datetime) -> None:
        with self.engine.begin() as conn:
            inserted = insert_ignore(
                conn,
                s.findings,
                dict(
                    finding_id=finding.finding_id,
                    run_id=run_id,
                    step=finding.step,
                    finding_type=finding.finding_type,
                    title=finding.title,
                    statement=finding.statement,
                    severity=str(finding.severity),
                    confidence=str(finding.confidence),
                    assumptions=list(finding.assumptions),
                    metadata=finding.metadata,
                    created_at=created_at,
                ),
                ("finding_id",),
            )
            if not inserted:
                # Content-addressed: the same finding again. Re-activate it if a retry had superseded it.
                conn.execute(
                    update(s.findings)
                    .where(s.findings.c.finding_id == finding.finding_id)
                    .values(superseded_at=None)
                )
                return
            for evidence_id in dict.fromkeys(finding.evidence_ids):
                insert_ignore(
                    conn,
                    s.finding_evidence,
                    {"finding_id": finding.finding_id, "evidence_id": evidence_id, "relation": "supports"},
                    ("finding_id", "evidence_id", "relation"),
                )

    def supersede_step(self, run_id: str, step: str, at: datetime) -> int:
        """Mark a step's active findings as superseded (the step is being executed again)."""
        with self.engine.begin() as conn:
            result = conn.execute(
                update(s.findings)
                .where(
                    and_(
                        s.findings.c.run_id == run_id,
                        s.findings.c.step == step,
                        s.findings.c.superseded_at.is_(None),
                    )
                )
                .values(superseded_at=at)
            )
        return int(result.rowcount)

    def list_for_run(self, run_id: str, include_superseded: bool = False) -> list[Finding]:
        q = select(s.findings).where(s.findings.c.run_id == run_id)
        if not include_superseded:
            q = q.where(s.findings.c.superseded_at.is_(None))
        with self.engine.connect() as conn:
            rows = conn.execute(q.order_by(s.findings.c.created_at, s.findings.c.finding_id)).all()
            links = conn.execute(
                select(s.finding_evidence.c.finding_id, s.finding_evidence.c.evidence_id)
                .select_from(s.finding_evidence.join(s.findings))
                .where(s.findings.c.run_id == run_id)
                .order_by(s.finding_evidence.c.evidence_id)
            ).all()
        by_finding: dict[str, list[str]] = {}
        for link in links:
            by_finding.setdefault(link.finding_id, []).append(link.evidence_id)
        return [
            Finding(
                finding_id=r.finding_id,
                step=r.step,
                finding_type=r.finding_type,
                title=r.title,
                statement=r.statement,
                severity=Severity(r.severity),
                confidence=Confidence(r.confidence),
                evidence_ids=tuple(by_finding.get(r.finding_id, [])),
                assumptions=tuple(r.assumptions),
                metadata={
                    **r.metadata,
                    **({"superseded_at": r.superseded_at.isoformat()} if r.superseded_at else {}),
                },
            )
            for r in rows
        ]


class SqlAuditRepository:
    """Append-only. There is deliberately no update or delete method."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def append(self, event: AuditEvent) -> AuditEvent:
        with self.engine.begin() as conn:
            result = conn.execute(
                insert(s.audit_events).values(
                    run_id=event.run_id,
                    step=event.step,
                    actor=event.actor,
                    event_type=event.event_type,
                    payload=event.payload,
                    payload_hash=event.payload_hash,
                    created_at=event.created_at,
                )
            )
            key = result.inserted_primary_key
            assert key is not None
            event_id = int(key[0])
        return event.model_copy(update={"event_id": event_id})

    def list(
        self, run_id: str | None = None, limit: int = 10_000, after_event_id: int = 0
    ) -> list[AuditEvent]:
        q = (
            select(s.audit_events)
            .where(s.audit_events.c.event_id > after_event_id)
            .order_by(s.audit_events.c.event_id)
            .limit(limit)
        )
        if run_id is not None:
            q = q.where(s.audit_events.c.run_id == run_id)
        with self.engine.connect() as conn:
            return [
                AuditEvent(
                    event_id=r.event_id,
                    run_id=r.run_id,
                    step=r.step,
                    actor=r.actor,
                    event_type=r.event_type,
                    payload=r.payload,
                    payload_hash=r.payload_hash,
                    created_at=r.created_at,
                )
                for r in conn.execute(q)
            ]


class SqlApprovalRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def add(self, record: ApprovalRecord) -> None:
        values = record.model_dump(mode="python")
        values["decision"] = str(record.decision)
        try:
            with self.engine.begin() as conn:
                conn.execute(insert(s.approvals).values(**values))
        except IntegrityError as exc:
            raise ConflictError("a decision has already been recorded for this committee pause") from exc

    def list_for_run(self, run_id: str) -> list[ApprovalRecord]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(s.approvals).where(s.approvals.c.run_id == run_id).order_by(s.approvals.c.created_at)
            )
            return [
                ApprovalRecord(
                    approval_id=r.approval_id,
                    run_id=r.run_id,
                    step=r.step,
                    approver=r.approver,
                    decision=ApprovalDecision(r.decision),
                    reason=r.reason,
                    created_at=r.created_at,
                    gate_context=r.gate_context,
                )
                for r in rows
            ]


class SqlApiKeyRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def add(self, key_id: str, key_hash: str, owner: str, role: str, created_at: datetime) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(s.api_keys).values(
                    key_id=key_id, key_hash=key_hash, owner=owner, role=role, created_at=created_at
                )
            )

    def find_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(s.api_keys).where(s.api_keys.c.key_hash == key_hash)).first()
        return dict(row._mapping) if row else None

    def revoke(self, key_id: str, at: datetime) -> None:
        with self.engine.begin() as conn:
            result = conn.execute(
                update(s.api_keys)
                .where(and_(s.api_keys.c.key_id == key_id, s.api_keys.c.revoked_at.is_(None)))
                .values(revoked_at=at)
            )
        if result.rowcount != 1:
            raise NotFoundError(f"no active key {key_id}")

    def list(self) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(
                    s.api_keys.c.key_id,
                    s.api_keys.c.owner,
                    s.api_keys.c.role,
                    s.api_keys.c.created_at,
                    s.api_keys.c.revoked_at,
                ).order_by(s.api_keys.c.created_at)
            )
            return [dict(r._mapping) for r in rows]


class SqlUsageRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def add(
        self,
        *,
        run_id: str | None,
        step: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        created_at: datetime,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(s.model_usage).values(
                    run_id=run_id,
                    step=step,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                    created_at=created_at,
                )
            )

    def cost_since(self, since: datetime) -> float:
        q = select(func.coalesce(func.sum(s.model_usage.c.cost_usd), 0.0)).where(
            s.model_usage.c.created_at >= since
        )
        with self.engine.connect() as conn:
            return float(conn.execute(q).scalar_one())

    def totals_for_run(self, run_id: str) -> tuple[int, float]:
        q = select(
            func.coalesce(func.sum(s.model_usage.c.input_tokens + s.model_usage.c.output_tokens), 0),
            func.coalesce(func.sum(s.model_usage.c.cost_usd), 0.0),
        ).where(s.model_usage.c.run_id == run_id)
        with self.engine.connect() as conn:
            tokens, cost = conn.execute(q).one()
        return int(tokens), float(cost)


WriteFence = tuple[str, str, Callable[[], datetime]]


def _check_fence(conn: Connection, fence: WriteFence) -> None:
    run_id, owner, now = fence
    changed = conn.execute(
        update(s.workflow_runs)
        .where(
            and_(
                s.workflow_runs.c.run_id == run_id,
                s.workflow_runs.c.lease_owner == owner,
                s.workflow_runs.c.lease_expires_at >= now(),
            )
        )
        .values(updated_at=s.workflow_runs.c.updated_at)
    )
    if changed.rowcount != 1:
        raise ConflictError("the run lease is no longer owned by this worker")


class _TransactionalEngine:
    """Route repository operations into a short, synchronous unit of work.

    Context-local routing keeps independent requests on independent connections. Never
    hold a unit of work over an await or dispatch work from inside one.
    """

    def __init__(
        self, engine: Engine, current: ContextVar[Connection | None], fence: ContextVar[WriteFence | None]
    ):
        self.engine = engine
        self.current = current
        self.fence = fence

    @contextmanager
    def begin(self) -> Iterator[Connection]:
        conn = self.current.get()
        if conn is not None:
            yield conn
        else:
            with self.engine.begin() as opened:
                fence = self.fence.get()
                if fence is not None:
                    _check_fence(opened, fence)
                yield opened

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        conn = self.current.get()
        if conn is not None:
            yield conn
        else:
            with self.engine.connect() as opened:
                yield opened


class Repositories:
    """All repositories over one engine."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self._current: ContextVar[Connection | None] = ContextVar("repository_transaction", default=None)
        self._fence: ContextVar[WriteFence | None] = ContextVar("repository_write_fence", default=None)
        engine = cast(Engine, _TransactionalEngine(engine, self._current, self._fence))
        self.experiments: ExperimentRepository = SqlExperimentRepository(engine)
        self.runs: RunRepository = SqlRunRepository(engine)
        self.steps: StepResultRepository = SqlStepResultRepository(engine)
        self.evidence: EvidenceRepository = SqlEvidenceRepository(engine)
        self.findings: FindingRepository = SqlFindingRepository(engine)
        self.audit: AuditRepository = SqlAuditRepository(engine)
        self.approvals: ApprovalRepository = SqlApprovalRepository(engine)
        self.api_keys: ApiKeyRepository = SqlApiKeyRepository(engine)
        self.usage: UsageRepository = SqlUsageRepository(engine)

    @contextmanager
    def fenced(self, run_id: str, owner: str, now: Callable[[], datetime]) -> Iterator[None]:
        """Fence *all* step writes, including evidence emitted before the checkpoint."""
        token = self._fence.set((run_id, owner, now))
        try:
            yield
        finally:
            self._fence.reset(token)

    @contextmanager
    def transaction(
        self,
        *,
        run_id: str | None = None,
        owner: str | None = None,
        now: datetime | None = None,
        guard_ledger: bool = False,
    ) -> Iterator[None]:
        """Atomically publish related records, optionally fencing a workflow owner.

        The no-op UPDATE takes the same database row lock used by claim/takeover.
        A unique owner token cannot commit after another owner claims the run, even
        when its coroutine resumes after a long suspension.
        """
        if self._current.get() is not None:
            raise RuntimeError("nested repository transactions are not supported")
        with self.engine.begin() as conn:
            if guard_ledger:
                conn.execute(
                    update(s.research_guard)
                    .where(s.research_guard.c.guard_id == 1)
                    .values(revision=s.research_guard.c.revision)
                )
            if run_id is not None:
                predicate = s.workflow_runs.c.run_id == run_id
                if owner is not None:
                    if now is None:
                        raise ValueError("a fenced transaction requires the current time")
                    predicate = and_(
                        predicate,
                        s.workflow_runs.c.lease_owner == owner,
                        s.workflow_runs.c.lease_expires_at >= now,
                    )
                result = conn.execute(
                    update(s.workflow_runs).where(predicate).values(updated_at=s.workflow_runs.c.updated_at)
                )
                if result.rowcount != 1:
                    raise ConflictError("the run lease is no longer owned by this worker")
            token = self._current.set(conn)
            try:
                yield
            finally:
                self._current.reset(token)


__all__: Sequence[str] = [
    "ApiKeyRepository",
    "ApprovalRepository",
    "AuditRepository",
    "EvidenceRepository",
    "ExperimentRepository",
    "FindingRepository",
    "Repositories",
    "RunRepository",
    "StepResultRepository",
    "UsageRepository",
]
