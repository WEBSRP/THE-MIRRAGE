"""Durable operational email provider health without message/recipient data."""
from alembic import op
import sqlalchemy as sa
from backend.migrations.schema_email_health import schema

revision = "20261120_0006"
down_revision = "20261120_0005"
branch_labels = None
depends_on = None


def upgrade():
    schema().tables["email_delivery_attempts"].create(op.get_bind(), checkfirst=False)


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("Offline downgrade is disabled")
    table = schema().tables["email_delivery_attempts"]
    if op.get_bind().dialect.name == "postgresql":
        op.get_bind().execute(sa.text("LOCK TABLE email_delivery_attempts IN ACCESS EXCLUSIVE MODE"))
    else:
        op.get_bind().execute(table.update().where(sa.false()).values(provider=table.c.provider))
    if op.get_bind().execute(sa.select(sa.literal(1)).select_from(table).limit(1)).first():
        raise RuntimeError("Downgrade would discard data; retain the schema or restore a verified backup")
    table.drop(op.get_bind(), checkfirst=False)
