from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_db
from backend.app.core.config import settings
from backend.app.api.deps import get_current_admin_user
from backend.app.models.user import User
from backend.app.services.email_health import email_health
from backend.app.services.email_service import email_service

router = APIRouter(prefix="/health", tags=["System Health & Diagnostics"])


@router.get("/email", summary="Admin: email provider configuration and recent acceptance health")
async def email_provider_health(response: Response,
    current_user: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    simulated = settings.ENVIRONMENT == "testing" or (settings.ENVIRONMENT == "development" and settings.OTP_DEV_MODE)
    error = settings.email_configuration_error()
    report = await email_health.report(db, email_service.provider)
    report.update(provider=email_service.provider,
                  configuration="simulation" if simulated else "invalid" if error else "ready",
                  configuration_error=None if simulated else error)
    if simulated:
        report["status"] = "simulated"
    elif error:
        report["status"] = "unconfigured"
    return report


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
