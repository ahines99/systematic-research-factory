"""Superseded findings, run leases, one approval per pause, TRUNCATE protection.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from research_factory.persistence.schema import APPEND_ONLY_TABLES, UTCDateTime

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("superseded_at", UTCDateTime))
    op.add_column("workflow_runs", sa.Column("lease_owner", sa.String(64)))
    op.add_column("workflow_runs", sa.Column("lease_expires_at", UTCDateTime))
    op.create_index("uq_approvals_run_step", "approvals", ["run_id", "step"], unique=True)
    if op.get_bind().dialect.name == "postgresql":
        # Row triggers do not fire on TRUNCATE; a statement trigger closes that gap.
        for table in APPEND_ONLY_TABLES:
            op.execute(
                f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
                "FOR EACH STATEMENT EXECUTE FUNCTION rsf_forbid_mutation();"
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in APPEND_ONLY_TABLES:
            op.execute(f"DROP TRIGGER IF EXISTS {table}_no_truncate ON {table};")
    op.drop_index("uq_approvals_run_step", table_name="approvals")
    with op.batch_alter_table("workflow_runs") as batch:
        batch.drop_column("lease_expires_at")
        batch.drop_column("lease_owner")
    with op.batch_alter_table("findings") as batch:
        batch.drop_column("superseded_at")
