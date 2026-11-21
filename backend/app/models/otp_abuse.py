from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class OtpAbuseBucket(Base):
    """Current fixed window per pseudonymous IP identity or global send budget."""
    __tablename__ = "otp_abuse_buckets"

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    window: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
