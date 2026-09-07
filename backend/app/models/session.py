from datetime import datetime, timezone
import enum
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base

if TYPE_CHECKING:
    from backend.app.models.user import User
    from backend.app.models.activity import ActivityLog


class SessionStatus(str, enum.Enum):
    PENDING = "pending"
    INITIALIZING = "initializing"
    PROVISIONING = "provisioning"
    READY = "ready"
    STOPPING = "stopping"
    TERMINATED = "terminated"
    EXPIRED = "expired"
    ERROR = "error"


class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: f"session-{uuid.uuid4().hex[:8]}"
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus),
        default=SessionStatus.PENDING,
        index=True,
        nullable=False
    )

    # Kubernetes Metadata
    pod_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    pod_namespace: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pod_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Decoy and Internal Network IP Endpoints
    # The decoy/honeypot IP displayed to the user
    mirage_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    # The internal CTF challenge IP (NEVER directly exposed in public endpoints)
    ctf_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Player's assigned VPN IP (e.g. 10.8.0.X)
    player_vpn_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Ports
    mirage_port: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    ctf_port: Mapped[int] = mapped_column(Integer, default=2222, nullable=False)

    # Lifecycle & Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    ready_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    terminated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    activity_logs: Mapped[List["ActivityLog"]] = relationship(
        "ActivityLog",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    @property
    def is_active(self) -> bool:
        return self.status in (
            SessionStatus.PENDING,
            SessionStatus.INITIALIZING,
            SessionStatus.PROVISIONING,
            SessionStatus.READY,
        )
