import asyncio
import logging
from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal
from backend.app.services import session_queue
from backend.app.services.session_service import session_service
from backend.app.services.vpn_revocation import vpn_revocation_service
from backend.app.services.orphan_cleanup import orphan_cleanup_service
from backend.app.services.otp_abuse import otp_abuse_limiter
from backend.app.services.email_health import email_health

logger = logging.getLogger("mirrage.worker.cleanup")


async def session_cleanup_worker():
    """Independent durable jobs: a failed CRL operation cannot skip pod cleanup."""
    logger.info("Starting MIRRAGE cleanup/revocation worker...")
    operations = [
        ("vpn_revocations", vpn_revocation_service.process_pending),
        ("expired_sessions", session_service.cleanup_expired_sessions),
        ("session_reconciliation", session_service.reconcile_orphaned_sessions),
        ("orphan_resources", orphan_cleanup_service.sweep),
        ("session_queue", session_queue.process),
        ("crl_maintenance", vpn_revocation_service.maintain_crl),
        ("otp_ip_buckets", otp_abuse_limiter.cleanup),
        ("email_health", email_health.cleanup),
    ]
    while True:
        for name, operation in operations:
            try:
                async with AsyncSessionLocal() as db:
                    await operation(db)
            except Exception:
                logger.error("Background operation failed: %s; will retry", name)
        await asyncio.sleep(min(settings.SESSION_CLEANUP_INTERVAL_SECONDS,
                                settings.VPN_REVOCATION_RETRY_SECONDS))
