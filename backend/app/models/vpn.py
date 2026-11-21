from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
    # Canonical reserved VPN IP; telemetry must never change the reservation.
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


class VpnAddressReservation(Base):
    """Stable, unique certificate/address binding, retained across revocations."""
    __tablename__ = "vpn_address_reservations"

    address: Mapped[str] = mapped_column(String(45), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    client_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class VpnRevocation(Base):
    """Durable deny/operation record; survives profile/account deletion."""
    __tablename__ = "vpn_revocations"

    client_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[Optional[str]] = mapped_column(String(36))
    last_error: Mapped[Optional[str]] = mapped_column(String(64))
    certificate_pem: Mapped[Optional[str]] = mapped_column(Text)  # Public certificate only; no key/profile.


class VpnCrlMaintenance(Base):
    """Singleton lease/health state for CRL checks across API workers."""
    __tablename__ = "vpn_crl_maintenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[Optional[str]] = mapped_column(String(36))
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(String(64))
