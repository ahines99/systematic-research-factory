"""Relational schema (SQLAlchemy Core). Portable across SQLite and PostgreSQL (ADR-0001).

The Alembic migrations in ``migrations/`` create exactly this schema; a test compares them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Dialect,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import TypeDecorator

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=NAMING)

# Serializes a new trial with the instant a committee decision is committed.
research_guard = Table(
    "research_guard",
    metadata,
    Column("guard_id", Integer, primary_key=True),
    Column("revision", Integer, nullable=False),
)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware datetimes on every backend (SQLite drops tzinfo; we restore UTC)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetimes are not stored")
        return value.astimezone(UTC)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        parsed: datetime = datetime.fromisoformat(value) if isinstance(value, str) else value
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


# Autoincrementing 64-bit key that SQLite also accepts as ROWID alias.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")

experiments = Table(
    "experiments",
    metadata,
    Column("experiment_id", String(64), primary_key=True),
    Column("research_family", String(120), nullable=False),
    Column("trial_number", Integer, nullable=False),
    Column("document", JSON, nullable=False),
    Column("created_by", String(120), nullable=False),
    Column("created_at", UTCDateTime, nullable=False),
    UniqueConstraint("research_family", "trial_number", name="uq_experiments_family_trial"),
)

trial_results = Table(
    "trial_results",
    metadata,
    Column("experiment_id", String(64), ForeignKey("experiments.experiment_id"), primary_key=True),
    Column("sharpe_per_period", Float, nullable=False),
    Column("n_obs", Integer, nullable=False),
    Column("recorded_at", UTCDateTime, nullable=False),
)

workflow_runs = Table(
    "workflow_runs",
    metadata,
    Column("run_id", String(64), primary_key=True),
    Column("experiment_id", String(64), ForeignKey("experiments.experiment_id"), nullable=False),
    Column("project_type", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("current_step", String(64)),
    Column("requested_by", String(120), nullable=False),
    Column("decision", String(32)),
    Column("status_reason", Text),
    Column("created_at", UTCDateTime, nullable=False),
    Column("updated_at", UTCDateTime, nullable=False),
    Column("lease_owner", String(64)),
    Column("lease_expires_at", UTCDateTime),
    Column("execution_manifest", JSON, nullable=False, server_default="{}"),
    Index("ix_workflow_runs_requested_by_created", "requested_by", "created_at"),
)

evidence = Table(
    "evidence",
    metadata,
    Column("evidence_id", String(64), primary_key=True),
    Column("content_hash", String(64), nullable=False),
    Column("source_uri", Text, nullable=False),
    Column("source_type", String(64), nullable=False),
    Column("as_of", UTCDateTime),
    Column("retrieved_at", UTCDateTime, nullable=False),
    Column("metadata", JSON, nullable=False),
)

run_evidence = Table(
    "run_evidence",
    metadata,
    Column("run_id", String(64), ForeignKey("workflow_runs.run_id"), primary_key=True),
    Column("evidence_id", String(64), ForeignKey("evidence.evidence_id"), primary_key=True),
    Column("step", String(64), primary_key=True),
)

step_results = Table(
    "step_results",
    metadata,
    Column("run_id", String(64), ForeignKey("workflow_runs.run_id"), primary_key=True),
    Column("step", String(64), primary_key=True),
    Column("status", String(32), nullable=False),
    Column("idempotency_key", String(80), nullable=False),
    Column("artifact_evidence_id", String(64), ForeignKey("evidence.evidence_id")),
    Column("attempts", Integer, nullable=False),
    Column("error_code", String(64)),
    Column("error_message", Text),
    Column("created_at", UTCDateTime, nullable=False),
    Column("fail_run", Boolean, nullable=False, server_default="0"),
    Column("run_decision", String(32)),
    Column("gate_context", String(64)),
)

findings = Table(
    "findings",
    metadata,
    Column("finding_id", String(64), primary_key=True),
    Column("run_id", String(64), ForeignKey("workflow_runs.run_id"), nullable=False),
    Column("step", String(64), nullable=False),
    Column("finding_type", String(64), nullable=False),
    Column("title", Text, nullable=False),
    Column("statement", Text, nullable=False),
    Column("severity", String(16), nullable=False),
    Column("confidence", String(16), nullable=False),
    Column("assumptions", JSON, nullable=False),
    Column("metadata", JSON, nullable=False),
    Column("created_at", UTCDateTime, nullable=False),
    Column("superseded_at", UTCDateTime),  # set when the step that produced it is re-executed
    Index("ix_findings_run", "run_id"),
)

finding_evidence = Table(
    "finding_evidence",
    metadata,
    Column("finding_id", String(64), ForeignKey("findings.finding_id"), primary_key=True),
    Column("evidence_id", String(64), ForeignKey("evidence.evidence_id"), primary_key=True),
    Column("relation", String(32), primary_key=True),
)

audit_events = Table(
    "audit_events",
    metadata,
    Column("event_id", BigIntPK, primary_key=True, autoincrement=True),
    Column("run_id", String(64)),
    Column("step", String(64), nullable=False),
    Column("actor", String(120), nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("created_at", UTCDateTime, nullable=False),
    Index("ix_audit_events_run", "run_id"),
)

approvals = Table(
    "approvals",
    metadata,
    Column("approval_id", String(64), primary_key=True),
    Column("run_id", String(64), ForeignKey("workflow_runs.run_id"), nullable=False),
    Column("step", String(64), nullable=False),
    Column("approver", String(120), nullable=False),
    Column("decision", String(32), nullable=False),
    Column("reason", Text, nullable=False),
    Column("created_at", UTCDateTime, nullable=False),
    Column("gate_context", String(64), nullable=False, server_default="legacy"),
    Index("uq_approvals_run_step_context", "run_id", "step", "gate_context", unique=True),
)

api_keys = Table(
    "api_keys",
    metadata,
    Column("key_id", String(32), primary_key=True),
    Column("key_hash", String(64), nullable=False, unique=True),
    Column("owner", String(120), nullable=False),
    Column("role", String(32), nullable=False),
    Column("created_at", UTCDateTime, nullable=False),
    Column("revoked_at", UTCDateTime),
)

model_usage = Table(
    "model_usage",
    metadata,
    Column("usage_id", BigIntPK, primary_key=True, autoincrement=True),
    Column("run_id", String(64)),
    Column("step", String(64), nullable=False),
    Column("model", String(120), nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cost_usd", Float, nullable=False),
    Column("created_at", UTCDateTime, nullable=False),
    Index("ix_model_usage_created", "created_at"),
)

# Tables whose rows may never be updated or deleted (enforced by database triggers).
APPEND_ONLY_TABLES = ("audit_events", "experiments", "trial_results", "evidence", "approvals")
