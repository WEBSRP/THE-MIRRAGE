"""Async Alembic environment shared by CLI and checked schema adoption."""
import asyncio

from alembic import context
from alembic.migration import MigrationContext
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

import backend.app.models  # Register all models without importing the application.
from backend.app.core.config import settings
from backend.app.core.database import Base

config = context.config


def migrate(connection):
    def execute():
        if connection.dialect.name == "postgresql":
            connection.execute(sa.text("SELECT pg_advisory_xact_lock(74291826)"))
        tables = set(sa.inspect(connection).get_table_names()) - {"alembic_version"}
        current = MigrationContext.configure(connection).get_current_heads()
        if tables and not current and not config.attributes.get("verified_adoption"):
            raise RuntimeError("Unversioned database: use the checked migration adopt command before upgrade")
        context.configure(connection=connection, target_metadata=Base.metadata,
                          compare_type=True, compare_server_default=True)
        with context.begin_transaction():
            context.run_migrations()
    if connection.in_transaction():
        execute()
    else:
        with connection.begin():
            execute()


async def online():
    engine = create_async_engine(config.attributes.get("database_url", settings.DATABASE_URL),
                                 poolclass=sa.pool.NullPool, echo=False, hide_parameters=True)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(url=config.attributes.get("database_url", settings.DATABASE_URL),
                      target_metadata=Base.metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    migrate(config.attributes["connection"])
else:
    asyncio.run(online())
