from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, List
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base

if TYPE_CHECKING:
    from backend.app.models.user import User


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    slug: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )
    title: Mapped[str] = mapped_column(
        String(128),
        nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(64),
        default="Deception",
        nullable=False
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    points: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False
    )
    # sha256:<hex>; legacy column name retained to avoid an ALTER on existing DBs.
    flag: Mapped[str] = mapped_column(
        String(128),
        nullable=False
    )
    hint: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    submissions: Mapped[List["FlagSubmission"]] = relationship(
        "FlagSubmission",
        back_populates="challenge",
        cascade="all, delete-orphan"
    )


class FlagSubmission(Base):
    __tablename__ = "flag_submissions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    challenge_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("challenges.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    submitted_flag: Mapped[str] = mapped_column(
        # Legacy column retained; new attempts store only [REDACTED].
        String(128),
        nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="submissions")
    challenge: Mapped["Challenge"] = relationship("Challenge", back_populates="submissions")


class ChallengeSolve(Base):
    """One authoritative solve per player/challenge, enforced across workers."""
    __tablename__ = "challenge_solves"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    challenge_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    solved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)


class FlagSubmissionQuota(Base):
    """Database-backed, account-wide fixed-window limit, shared by API workers."""
    __tablename__ = "flag_submission_quotas"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    window: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
