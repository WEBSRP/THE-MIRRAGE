"""Frozen schema addition for 20261120_0006. No message contents or recipients."""
import sqlalchemy as sa
from backend.migrations.schema_otp_abuse import schema as prior_schema

REVISION = "20261120_0006"


def schema():
    metadata = prior_schema()
    table = sa.Table("email_delivery_attempts", metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(40)),
        sa.Column("http_status", sa.Integer()))
    sa.Index("ix_email_delivery_attempts_started_at", table.c.started_at)
    return metadata
