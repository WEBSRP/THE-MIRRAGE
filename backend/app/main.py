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

    # 1. Initialize DB tables
    await init_db()
    logger.info("Database schema synchronized.")

    # 2. Seed initial challenges
    async with AsyncSessionLocal() as db:
        await challenge_service.seed_default_challenges(db)
    logger.info("Default CTF and deception challenges seeded.")

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
    description="Cybersecurity CTF & Deception Honeypot Platform API",
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
