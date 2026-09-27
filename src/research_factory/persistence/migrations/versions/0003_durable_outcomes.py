"""Durable step effects, execution manifests and context-bound approvals.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_guard",
        sa.Column("guard_id", sa.Integer, primary_key=True),
        sa.Column("revision", sa.Integer, nullable=False),
    )
    op.execute(sa.text("INSERT INTO research_guard (guard_id, revision) VALUES (1, 0)"))
    op.add_column(
        "workflow_runs", sa.Column("execution_manifest", sa.JSON, nullable=False, server_default="{}")
    )
    op.add_column("step_results", sa.Column("fail_run", sa.Boolean, nullable=False, server_default="0"))
    op.add_column("step_results", sa.Column("run_decision", sa.String(32)))
    op.add_column("step_results", sa.Column("gate_context", sa.String(64)))
    op.add_column(
        "approvals", sa.Column("gate_context", sa.String(64), nullable=False, server_default="legacy")
    )
    op.drop_index("uq_approvals_run_step", table_name="approvals")
    op.create_index(
        "uq_approvals_run_step_context", "approvals", ["run_id", "step", "gate_context"], unique=True
    )


def downgrade() -> None:
    # Multiple review contexts cannot be represented by the previous unique index.
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text("SELECT run_id FROM approvals GROUP BY run_id, step HAVING COUNT(*) > 1")
    ).first()
    if duplicates:
        raise RuntimeError("cannot downgrade context-bound approvals without losing historical decisions")
    op.drop_index("uq_approvals_run_step_context", table_name="approvals")
    op.create_index("uq_approvals_run_step", "approvals", ["run_id", "step"], unique=True)
    op.drop_column("approvals", "gate_context")
    op.drop_column("step_results", "gate_context")
    op.drop_column("step_results", "run_decision")
    op.drop_column("step_results", "fail_run")
    op.drop_column("workflow_runs", "execution_manifest")
    op.drop_table("research_guard")
