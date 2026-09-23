"""Initial schema: experiments, runs, evidence, findings, audit, approvals, keys, usage.

Revision ID: 0001
Revises:
Create Date: 2026-09-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from research_factory.persistence.schema import APPEND_ONLY_TABLES, BigIntPK, UTCDateTime

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("experiment_id", sa.String(64), nullable=False),
        sa.Column("research_family", sa.String(120), nullable=False),
        sa.Column("trial_number", sa.Integer, nullable=False),
        sa.Column("document", sa.JSON, nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", UTCDateTime, nullable=False),
        sa.PrimaryKeyConstraint("experiment_id", name="pk_experiments"),
        sa.UniqueConstraint("research_family", "trial_number", name="uq_experiments_family_trial"),
    )
    op.create_table(
        "trial_results",
        sa.Column("experiment_id", sa.String(64), nullable=False),
        sa.Column("sharpe_per_period", sa.Float, nullable=False),
        sa.Column("n_obs", sa.Integer, nullable=False),
        sa.Column("recorded_at", UTCDateTime, nullable=False),
        sa.PrimaryKeyConstraint("experiment_id", name="pk_trial_results"),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiments.experiment_id"],
            name="fk_trial_results_experiment_id_experiments",
        ),
    )
    op.create_table(
        "workflow_runs",
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("experiment_id", sa.String(64), nullable=False),
        sa.Column("project_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_step", sa.String(64)),
        sa.Column("requested_by", sa.String(120), nullable=False),
        sa.Column("decision", sa.String(32)),
        sa.Column("status_reason", sa.Text),
        sa.Column("created_at", UTCDateTime, nullable=False),
        sa.Column("updated_at", UTCDateTime, nullable=False),
        sa.PrimaryKeyConstraint("run_id", name="pk_workflow_runs"),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiments.experiment_id"],
            name="fk_workflow_runs_experiment_id_experiments",
        ),
    )
    op.create_index("ix_workflow_runs_requested_by_created", "workflow_runs", ["requested_by", "created_at"])
    op.create_table(
        "evidence",
        sa.Column("evidence_id", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_uri", sa.Text, nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("as_of", UTCDateTime),
        sa.Column("retrieved_at", UTCDateTime, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False),
        sa.PrimaryKeyConstraint("evidence_id", name="pk_evidence"),
    )
    op.create_table(
        "run_evidence",
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("evidence_id", sa.String(64), nullable=False),
        sa.Column("step", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "evidence_id", "step", name="pk_run_evidence"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["workflow_runs.run_id"], name="fk_run_evidence_run_id_workflow_runs"
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["evidence.evidence_id"], name="fk_run_evidence_evidence_id_evidence"
        ),
    )
    op.create_table(
        "step_results",
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("step", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("artifact_evidence_id", sa.String(64)),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", UTCDateTime, nullable=False),
        sa.PrimaryKeyConstraint("run_id", "step", name="pk_step_results"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["workflow_runs.run_id"], name="fk_step_results_run_id_workflow_runs"
        ),
        sa.ForeignKeyConstraint(
            ["artifact_evidence_id"],
            ["evidence.evidence_id"],
            name="fk_step_results_artifact_evidence_id_evidence",
        ),
    )
    op.create_table(
        "findings",
        sa.Column("finding_id", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("step", sa.String(64), nullable=False),
        sa.Column("finding_type", sa.String(64), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("assumptions", sa.JSON, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False),
        sa.Column("created_at", UTCDateTime, nullable=False),
        sa.PrimaryKeyConstraint("finding_id", name="pk_findings"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["workflow_runs.run_id"], name="fk_findings_run_id_workflow_runs"
        ),
    )
    op.create_index("ix_findings_run", "findings", ["run_id"])
    op.create_table(
        "finding_evidence",
        sa.Column("finding_id", sa.String(64), nullable=False),
        sa.Column("evidence_id", sa.String(64), nullable=False),
        sa.Column("relation", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("finding_id", "evidence_id", "relation", name="pk_finding_evidence"),
        sa.ForeignKeyConstraint(
            ["finding_id"], ["findings.finding_id"], name="fk_finding_evidence_finding_id_findings"
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["evidence.evidence_id"], name="fk_finding_evidence_evidence_id_evidence"
        ),
    )
    op.create_table(
        "audit_events",
        sa.Column("event_id", BigIntPK, nullable=False, autoincrement=True),
        sa.Column("run_id", sa.String(64)),
        sa.Column("step", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("created_at", UTCDateTime, nullable=False),
        sa.PrimaryKeyConstraint("event_id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_run", "audit_events", ["run_id"])
    op.create_table(
        "approvals",
        sa.Column("approval_id", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("step", sa.String(64), nullable=False),
        sa.Column("approver", sa.String(120), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_at", UTCDateTime, nullable=False),
        sa.PrimaryKeyConstraint("approval_id", name="pk_approvals"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["workflow_runs.run_id"], name="fk_approvals_run_id_workflow_runs"
        ),
    )
    op.create_table(
        "api_keys",
        sa.Column("key_id", sa.String(32), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("owner", sa.String(120), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("created_at", UTCDateTime, nullable=False),
        sa.Column("revoked_at", UTCDateTime),
        sa.PrimaryKeyConstraint("key_id", name="pk_api_keys"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_table(
        "model_usage",
        sa.Column("usage_id", BigIntPK, nullable=False, autoincrement=True),
        sa.Column("run_id", sa.String(64)),
        sa.Column("step", sa.String(64), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Float, nullable=False),
        sa.Column("created_at", UTCDateTime, nullable=False),
        sa.PrimaryKeyConstraint("usage_id", name="pk_model_usage"),
    )
    op.create_index("ix_model_usage_created", "model_usage", ["created_at"])
    _create_append_only_triggers()


def _create_append_only_triggers() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in APPEND_ONLY_TABLES:
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} "
                    f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;"
                )
    elif dialect == "postgresql":
        op.execute(
            "CREATE OR REPLACE FUNCTION rsf_forbid_mutation() RETURNS trigger AS $$ "
            "BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql;"
        )
        for table in APPEND_ONLY_TABLES:
            op.execute(
                f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION rsf_forbid_mutation();"
            )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table in APPEND_ONLY_TABLES:
            op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table};")
        op.execute("DROP FUNCTION IF EXISTS rsf_forbid_mutation();")
    for table in (
        "model_usage",
        "api_keys",
        "approvals",
        "audit_events",
        "finding_evidence",
        "findings",
        "step_results",
        "run_evidence",
        "evidence",
        "workflow_runs",
        "trial_results",
        "experiments",
    ):
        op.drop_table(table)
