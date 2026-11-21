"""Exercise real versioned DDL and legacy adoption on disposable databases."""
from datetime import datetime, timezone
import asyncio
import io
import os
from pathlib import Path
import shutil
import uuid

from alembic import command
from alembic.migration import MigrationContext
import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.app.core.database import Base
from backend.app.core.migrations import (
    adopt_schema, matches_schema, migration_config, require_current_schema,
)
from backend.app.models.challenge import Challenge, ChallengeSolve
from backend.app.models.user import User
from backend.app.models.vpn import VpnAddressReservation, VpnRevocation
from backend.migrations.schema_20261120 import REVISIONS, schema_at
from backend.migrations.schema_email_health import REVISION as EMAIL_REVISION, schema as email_schema
from backend.migrations.schema_vpn_download_limit import REVISION as HEAD_REVISION
from backend.migrations.schema_otp_abuse import REVISION as ABUSE_REVISION, schema as abuse_schema


@pytest_asyncio.fixture(params=["sqlite", "postgresql"])
async def migration_db(request, tmp_path):
    admin = None
    if request.param == "postgresql":
        url = os.environ.get("MIRRAGE_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("Requires disposable PostgreSQL")
        schema = "migration_" + uuid.uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'migrate.db'}")
    try:
        yield engine
    finally:
        await engine.dispose()
        if admin:
            async with admin.begin() as connection:
                await connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()


async def migrate(engine, target="head", *, downgrade=False):
    async with engine.begin() as connection:
        def run(sync):
            config = migration_config()
            config.attributes["connection"] = sync
            (command.downgrade if downgrade else command.upgrade)(config, target)
        await connection.run_sync(run)


async def heads(engine):
    async with engine.connect() as connection:
        return await connection.run_sync(lambda sync: MigrationContext.configure(sync).get_current_heads())


@pytest.mark.asyncio
async def test_empty_upgrade_matches_current_models_and_roundtrips_all_revisions(migration_db):
    engine = migration_db
    await migrate(engine)
    assert await heads(engine) == (HEAD_REVISION,)
    async with engine.connect() as connection:
        assert await connection.run_sync(lambda sync: matches_schema(sync, Base.metadata))
        await connection.run_sync(require_current_schema)
        config = migration_config()
        config.attributes["connection"] = connection.sync_connection
        await connection.run_sync(lambda sync: command.check(config))
    await migrate(engine, "base", downgrade=True)
    assert await heads(engine) == ()
    async with engine.connect() as connection:
        assert await connection.run_sync(lambda sync: set(sa.inspect(sync).get_table_names())) <= {"alembic_version"}
    await migrate(engine)
    assert await heads(engine) == (HEAD_REVISION,)


