from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


class VpnProfileOut(BaseModel):
    client_name: str
    assigned_ip: Optional[str] = None
    is_connected: bool
    connected_since: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    revoked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class VpnStatusOut(BaseModel):
    connected_clients: int = 0
    is_connected: bool
    assigned_ip: Optional[str] = None
    bytes_received: int
    bytes_sent: int
    connected_since: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    indicator: str  # "connected" | "disconnected" | "standby"


class VpnDownloadOut(BaseModel):
    filename: str
    config_data: str
    client_ip: Optional[str] = None


class VpnRevokeResponse(BaseModel):
    message: str
    revoked_at: datetime
    user_id: str
    status: Literal["pending", "completed"]
    completed_at: Optional[datetime] = None
    attempts: int = 0
    last_error: Optional[str] = None


class VpnCrlHealthOut(BaseModel):
    checked_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_error: Optional[str] = None
