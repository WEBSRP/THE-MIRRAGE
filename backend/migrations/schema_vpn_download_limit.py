"""Frozen schema addition for the per-session VPN download limit."""
import sqlalchemy as sa

from backend.migrations.schema_email_health import schema as prior_schema

REVISION = "20261121_0007"


def download_count_column():
    return sa.Column("vpn_download_count", sa.Integer(), nullable=False, server_default=sa.text("0"))


def schema():
    metadata = prior_schema()
    metadata.tables["game_sessions"].append_column(download_count_column())
    return metadata
