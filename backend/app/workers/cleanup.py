import asyncio
import logging
from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal
from backend.app.services.session_service import session_service

logger = logging.getLogger("mirrage.worker.cleanup")


async def session_cleanup_worker():
    """Background task to periodically reap expired sessions and free K8s resources."""
    logger.info("Starting MIRRAGE session cleanup worker...")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                cleaned_count = await session_service.cleanup_expired_sessions(db)
                if cleaned_count > 0:
                    logger.info(f"Reaped and cleaned up {cleaned_count} expired session(s)")
        except Exception as e:
            logger.error(f"Error in session cleanup worker: {e}")

        await asyncio.sleep(settings.SESSION_CLEANUP_INTERVAL_SECONDS)
