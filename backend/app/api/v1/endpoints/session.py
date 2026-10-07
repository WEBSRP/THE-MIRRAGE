from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_current_user, get_db, get_optional_current_user
from backend.app.models.user import User
from backend.app.schemas.session import (
    ActiveSlotsInfo,
    SessionResponse,
    SessionStartRequest,
    SessionStatusResponse,
)
from backend.app.services.auth_service import auth_service
from backend.app.services.session_service import session_service

router = APIRouter(prefix="/session", tags=["Session & Environment Management"])


@router.get(
    "/slots",
    response_model=ActiveSlotsInfo,
    summary="Check available session slots"
)
async def get_slots(
    db: AsyncSession = Depends(get_db)
):
    """Check how many of the 3 player session slots are currently available."""
    return await session_service.get_active_slots_info(db)


@router.post(
    "/start",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start machine (Mirage + CTF environment)"
)
async def start_session(
    request: Optional[SessionStartRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start the player machine:
    1. Verifies that an active slot is available (max 3 concurrent).
    2. Provisions an isolated Kubernetes Pod containing Mirage (decoy) and CTF (core).
    3. Retrieves the Pod IP in the 10.42.0.0/16 subnet.
    4. Returns the Mirage endpoint (10.42.0.x) to the player.
    """
    return await session_service.start_session(db=db, user=current_user, request=request)


@router.get(
    "/status",
    response_model=SessionStatusResponse,
    summary="Get current machine status"
)
async def get_status(
    session_id: Optional[str] = Query(None, description="Optional specific session ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch the status, countdown timer, and IP endpoints of the player's active session.
    Automatically handles expiration when the 30-minute inactivity window is exceeded.
    """
    return await session_service.get_session_status(db=db, user=current_user, session_id=session_id)


@router.post(
    "/stop",
    response_model=SessionResponse,
    summary="Stop machine and delete Pod"
)
async def stop_session(
    session_id: Optional[str] = Query(None, description="Optional specific session ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Stop the player's active machine, delete the Kubernetes pod, and free the slot.
    """
    return await session_service.stop_session(db=db, user=current_user, session_id=session_id)


@router.post(
    "/extend",
    response_model=SessionStatusResponse,
    summary="Extend active session by 1 hour"
)
async def extend_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Extend the player's active session by 1 hour.
    The session must be active and not yet expired.
    Subject to the maximum session duration limit.
    """
    return await session_service.extend_session(db=db, user=current_user)
