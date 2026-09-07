from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    activity,
    auth,
    challenge,
    health,
    session,
    vpn,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(session.router)
api_router.include_router(vpn.router)
api_router.include_router(challenge.router)
api_router.include_router(activity.router)
api_router.include_router(health.router)
