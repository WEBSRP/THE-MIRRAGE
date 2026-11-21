"""Frozen schema addition for 20261120_0005; never import live models here."""
import sqlalchemy as sa
from backend.migrations.schema_20261120 import schema_at

REVISION = "20261120_0005"


def schema():
    metadata = schema_at("20261120_0004")
    table = sa.Table("otp_abuse_buckets", metadata,
                     sa.Column("key", sa.String(96), primary_key=True),
                     sa.Column("window", sa.BigInteger(), nullable=False),
                     sa.Column("attempts", sa.Integer(), nullable=False),
                     sa.Column("expires_at", sa.BigInteger(), nullable=False))
    sa.Index("ix_otp_abuse_buckets_expires_at", table.c.expires_at)
    return metadata
