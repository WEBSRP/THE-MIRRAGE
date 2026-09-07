from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_current_user, get_db
from backend.app.models.user import User
from backend.app.schemas.challenge import (
    ChallengeOut,
    FlagSubmitRequest,
    FlagSubmitResponse,
)
from backend.app.services.challenge_service import challenge_service

router = APIRouter(prefix="/challenges", tags=["CTF & Deception Challenges"])


@router.get(
    "/",
    response_model=List[ChallengeOut],
    summary="List available CTF challenges"
)
async def list_challenges(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all active challenges and whether the player has solved them."""
    return await challenge_service.list_challenges(db=db, user=current_user)


@router.post(
    "/submit",
    response_model=FlagSubmitResponse,
    summary="Submit a challenge flag"
)
async def submit_flag(
    payload: FlagSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a flag for verification.
    If correct, awards points and records the deception breakthrough.
    """
    return await challenge_service.submit_flag(
        db=db,
        user=current_user,
        challenge_slug=payload.challenge_slug,
        submitted_flag=payload.flag,
    )
