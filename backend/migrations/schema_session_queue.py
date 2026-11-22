"""Frozen schema addition for the session waiting list."""
import sqlalchemy as sa

from backend.migrations.schema_vpn_download_limit import schema as prior_schema

REVISION = "20261122_0008"


def slot_release_column():
    return sa.Column("slot_release_not_before", sa.DateTime(timezone=True), nullable=True)


def schema():
    metadata = prior_schema()
    metadata.tables["game_sessions"].append_column(slot_release_column())
    sa.Table(
        "session_queue_entries", metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  unique=True, nullable=False),
        sa.Column("hold_until", sa.DateTime(timezone=True)),
        sa.Column("email_attempted_at", sa.DateTime(timezone=True)),
    )
    return metadata
