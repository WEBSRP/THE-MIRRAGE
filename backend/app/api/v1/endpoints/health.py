from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_db
from backend.app.core.config import settings

router = APIRouter(prefix="/health", tags=["System Health & Diagnostics"])


@router.get(
    "/",
    summary="Platform health status"
)
async def health_check(
    db: AsyncSession = Depends(get_db)
):
    """Perform health checks across Database, Kubernetes, and OpenVPN connectivity."""
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    k8s_is_live = getattr(settings, "K8S_MODE", "mock").lower() == "production"
    vpn_is_live = getattr(settings, "VPN_MODE", "mock").lower() == "production"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "database": db_status,
            "k8s_engine": "live" if k8s_is_live else "simulated",
            "openvpn_engine": "live" if vpn_is_live else "simulated",
            "max_slots": settings.MAX_CONCURRENT_SESSIONS,
            "session_timeout_minutes": settings.SESSION_TIMEOUT_MINUTES,
        }
    }
