#!/usr/bin/env python3
import asyncio
import backend.app.models
import logging
from alembic import command
from backend.app.core.migrations import migration_config
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.services.challenge_service import challenge_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mirrage.init_db")


async def main():
    logger.info("Applying explicit MIRRAGE database migrations...")
    await asyncio.to_thread(command.upgrade, migration_config(), "head")
    await init_db()
    logger.info("Database migration revision verified.")

    logger.info("Seeding default challenges...")
    async with AsyncSessionLocal() as db:
        await challenge_service.seed_default_challenges(db)
    logger.info("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
