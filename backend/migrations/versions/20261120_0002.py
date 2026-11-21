"""shared flag solves and submission quotas. Frozen schema; do not import live ORM models."""
from backend.migrations.operations import create_revision, drop_empty_revision

revision = '20261120_0002'
down_revision = '20261120_0001'
branch_labels = None
depends_on = None


def upgrade():
    create_revision(revision)


def downgrade():
    drop_empty_revision(revision)
