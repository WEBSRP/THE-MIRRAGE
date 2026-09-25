from datetime import datetime
from typing import Optional
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
