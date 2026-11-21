"""baseline existing passwordless platform. Frozen schema; do not import live ORM models."""
from backend.migrations.operations import create_revision, drop_empty_revision

revision = '20261120_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    create_revision(revision)


def downgrade():
    drop_empty_revision(revision)
