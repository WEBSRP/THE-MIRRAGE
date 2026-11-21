"""Persist VPN download counts on each game session."""
from alembic import op
import sqlalchemy as sa

from backend.migrations.schema_vpn_download_limit import download_count_column, schema

revision = "20261121_0007"
down_revision = "20261120_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("game_sessions", download_count_column())


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("Offline downgrade is disabled")
    bind = op.get_bind()
    table = schema().tables["game_sessions"]
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("LOCK TABLE game_sessions IN ACCESS EXCLUSIVE MODE"))
    else:
        bind.execute(table.update().where(sa.false()).values(vpn_download_count=0))
    used = sa.select(sa.literal(1)).where(table.c.vpn_download_count > 0).limit(1)
    if bind.execute(used).first():
        raise RuntimeError("Downgrade would discard data; retain the VPN download counts")
    op.drop_column("game_sessions", "vpn_download_count")
