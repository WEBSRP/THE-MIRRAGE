"""Persist the session waiting list and expiring slot reservations."""
from alembic import op
import sqlalchemy as sa

from backend.migrations.schema_session_queue import schema, slot_release_column

revision = "20261122_0008"
down_revision = "20261121_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("game_sessions", slot_release_column())
    schema().tables["session_queue_entries"].create(op.get_bind(), checkfirst=False)


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("Offline downgrade is disabled")
    table = schema().tables["session_queue_entries"]
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("LOCK TABLE session_queue_entries, game_sessions IN ACCESS EXCLUSIVE MODE"))
    else:
        bind.execute(table.update().where(sa.false()).values(hold_until=None))
    if bind.execute(sa.select(table.c.id).limit(1)).first():
        raise RuntimeError("Downgrade would discard session queue entries")
    if bind.execute(sa.text("SELECT 1 FROM game_sessions WHERE slot_release_not_before > CURRENT_TIMESTAMP LIMIT 1")).first():
        raise RuntimeError("Downgrade would discard active slot cooldowns")
    table.drop(bind, checkfirst=False)
    op.drop_column("game_sessions", "slot_release_not_before")
