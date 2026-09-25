from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base

if TYPE_CHECKING:
    from backend.app.models.user import User


class VpnProfile(Base):
    __tablename__ = "vpn_profiles"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False
    )
    client_name: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False
    )
    # The complete generated .ovpn profile content
    config_data: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    # Assigned static/dynamic player VPN IP in the 10.8.0.0/24 subnet
    assigned_ip: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True
    )
    is_connected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    bytes_received: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )
    bytes_sent: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )
    connected_since: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="vpn_profile")