@pytest.mark.asyncio
@pytest.mark.parametrize("revision", REVISIONS)
async def test_checked_adoption_recognizes_each_supported_legacy_schema_without_data_loss(migration_db, revision):
    engine = migration_db
    async with engine.begin() as connection:
        await connection.run_sync(schema_at(revision).create_all)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        user = User(email="legacy@example.com", username="legacy", is_active=True, email_verified=True)
        db.add(user)
        await db.commit()
        user_id = user.id
    async with engine.begin() as connection:
        assert await connection.run_sync(adopt_schema) == revision
    await migrate(engine)
    async with AsyncSession(engine) as db:
        assert (await db.get(User, user_id)).email == "legacy@example.com"
    async with engine.connect() as connection:
        assert await connection.run_sync(lambda sync: matches_schema(sync, Base.metadata))


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["index", "column", "extra-table"])
async def test_adoption_rejects_schema_drift_without_stamping_or_repairing(migration_db, damage):
    engine = migration_db
    async with engine.begin() as connection:
        await connection.run_sync(schema_at(REVISIONS[0]).create_all)
        if damage == "index":
            await connection.execute(sa.text("DROP INDEX ix_users_email"))
        elif damage == "column":
            await connection.execute(sa.text("ALTER TABLE users DROP COLUMN email_verified"))
        else:
            await connection.execute(sa.text("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="does not exactly match"):
        async with engine.begin() as connection:
            await connection.run_sync(adopt_schema)
    assert await heads(engine) == ()
    async with engine.connect() as connection:
        assert "users" in await connection.run_sync(lambda sync: sa.inspect(sync).get_table_names())


@pytest.mark.asyncio
async def test_unversioned_existing_database_rejects_blind_upgrade_and_stamp(migration_db):
    engine = migration_db
    async with engine.begin() as connection:
        await connection.run_sync(schema_at(REVISIONS[0]).create_all)
    with pytest.raises(RuntimeError, match="checked migration adopt"):
        await migrate(engine)
    with pytest.raises(RuntimeError, match="checked migration adopt"):
        async with engine.begin() as connection:
            def stamp(sync):
                config = migration_config()
                config.attributes["connection"] = sync
                command.stamp(config, "head")
            await connection.run_sync(stamp)
    assert await heads(engine) == ()


@pytest.mark.asyncio
async def test_startup_checks_version_without_creating_tables(migration_db, monkeypatch):
    from backend.app.core import database
    engine = migration_db
    monkeypatch.setattr(database, "engine", engine)
    with pytest.raises(RuntimeError, match="migrations are required"):
        await database.init_db()
    async with engine.connect() as connection:
        assert await connection.run_sync(lambda sync: sa.inspect(sync).get_table_names()) == []
    await migrate(engine, REVISIONS[0])
    with pytest.raises(RuntimeError, match="migrations are required"):
        await database.init_db()
    await migrate(engine)
    await database.init_db()


@pytest.mark.asyncio
@pytest.mark.parametrize("revision", REVISIONS)
async def test_populated_downgrade_preserves_data_and_revision(migration_db, revision):
    engine = migration_db
    await migrate(engine, revision)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        user = User(email="keep@example.com", username="keep")
        db.add(user)
        await db.flush()
        if revision == REVISIONS[1]:
            challenge = Challenge(slug="keep", title="Keep", description="Keep", flag="dummy")
            db.add(challenge)
            await db.flush()
            db.add(ChallengeSolve(user_id=user.id, challenge_id=challenge.id,
                                  solved_at=datetime.now(timezone.utc), points=100))
        elif revision == REVISIONS[2]:
            db.add(VpnAddressReservation(address="10.8.0.10", user_id=user.id, client_name="keep"))
        elif revision == REVISIONS[3]:
            db.add(VpnRevocation(client_name="keep", user_id=user.id, requested_by=user.id,
                requested_at=datetime.now(timezone.utc), next_attempt_at=datetime.now(timezone.utc), attempts=1))
        await db.commit()
        user_id = user.id
    parent = REVISIONS[REVISIONS.index(revision) - 1] if revision != REVISIONS[0] else "base"
    with pytest.raises(RuntimeError, match="would discard data"):
        await migrate(engine, parent, downgrade=True)
    assert await heads(engine) == (revision,)
    async with AsyncSession(engine) as db:
        assert await db.get(User, user_id) is not None
    await migrate(engine)  # Failed rollback does not strand future forward upgrades.


@pytest.mark.asyncio
async def test_postgres_enum_drift_rejects_adoption(migration_db):
    engine = migration_db
    if engine.dialect.name != "postgresql":
        pytest.skip("Native PostgreSQL enum validation")
    async with engine.begin() as connection:
        await connection.run_sync(schema_at(REVISIONS[0]).create_all)
        await connection.execute(sa.text("ALTER TYPE sessionstatus ADD VALUE 'UNEXPECTED'"))
    with pytest.raises(RuntimeError, match="does not exactly match"):
        async with engine.begin() as connection:
            await connection.run_sync(adopt_schema)


@pytest.mark.asyncio
async def test_security_table_primary_key_drift_rejects_adoption(migration_db):
    engine = migration_db
    metadata = schema_at(REVISIONS[1])
    # Reproduce a table with the correct columns but no authoritative unique solve key.
    solves = metadata.tables["challenge_solves"]
    solves.constraints.remove(solves.primary_key)
    for column in solves.columns:
        column.primary_key = False
    solves.primary_key = sa.PrimaryKeyConstraint()
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    with pytest.raises(RuntimeError, match="does not exactly match"):
        async with engine.begin() as connection:
            await connection.run_sync(adopt_schema)


@pytest.mark.asyncio
async def test_revision_template_can_generate_a_new_revision_without_modifying_repo(migration_db, tmp_path):
    engine = migration_db
    await migrate(engine)
    scripts = tmp_path / "revision-scripts"
    shutil.copytree(Path(__file__).resolve().parents[1] / "migrations", scripts)
    async with engine.begin() as connection:
        def generate(sync):
            config = migration_config()
            config.set_main_option("script_location", str(scripts))
            config.attributes["connection"] = sync
            return command.revision(config, message="test revision template", autogenerate=True)
        result = await connection.run_sync(generate)
    source = Path(result.path).read_text()
    compile(source, str(result.path), "exec")
    assert result.down_revision == HEAD_REVISION


@pytest.mark.asyncio
async def test_postgres_downgrade_cannot_drop_a_concurrently_inserted_revocation(migration_db):
    engine = migration_db
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL DDL/writer lock ordering")
    await migrate(engine)
    now = datetime.now(timezone.utc)
    pending = None
    async with engine.begin() as writer:
        await writer.execute(sa.insert(VpnRevocation).values(client_name="concurrent-keep",
            user_id="keep", requested_by="keep", requested_at=now, next_attempt_at=now, attempts=0))
        pending = asyncio.create_task(migrate(engine, REVISIONS[2], downgrade=True))
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(pending), 0.05)
    with pytest.raises(RuntimeError, match="would discard data"):
        await asyncio.wait_for(pending, 5)
    assert await heads(engine) == (HEAD_REVISION,)
    async with engine.connect() as connection:
        assert (await connection.execute(sa.select(VpnRevocation.client_name))).scalar_one() == "concurrent-keep"


def test_offline_upgrade_generates_reviewable_postgresql_sql_without_connecting():
    config = migration_config()
    config.attributes["database_url"] = "postgresql+asyncpg://offline/unused"
    config.output_buffer = io.StringIO()
    command.upgrade(config, "head", sql=True)
    sql = config.output_buffer.getvalue()
    assert "CREATE TABLE users" in sql and "CREATE TYPE sessionstatus" in sql
    assert "CREATE TABLE vpn_revocations" in sql and "alembic_version" in sql


@pytest.mark.asyncio
async def test_adoption_of_otp_budget_schema_and_populated_downgrade_guard(migration_db):
    from backend.app.models.otp_abuse import OtpAbuseBucket
    engine = migration_db
    async with engine.begin() as connection:
        await connection.run_sync(abuse_schema().create_all)
        assert await connection.run_sync(adopt_schema) == ABUSE_REVISION
        await connection.execute(sa.insert(OtpAbuseBucket).values(
            key="global:hour", window=1, attempts=1, expires_at=7200))
    with pytest.raises(RuntimeError, match="would discard data"):
        await migrate(engine, REVISIONS[-1], downgrade=True)
    assert await heads(engine) == (ABUSE_REVISION,)
    async with engine.connect() as connection:
        assert (await connection.execute(sa.select(OtpAbuseBucket.attempts))).scalar_one() == 1


@pytest.mark.asyncio
async def test_adoption_and_retention_guard_for_email_health(migration_db):
    from backend.app.models.email_delivery import EmailDeliveryAttempt
    engine = migration_db
    async with engine.begin() as connection:
        await connection.run_sync(email_schema().create_all)
        assert await connection.run_sync(adopt_schema) == EMAIL_REVISION
        await connection.execute(sa.insert(EmailDeliveryAttempt).values(
            provider="resend", outcome="pending", started_at=datetime.now(timezone.utc)))
    with pytest.raises(RuntimeError, match="would discard data"):
        await migrate(engine, ABUSE_REVISION, downgrade=True)
    assert await heads(engine) == (EMAIL_REVISION,)
