from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class SessionQueueEntry(Base):
    __tablename__ = "session_queue_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    hold_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
