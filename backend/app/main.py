import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.api.v1.api import api_router
from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.core.exceptions import MirrageException
from backend.app.core.flags import get_shared_flags
from backend.app.services.challenge_service import challenge_service
from backend.app.workers.cleanup import session_cleanup_worker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mirrage.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifespan events."""
    logger.info("Initializing MIRRAGE backend engine...")

    # 0. Validate production safety (fails closed if production is misconfigured)
    settings.validate_production_config()
    get_shared_flags()  # Fail before touching the DB if production flags are missing/invalid.
    if settings.K8S_MODE == "production":
        from backend.app.services.session_gateway import session_gateway
        await session_gateway.check()
    if settings.VPN_MODE == "production":
        from backend.app.services.vpn_control import vpn_control
        await vpn_control.health()

    # 1. Require an explicitly migrated schema before any seed/cleanup writes.
    await init_db()
    logger.info("Database migration revision verified.")

    # 2. Seed initial challenges
    async with AsyncSessionLocal() as db:
        await challenge_service.seed_default_challenges(db)
    logger.info("Default CTF and deception challenges seeded.")

    # 2.5 Reconcile any orphaned/stale sessions from DB against Kubernetes on startup
    try:
        from backend.app.services.session_service import session_service
        async with AsyncSessionLocal() as db:
            reconciled = await session_service.reconcile_orphaned_sessions(db)
            if reconciled > 0:
                logger.info(f"Startup reconciliation: cleaned {reconciled} orphaned session(s).")
    except Exception as e:
        logger.error(f"Startup reconciliation error: {e}")

    # Scan actual resources as well as DB rows after a controller restart.
    try:
        from backend.app.services.orphan_cleanup import orphan_cleanup_service
        async with AsyncSessionLocal() as db:
            await orphan_cleanup_service.sweep(db)
    except Exception:
        logger.error("Startup resource sweep failed; periodic worker will retry")

    # 3. Start background worker for session expiration & cleanup
    cleanup_task = asyncio.create_task(session_cleanup_worker())

    yield

    # Shutdown
    logger.info("Shutting down MIRRAGE backend engine...")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Cybersecurity CTF Platform API",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Set up CORS Middleware (restricted methods and headers)
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        expose_headers=["Retry-After"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    )


# Exception handler for domain exceptions
@app.exception_handler(MirrageException)
async def mirrage_exception_handler(request: Request, exc: MirrageException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": exc.code,
            "message": exc.detail,
        },
        headers=exc.headers,
    )


# Generic fallback exception handler (prevents leaking internal stack traces)
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


# Mount main API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)


# Root info endpoint
@app.get("/", tags=["Root"])
async def root_info():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": f"{settings.API_V1_STR}/docs",
        "tagline": "What you see is not what was built.",
    }
