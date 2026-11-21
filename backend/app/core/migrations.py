"""Revision checks and strictly verified adoption of legacy create_all databases."""
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
import sqlalchemy as sa

from backend.app.core.config import settings
from backend.migrations.schema_20261120 import REVISIONS, schema_at
from backend.migrations.schema_otp_abuse import REVISION as OTP_ABUSE_REVISION, schema as otp_abuse_schema
from backend.migrations.schema_email_health import REVISION as EMAIL_HEALTH_REVISION, schema as email_health_schema


from backend.migrations.schema_vpn_download_limit import REVISION as VPN_DOWNLOAD_REVISION, schema as vpn_download_schema


def migration_config():
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["database_url"] = settings.DATABASE_URL
    return config


def expected_heads():
    return set(ScriptDirectory.from_config(migration_config()).get_heads())


def require_current_schema(connection):
    if set(MigrationContext.configure(connection).get_current_heads()) != expected_heads():
        raise RuntimeError("Database migrations are required; use the migration status/adopt/upgrade commands before startup")


def matches_schema(connection, metadata):
    inspector = sa.inspect(connection)
    # Alembic autogenerate does not reliably compare primary-key changes.
    for table in metadata.tables.values():
        actual = inspector.get_pk_constraint(table.name).get("constrained_columns") or []
        if actual != [column.name for column in table.primary_key.columns]:
            return False
    context = MigrationContext.configure(connection, opts={"compare_type": True, "compare_server_default": True})
    if compare_metadata(context, metadata):
        return False
    # Alembic's normal type comparison does not detect native enum label drift.
    if connection.dialect.name == "postgresql":
        enums = {item["name"]: item["labels"] for item in inspector.get_enums()}
        for table in metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, sa.Enum) and enums.get(column.type.name) != column.type.enums:
                    return False
    return True


def adopt_schema(connection):
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("SELECT pg_advisory_xact_lock(74291826)"))
    if MigrationContext.configure(connection).get_current_heads():
        raise RuntimeError("Database is already versioned; use status and upgrade")
    tables = set(sa.inspect(connection).get_table_names()) - {"alembic_version"}
    snapshots = [(revision, schema_at(revision)) for revision in REVISIONS]
    snapshots.append((OTP_ABUSE_REVISION, otp_abuse_schema()))
    snapshots.append((EMAIL_HEALTH_REVISION, email_health_schema()))
    snapshots.append((VPN_DOWNLOAD_REVISION, vpn_download_schema()))
    for revision, metadata in reversed(snapshots):
        if tables == set(metadata.tables) and matches_schema(connection, metadata):
            config = migration_config()
            config.attributes.update(connection=connection, verified_adoption=True)
            command.stamp(config, revision)
            return revision
    raise RuntimeError("Legacy schema does not exactly match a supported revision; review a restored copy before adoption")
