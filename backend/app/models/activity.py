from datetime import datetime, timezone
import enum
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base

if TYPE_CHECKING:
    from backend.app.models.user import User
    from backend.app.models.session import GameSession


class ActivityEventType(str, enum.Enum):
    SESSION_START = "session_start"
    SESSION_STOP = "session_stop"
    VPN_CONNECT = "vpn_connect"
    VPN_DISCONNECT = "vpn_disconnect"
    SSH_AUTH_ATTEMPT = "ssh_auth_attempt"
    SSH_COMMAND = "ssh_command"
    HONEYPOT_TRIGGER = "honeypot_trigger"
    DECEPTION_DISCOVERY = "deception_discovery"
    FLAG_SUBMISSION = "flag_submission"


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("game_sessions.id", ondelete="SET NULL"),
        index=True,
        nullable=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    event_type: Mapped[ActivityEventType] = mapped_column(
        Enum(ActivityEventType),
        index=True,
        nullable=False
    )
    summary: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True
    )
    source_ip: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="activity_logs")
    session: Mapped[Optional["GameSession"]] = relationship("GameSession", back_populates="activity_logs")
