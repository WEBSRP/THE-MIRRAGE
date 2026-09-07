from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.activity import ActivityEventType, ActivityLog
from backend.app.models.user import User


def _sanitize_payload(data: Any) -> Any:
    """Recursively mask sensitive values in activity log payloads."""
    SENSITIVE_KEYS = {
        "password", "token", "access_token", "secret", "secret_key",
        "private_key", "ca_key", "passphrase", "ovpn", "config_data",
        "authorization", "flag"
    }
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(sens in k.lower() for sens in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize_payload(v)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_payload(item) for item in data]
    return data


class ActivityService:
    async def log_event(
        self,
        db: AsyncSession,
        user_id: str,
        event_type: ActivityEventType,
        summary: str,
        payload: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        source_ip: Optional[str] = None,
    ) -> ActivityLog:
        """Create and persist an activity log entry with automatic sensitive data masking."""
        safe_payload = _sanitize_payload(payload) if payload else None
        log_entry = ActivityLog(
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            summary=summary,
            payload=safe_payload,
            source_ip=source_ip,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(log_entry)
        await db.commit()
        await db.refresh(log_entry)
        return log_entry

    async def get_user_activity(
        self,
        db: AsyncSession,
        user: User,
        limit: int = 50,
        offset: int = 0
    ) -> List[ActivityLog]:
        """Fetch audit log history for a player."""
        query = (
            select(ActivityLog)
            .where(ActivityLog.user_id == user.id)
            .order_by(desc(ActivityLog.timestamp))
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        return list(result.scalars().all())


activity_service = ActivityService()
