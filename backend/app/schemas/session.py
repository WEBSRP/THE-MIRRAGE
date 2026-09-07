from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from backend.app.models.session import SessionStatus


class SessionStartRequest(BaseModel):
    # Optional parameters for future customization
    difficulty: Optional[str] = "standard"


class SessionResponse(BaseModel):
    session_id: str
    mirage_ip: Optional[str] = None
    status: SessionStatus
    mirage_port: int = 22
    player_vpn_ip: Optional[str] = None
    expires_at: Optional[datetime] = None
    time_remaining_seconds: Optional[int] = None
    message: Optional[str] = None

    model_config = {"from_attributes": True}


class SessionStatusResponse(BaseModel):
    session_id: str
    status: SessionStatus
    mirage_ip: Optional[str] = None
    mirage_port: int = 22
    player_vpn_ip: Optional[str] = None
    created_at: datetime
    ready_at: Optional[datetime] = None
    expires_at: datetime
    last_active_at: datetime
    time_remaining_seconds: int
    is_ready: bool

    model_config = {"from_attributes": True}


class ActiveSlotsInfo(BaseModel):
    total_slots: int
    active_slots: int
    available_slots: int
    is_slot_available: bool
