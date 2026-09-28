import asyncio
import logging
from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal
from backend.app.services.session_service import session_service

logger = logging.getLogger("mirrage.worker.cleanup")


async def session_cleanup_worker():
    """Background task to periodically reap expired sessions and reconcile orphaned pods."""
    logger.info("Starting MIRRAGE session cleanup worker...")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                # 1. Clean up expired sessions (existing behavior)
                cleaned_count = await session_service.cleanup_expired_sessions(db)
                if cleaned_count > 0:
                    logger.info(f"Reaped and cleaned up {cleaned_count} expired session(s)")

                # 2. Reconcile sessions whose K8s pods have vanished
                reconciled_count = await session_service.reconcile_orphaned_sessions(db)
                if reconciled_count > 0:
                    logger.info(f"Reconciled {reconciled_count} orphaned session(s) (pods no longer exist)")
        except Exception as e:
            logger.error(f"Error in session cleanup worker: {e}")

        await asyncio.sleep(settings.SESSION_CLEANUP_INTERVAL_SECONDS)
