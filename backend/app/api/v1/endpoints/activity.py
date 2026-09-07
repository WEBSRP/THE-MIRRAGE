from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_current_user, get_db
from backend.app.models.user import User
from backend.app.schemas.activity import ActivityLogOut
from backend.app.services.activity_service import activity_service

router = APIRouter(prefix="/activity", tags=["Player Telemetry & Deception Logs"])


@router.get(
    "/",
    response_model=List[ActivityLogOut],
    summary="Get player activity and honeypot interaction logs"
)
async def get_my_activity(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve audit events, session activities, and honeypot triggers for the player."""
    return await activity_service.get_user_activity(
        db=db, user=current_user, limit=limit, offset=offset
    )
