#!/usr/bin/env python3
import asyncio
import logging
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.services.challenge_service import challenge_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mirrage.init_db")


async def main():
    logger.info("Initializing MIRRAGE database schema...")
    await init_db()
    logger.info("Database schema initialized.")

    logger.info("Seeding default challenges...")
    async with AsyncSessionLocal() as db:
        await challenge_service.seed_default_challenges(db)
    logger.info("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
