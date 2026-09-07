from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChallengeOut(BaseModel):
    id: str
    slug: str
    title: str
    category: str
    description: str
    points: int
    hint: Optional[str] = None
    is_solved: bool = False

    model_config = {"from_attributes": True}


class FlagSubmitRequest(BaseModel):
    challenge_slug: str
    flag: str = Field(..., min_length=4, max_length=128)


class FlagSubmitResponse(BaseModel):
    is_correct: bool
    message: str
    points_awarded: int = 0
    already_solved: bool = False
