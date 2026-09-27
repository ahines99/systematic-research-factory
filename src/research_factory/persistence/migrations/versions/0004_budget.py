"""Reserve model budgets before dispatch and reconcile paid responses."""

from alembic import op

from research_factory.persistence.budget import budget_lock, model_reservations

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    budget_lock.create(op.get_bind(), checkfirst=True)
    model_reservations.create(op.get_bind(), checkfirst=True)
    op.get_bind().execute(budget_lock.insert().values(lock_id=1, version=0))


def downgrade() -> None:
    model_reservations.drop(op.get_bind())
    budget_lock.drop(op.get_bind())
