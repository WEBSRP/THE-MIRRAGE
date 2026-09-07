from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel
from backend.app.models.activity import ActivityEventType


class ActivityLogCreate(BaseModel):
    event_type: ActivityEventType
    summary: str
    payload: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class ActivityLogOut(BaseModel):
    id: str
    event_type: ActivityEventType
    summary: str
    payload: Optional[Dict[str, Any]] = None
    source_ip: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}
