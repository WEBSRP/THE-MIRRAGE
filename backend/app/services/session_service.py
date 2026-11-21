"""
MIRRAGE Session Service — Manages player machine lifecycle.

Slot reservation is serialized in the database. READY requires an owner policy
and a gateway lease. Fixed session lifetime changes only through explicit renewal.
Cleanup revokes access before deleting pods; failures retain a slot for retries.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.exceptions import (
    ActiveSessionExistsError,
    EntityNotFoundError,
    MirrageException,
    SlotLimitExceededError,
)
from backend.app.models.activity import ActivityEventType, ActivityLog
from backend.app.models.session import GameSession, SessionStatus
from backend.app.models.user import User
from backend.app.services.vpn_access import require_vpn_access, vpn_access_revoked
from backend.app.schemas.session import (
    ActiveSlotsInfo,
    SessionResponse,
    SessionStartRequest,
    SessionStatusResponse,
)

logger = logging.getLogger("mirrage.session")

# Statuses considered "active" (consuming a slot)
ACTIVE_STATUSES = [
    SessionStatus.PENDING,
    SessionStatus.INITIALIZING,
    SessionStatus.PROVISIONING,
    SessionStatus.READY,
    SessionStatus.STOPPING,
]


def _to_utc(dt: Optional[datetime]) -> datetime:
    """Ensure datetime object is timezone-aware UTC."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _time_remaining(expires_at: datetime) -> int:
    """Compute seconds remaining until expiration."""
    now = datetime.now(timezone.utc)
    return max(0, int((_to_utc(expires_at) - now).total_seconds()))


class SessionService:
    def __init__(self):
        # Lazy import to avoid circular imports at module level
        self._k8s = None
        self._vpn = None
        self._slot_lock = asyncio.Lock()
        self._runtime_lock = asyncio.Lock()
        self._gateway = None

    @property
    def k8s_provisioner(self):
        if self._k8s is None:
            from backend.app.services.k8s_service import k8s_provisioner
            self._k8s = k8s_provisioner
        return self._k8s

    @property
    def vpn_service(self):
        if self._vpn is None:
            from backend.app.services.vpn_service import vpn_service
            self._vpn = vpn_service
        return self._vpn

    async def get_active_slots_info(self, db: AsyncSession) -> ActiveSlotsInfo:
        """Query currently active sessions vs max slot limit."""
        query = select(func.count(GameSession.id)).where(
            GameSession.status.in_(ACTIVE_STATUSES)
        )
        result = await db.execute(query)
        active_count = result.scalar() or 0
        total_slots = settings.MAX_CONCURRENT_SESSIONS
        available = max(0, total_slots - active_count)

        return ActiveSlotsInfo(
            total_slots=total_slots,
            active_slots=active_count,
            available_slots=available,
            is_slot_available=available > 0,
        )

    async def _acquire_slot_atomic(self, db: AsyncSession, user_id: str) -> None:
        """
        Atomically verify slot availability and user session uniqueness.

        Uses SELECT ... FOR UPDATE on active sessions to serialize concurrent
        session-start requests. This prevents the TOCTOU race condition where
        multiple requests pass the count check simultaneously.

        For SQLite (testing), falls back to a simple count check since SQLite
        does not support FOR UPDATE.
        """
        is_sqlite = "sqlite" in str(db.bind.url) if db.bind else False

        if is_sqlite:
            # SQLite fallback: simple count (acceptable for single-threaded tests)
            count_query = select(func.count(GameSession.id)).where(
                GameSession.status.in_(ACTIVE_STATUSES)
            )
            result = await db.execute(count_query)
            active_count = result.scalar() or 0

            if active_count >= settings.MAX_CONCURRENT_SESSIONS:
                raise SlotLimitExceededError(settings.MAX_CONCURRENT_SESSIONS)

            # Check user doesn't already have active session
            user_query = select(GameSession).where(
                GameSession.user_id == user_id,
                GameSession.status.in_(ACTIVE_STATUSES),
            )
            user_result = await db.execute(user_query)
            existing = user_result.scalars().first()
            if existing:
                raise ActiveSessionExistsError(existing.id)
        else:
            # PostgreSQL: Use FOR UPDATE to lock active session rows
            # This serializes concurrent session-start requests
            lock_query = (
                select(GameSession)
                .where(GameSession.status.in_(ACTIVE_STATUSES))
                .with_for_update()
            )
            result = await db.execute(lock_query)
            active_sessions = list(result.scalars().all())

            if len(active_sessions) >= settings.MAX_CONCURRENT_SESSIONS:
                raise SlotLimitExceededError(settings.MAX_CONCURRENT_SESSIONS)

            # Check if this user already has an active session
            for session in active_sessions:
                if session.user_id == user_id:
                    raise ActiveSessionExistsError(session.id)

    @property
    def gateway(self):
        if self._gateway is None:
            from backend.app.services.session_gateway import session_gateway
            self._gateway = session_gateway
        return self._gateway

    async def _end_session(self, db, session, final_status):
        """Revoke ingress BEFORE deleting/releasing a pod IP. Retry failures."""
        async with self._runtime_lock:
            await db.refresh(session, with_for_update=True)
            if final_status == SessionStatus.EXPIRED and _to_utc(session.expires_at) > datetime.now(timezone.utc):
                return False  # A concurrent extension won the database row lock.
            if session.status in (SessionStatus.TERMINATED, SessionStatus.EXPIRED):
                return True
            session.status = SessionStatus.STOPPING
            session.mirage_ip = session.pod_ip = session.ctf_ip = None
            await db.commit()
            try:
                await self.gateway.revoke(session.id)
                if session.pod_name and not await self.k8s_provisioner.delete_player_pod(session.pod_name):
                    raise RuntimeError("Pod or policy deletion is pending")
                await self.gateway.forget(session.id)
            except Exception:
                session.error_message = "Access/resource cleanup pending; automatic retry scheduled"
                await db.commit()
                return False
            session.status = final_status
            session.terminated_at = datetime.now(timezone.utc)
            await db.commit()
            return True

    @staticmethod
    def can_download_vpn(session: GameSession) -> bool:
        now = datetime.now(timezone.utc)
        return bool(
            session.status == SessionStatus.READY
            and session.ready_at is not None
            and session.mirage_ip
            and _to_utc(session.created_at) + timedelta(minutes=3) <= now
            and now < _to_utc(session.expires_at)
        )

    @staticmethod
    def vpn_downloads_remaining(session: GameSession) -> int:
        return max(0, settings.VPN_DOWNLOAD_LIMIT_PER_SESSION - session.vpn_download_count)

    async def consume_vpn_download(self, db: AsyncSession, user_id: str) -> str:
        await require_vpn_access(db, user_id)
        session = await self.get_active_session_for_user(db, user_id)
        not_ready = MirrageException(
            409, "VPN downloads unlock when your session is healthy and the countdown has ended.",
            "VPN_SESSION_NOT_READY",
        )
        if session is None or not self.can_download_vpn(session):
            raise not_ready

        now = datetime.now(timezone.utc)
        limit = settings.VPN_DOWNLOAD_LIMIT_PER_SESSION
        eligible = (
            GameSession.id == session.id,
            GameSession.user_id == user_id,
            GameSession.status == SessionStatus.READY,
            GameSession.ready_at.is_not(None),
            GameSession.mirage_ip == session.mirage_ip,
            GameSession.created_at <= now - timedelta(minutes=3),
            GameSession.expires_at > now,
        )
        # The conditional update arbitrates concurrent requests before credential work.
        result = await db.execute(
            update(GameSession).where(*eligible, GameSession.vpn_download_count < limit)
            .values(vpn_download_count=GameSession.vpn_download_count + 1)
            .returning(GameSession.vpn_download_count)
            .execution_options(synchronize_session="fetch")
        )
        if result.scalar_one_or_none() is None:
            count = await db.scalar(select(GameSession.vpn_download_count).where(*eligible))
            if count is not None and count >= limit:
                raise MirrageException(
                    429, "You have used all VPN downloads for this session.",
                    "VPN_DOWNLOAD_LIMIT_REACHED",
                )
            raise not_ready
        await db.commit()
        return session.id

    async def refund_vpn_download(self, db: AsyncSession, session_id: str) -> None:
        # Credential generation can open or commit transactions of its own.
        await db.rollback()
        await db.execute(
            update(GameSession)
            .where(GameSession.id == session_id, GameSession.vpn_download_count > 0)
            .values(vpn_download_count=GameSession.vpn_download_count - 1)
        )
        await db.commit()

    async def _reconcile_single_session(self, db: AsyncSession, session: GameSession) -> GameSession:
        now = datetime.now(timezone.utc)
        if session.status == SessionStatus.STOPPING:
            await self._end_session(db, session, SessionStatus.TERMINATED)
            return session
        if not session.is_active:
            if session.mirage_ip or session.pod_ip or session.ctf_ip:
                session.mirage_ip = session.pod_ip = session.ctf_ip = None
                await db.commit()
            return session
        if await vpn_access_revoked(db, session.user_id):
            await self._end_session(db, session, SessionStatus.TERMINATED)
            return session
        if _to_utc(session.expires_at) <= now:
            await self._end_session(db, session, SessionStatus.EXPIRED)
            return session
        initializing = session.ready_at is None and session.status in (
            SessionStatus.PENDING, SessionStatus.INITIALIZING, SessionStatus.PROVISIONING
        )
        if initializing:
            # The start request owns the first READY transition, after gateway grant.
            # A worker must not kill the deterministic pod record before creation.
            if now >= _to_utc(session.created_at) + timedelta(minutes=3):
                await self._end_session(db, session, SessionStatus.ERROR)
            return session
        if not session.pod_name:
            await self._end_session(db, session, SessionStatus.TERMINATED)
            return session
        try:
            pod = await self.k8s_provisioner.get_pod_status(session.pod_name)
            if pod is None or pod.get("phase") not in ("Running", "Pending"):
                await self._end_session(db, session, SessionStatus.TERMINATED)
            elif settings.K8S_MODE == "production" and (
                pod.get("user_id") != session.user_id or pod.get("session_id") != session.id
            ):
                raise RuntimeError("Pod ownership does not match session")
            elif not pod.get("ready") or not pod.get("ip"):
                session.status = SessionStatus.INITIALIZING
                session.mirage_ip = session.pod_ip = session.ctf_ip = None
                await db.commit()
            elif (session.status != SessionStatus.READY or session.mirage_ip != pod["ip"]
                  or not await self.gateway.active(session.id, session.player_vpn_ip, pod["ip"], _to_utc(session.expires_at))):
                async with self._runtime_lock:
                    await db.refresh(session, with_for_update=True)
                    if not session.is_active:
                        return session
                    if pod.get("user_id") not in (None, session.user_id) or pod.get("session_id") not in (None, session.id):
                        raise RuntimeError("Pod ownership changed")
                    if settings.K8S_MODE == "production" and (
                        pod.get("user_id") != session.user_id or pod.get("session_id") != session.id
                    ):
                        raise RuntimeError("Pod ownership labels are missing")
                    await require_vpn_access(db, session.user_id, lock=True)
                    await self.gateway.revoke(session.id)
                    await self.gateway.forget(session.id)
                    await self.gateway.grant(session.id, session.player_vpn_ip, pod["ip"], _to_utc(session.expires_at))
                    session.status = SessionStatus.READY
                    session.mirage_ip = session.pod_ip = session.ctf_ip = pod["ip"]
                    await db.commit()
        except Exception:
            logger.error("Cannot reconcile session %s; revoking access", session.id)
            await db.rollback()
            await self._end_session(db, session, SessionStatus.ERROR)
        return session

    async def get_active_session_for_user(
        self, db: AsyncSession, user_id: str
    ) -> Optional[GameSession]:
        """Fetch currently active session for the given user, reconciling with K8s if needed."""
        query = (
            select(GameSession)
            .where(
                GameSession.user_id == user_id,
                GameSession.status.in_(ACTIVE_STATUSES),
            )
            .order_by(GameSession.created_at.desc())
        )
        result = await db.execute(query)
        session = result.scalars().first()

        if not session:
            return None

        # Reconcile session against Kubernetes
        session = await self._reconcile_single_session(db, session)
        if not session.is_active:
            return None

        return session

    def _record_activity(self, session: GameSession) -> None:
        """
        Record meaningful activity on the session.

        Updates last_active_at but does NOT modify expires_at.
        Session lifetime is fixed at creation (SESSION_TIMEOUT_MINUTES).
        Explicit extension requires the extend_session endpoint.
        """
        session.last_active_at = datetime.now(timezone.utc)

    async def start_session(
        self,
        db: AsyncSession,
        user: User,
        request: Optional[SessionStartRequest] = None,
    ) -> SessionResponse:
        """
        Start machine:
        1. Atomically check active slots (< MAX_CONCURRENT_SESSIONS) and user uniqueness
        2. Provision Pod (Mirage + CTF)
        3. Wait for pod readiness and verify CURRENT pod IP
        4. Return session details
        """
        await require_vpn_access(db, user.id)
        # 1. Reconcile and check for existing active session
        existing_session = await self.get_active_session_for_user(db, user.id)
        if existing_session:
            if existing_session.status == SessionStatus.READY:
                return SessionResponse(
                    session_id=existing_session.id,
                    mirage_ip=existing_session.mirage_ip,
                    status=existing_session.status,
                    mirage_port=existing_session.mirage_port,
                    ctf_port=existing_session.ctf_port,
                    player_vpn_ip=existing_session.player_vpn_ip,
                    expires_at=existing_session.expires_at,
                    initialization_deadline=existing_session.created_at + timedelta(minutes=3),
                    time_remaining_seconds=_time_remaining(existing_session.expires_at),
                    message="Active session restored",
                )
            else:
                raise ActiveSessionExistsError(existing_session.id)

        # VPN provisioning commits its own durable reservation before slot locking.
        # 2. Atomically reserve slot and create INITIALIZING record under mutual exclusion
        async with self._slot_lock:
            vpn_profile = await self.vpn_service.generate_or_get_profile(db, user)
            await self.reconcile_orphaned_sessions(db)
            if db.bind and db.bind.dialect.name == "postgresql":
                await db.execute(text("SELECT pg_advisory_xact_lock(74291823)"))

            count_query = select(func.count(GameSession.id)).where(
                GameSession.status.in_(ACTIVE_STATUSES)
            )
            result = await db.execute(count_query)
            active_count = result.scalar() or 0

            if active_count >= settings.MAX_CONCURRENT_SESSIONS:
                raise SlotLimitExceededError(settings.MAX_CONCURRENT_SESSIONS)

            user_query = select(GameSession).where(
                GameSession.user_id == user.id,
                GameSession.status.in_(ACTIVE_STATUSES),
            )
            user_result = await db.execute(user_query)
            existing = user_result.scalars().first()
            if existing:
                raise ActiveSessionExistsError(existing.id)

            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)
            init_deadline = now + timedelta(minutes=3)

            new_session = GameSession(
                user_id=user.id,
                status=SessionStatus.INITIALIZING,
                player_vpn_ip=vpn_profile.assigned_ip,
                mirage_port=2222,
                ctf_port=22,
                created_at=now,
                expires_at=expires_at,
                last_active_at=now,
            )
            db.add(new_session)
            await db.flush()
            new_session.pod_name = self.k8s_provisioner.pod_name(new_session.id)
            new_session.pod_namespace = settings.K8S_NAMESPACE
            await db.commit()
            await db.refresh(new_session)

        # 3. Provision Kubernetes Pod and confirm readiness
        user_id = user.id
        try:
            pod_name, mirage_ip, ctf_ip = await self.k8s_provisioner.provision_player_pod(
                session_id=new_session.id,
                user_id=user_id,
                username=user.username,
                player_vpn_ip=new_session.player_vpn_ip,
            )

            pod_status = await self.k8s_provisioner.get_pod_status(pod_name)
            if not pod_status or not pod_status.get("ready") or not pod_status.get("ip"):
                raise RuntimeError(f"Pod {pod_name} did not become ready or has no IP")

            async with self._runtime_lock:
                await db.refresh(new_session, with_for_update=True)
                if new_session.status != SessionStatus.INITIALIZING:
                    raise RuntimeError("Session was stopped while provisioning")
                await require_vpn_access(db, user_id, lock=True)
                new_session.pod_name = pod_name
                new_session.pod_ip = new_session.mirage_ip = pod_status["ip"]
                new_session.ctf_ip = ctf_ip
                await self.gateway.grant(new_session.id, new_session.player_vpn_ip,
                                         pod_status["ip"], _to_utc(new_session.expires_at))
                new_session.status = SessionStatus.READY
                new_session.ready_at = datetime.now(timezone.utc)
                self._record_activity(new_session)
                db.add(ActivityLog(
                    id=str(uuid.uuid4()), user_id=user_id, session_id=new_session.id,
                    event_type=ActivityEventType.SESSION_START,
                    summary=f"Player started machine (Mirage IP: {pod_status['ip']})",
                    payload={"mirage_ip": pod_status["ip"], "vpn_ip": new_session.player_vpn_ip,
                             "session_id": new_session.id},
                ))
                await db.commit()
                await db.refresh(new_session)

            return SessionResponse(
                session_id=new_session.id,
                mirage_ip=new_session.mirage_ip,
                status=new_session.status,
                mirage_port=new_session.mirage_port,
                ctf_port=new_session.ctf_port,
                player_vpn_ip=new_session.player_vpn_ip,
                expires_at=new_session.expires_at,
                initialization_deadline=init_deadline,
                time_remaining_seconds=_time_remaining(new_session.expires_at),
                message="Mirage environment initialized successfully",
            )

        except Exception as e:
            logger.error(f"Session provisioning failed for user {user_id}: {e}")
            await db.rollback()
            await self._end_session(db, new_session, SessionStatus.ERROR)

            raise MirrageException(
                status_code=500,
                detail="Failed to provision session environment. Please try again.",
                code="SESSION_PROVISION_ERROR",
            )

    async def get_session_status(
        self,
        db: AsyncSession,
        user: User,
        session_id: Optional[str] = None,
        is_activity: bool = False,
    ) -> SessionStatusResponse:
        """
        Get status of specific session or user's active session.
        Authoritative source of truth: verifies against Kubernetes.
        """
        session = None
        if session_id:
            query = select(GameSession).where(
                GameSession.id == session_id,
                GameSession.user_id == user.id,
            )
            result = await db.execute(query)
            session = result.scalars().first()
            if not session:
                raise EntityNotFoundError("GameSession", session_id)
            if session.is_active:
                session = await self._reconcile_single_session(db, session)
        else:
            session = await self.get_active_session_for_user(db, user.id)
            if not session:
                last_query = (
                    select(GameSession)
                    .where(GameSession.user_id == user.id)
                    .order_by(GameSession.created_at.desc())
                )
                last_res = await db.execute(last_query)
                session = last_res.scalars().first()
                if not session:
                    raise EntityNotFoundError("Active Session for User", user.username)

        # Record meaningful activity (does not change expiration)
        if session.is_active and is_activity:
            self._record_activity(session)
            await db.commit()

        # CRITICAL RULE: If session is NOT active, NEVER return target IP or is_ready=True
        if not session.is_active:
            time_rem = 0
            is_ready = False
            mirage_ip = None
        else:
            time_rem = _time_remaining(session.expires_at)
            is_ready = (session.status == SessionStatus.READY)
            mirage_ip = session.mirage_ip if is_ready else None

        init_deadline = session.created_at + timedelta(minutes=3)

        return SessionStatusResponse(
            session_id=session.id,
            status=session.status,
            mirage_ip=mirage_ip,
            mirage_port=session.mirage_port,
            ctf_port=session.ctf_port,
            player_vpn_ip=session.player_vpn_ip,
            created_at=session.created_at,
            ready_at=session.ready_at,
            expires_at=session.expires_at,
            initialization_deadline=init_deadline,
            last_active_at=session.last_active_at,
            time_remaining_seconds=time_rem,
            is_ready=is_ready,
            vpn_download_available=self.can_download_vpn(session) and self.vpn_downloads_remaining(session) > 0,
            vpn_downloads_remaining=self.vpn_downloads_remaining(session),
        )

    async def record_activity(
        self, db: AsyncSession, session: GameSession
    ) -> None:
        if session.is_active:
            self._record_activity(session)
            await db.commit()

    async def record_activity_for_user(
        self, db: AsyncSession, user_id: str
    ) -> None:
        session = await self.get_active_session_for_user(db, user_id)
        if session and session.is_active:
            self._record_activity(session)
            await db.commit()

    async def stop_session(
        self,
        db: AsyncSession,
        user: User,
        session_id: Optional[str] = None,
    ) -> SessionResponse:
        """
        Stop and terminate an active session in the required order:
        1. Mark session stopping
        2. Delete Kubernetes resources
        3. Confirm deletion
        4. Release concurrency slot
        5. Clear runtime target information
        6. Mark session stopped
        7. Return correct state
        """
        if session_id:
            query = select(GameSession).where(
                GameSession.id == session_id,
                GameSession.user_id == user.id,
            )
            result = await db.execute(query)
            session = result.scalars().first()
            if not session:
                raise EntityNotFoundError("GameSession", session_id)
        else:
            session = await self.get_active_session_for_user(db, user.id)
            if not session:
                last_query = (
                    select(GameSession)
                    .where(GameSession.user_id == user.id)
                    .order_by(GameSession.created_at.desc())
                )
                last_res = await db.execute(last_query)
                session = last_res.scalars().first()
                if not session:
                    raise MirrageException(
                        status_code=400,
                        detail="No active session found to stop",
                        code="NO_ACTIVE_SESSION",
                    )

        # Idempotent: already stopped sessions return gracefully
        if session.status in (SessionStatus.TERMINATED, SessionStatus.EXPIRED):
            return SessionResponse(
                session_id=session.id,
                status=session.status,
                mirage_ip=None,
                message="Session already stopped",
            )

        if not await self._end_session(db, session, SessionStatus.TERMINATED):
            raise MirrageException(503, "Session access cleanup is pending; retry shortly", "SESSION_CLEANUP_PENDING")

        activity = ActivityLog(
            id=str(uuid.uuid4()),
            user_id=user.id,
            session_id=session.id,
            event_type=ActivityEventType.SESSION_STOP,
            summary=f"Player stopped machine (Session: {session.id})",
        )
        db.add(activity)
        await db.commit()

        # 7. Return correct state to frontend
        return SessionResponse(
            session_id=session.id,
            status=session.status,
            mirage_ip=None,
            message="Session terminated successfully",
        )

    async def extend_session(
        self,
        db: AsyncSession,
        user: User,
    ) -> SessionStatusResponse:
        """
        Extend the user's active session by exactly 1 hour.

        Validates:
        - Session is active and not expired
        - Total session duration does not exceed SESSION_MAX_DURATION_MINUTES
        - Session has not already been stopped/terminated

        Returns the updated session status.
        """
        await require_vpn_access(db, user.id)
        # Look for the user's latest session
        query = (
            select(GameSession)
            .where(GameSession.user_id == user.id)
            .order_by(GameSession.created_at.desc())
        )
        result = await db.execute(query)
        latest_session = result.scalars().first()

        if not latest_session:
            raise MirrageException(
                status_code=400,
                detail="No active session found to extend",
                code="NO_ACTIVE_SESSION",
            )

        now = datetime.now(timezone.utc)

        # Check if already expired or inactive
        if latest_session.status == SessionStatus.EXPIRED or _to_utc(latest_session.expires_at) <= now:
            raise MirrageException(
                status_code=400,
                detail="Session has already expired and cannot be extended",
                code="SESSION_EXPIRED",
            )

        if not latest_session.is_active:
            raise MirrageException(
                status_code=400,
                detail="Session is no longer active",
                code="SESSION_NOT_ACTIVE",
            )

        # Reconcile if needed
        session = await self._reconcile_single_session(db, latest_session)
        if session.status == SessionStatus.EXPIRED or _to_utc(session.expires_at) <= now:
            raise MirrageException(
                status_code=400,
                detail="Session has already expired and cannot be extended",
                code="SESSION_EXPIRED",
            )

        if not session.is_active:
            raise MirrageException(
                status_code=400,
                detail="Session is no longer active",
                code="SESSION_NOT_ACTIVE",
            )

        async with self._runtime_lock:
            await db.refresh(session, with_for_update=True)
            if session.status != SessionStatus.READY or not session.pod_ip:
                raise MirrageException(409, "Session is not ready for extension", "SESSION_NOT_READY")
            if not session.is_active or _to_utc(session.expires_at) <= datetime.now(timezone.utc):
                raise MirrageException(400, "Session is no longer active", "SESSION_NOT_ACTIVE")
            await require_vpn_access(db, session.user_id, lock=True)
            # Check max duration limit
            new_expires_at = _to_utc(session.expires_at) + timedelta(hours=1)
            total_duration = new_expires_at - _to_utc(session.created_at)
            max_duration = timedelta(minutes=settings.SESSION_MAX_DURATION_MINUTES)

            if total_duration > max_duration:
                raise MirrageException(
                    status_code=400,
                    detail=f"Cannot extend: maximum session duration of {settings.SESSION_MAX_DURATION_MINUTES} minutes would be exceeded",
                    code="MAX_DURATION_EXCEEDED",
                )

            # Commit expiry first: a controller crash must never leave a kernel
            # lease longer than the persisted session. Root renew cannot resurrect
            # a binding concurrently revoked by another API worker.
            session.expires_at = new_expires_at
            session.last_active_at = now
            await db.commit()
            try:
                await self.gateway.renew(session.id, session.player_vpn_ip, session.pod_ip, new_expires_at)
            except Exception:
                try:
                    await self.gateway.revoke(session.id)
                except Exception:
                    pass
                await db.refresh(session, with_for_update=True)
                if session.status not in (SessionStatus.TERMINATED, SessionStatus.EXPIRED):
                    session.status = SessionStatus.STOPPING
                    session.mirage_ip = session.pod_ip = session.ctf_ip = None
                    session.error_message = "Network renewal failed; cleanup pending"
                    await db.commit()
                raise MirrageException(503, "Network renewal failed; session cleanup is pending", "SESSION_CLEANUP_PENDING") from None
            await db.refresh(session)

        logger.info(
            f"Session {session.id} extended by 1 hour. "
            f"New expiration: {session.expires_at}"
        )

        # Return updated status
        init_deadline = session.created_at + timedelta(minutes=3)
        is_ready = session.status == SessionStatus.READY

        return SessionStatusResponse(
            session_id=session.id,
            status=session.status,
            mirage_ip=session.mirage_ip if is_ready else None,
            mirage_port=session.mirage_port,
            ctf_port=session.ctf_port,
            player_vpn_ip=session.player_vpn_ip,
            created_at=session.created_at,
            ready_at=session.ready_at,
            expires_at=session.expires_at,
            initialization_deadline=init_deadline,
            last_active_at=session.last_active_at,
            time_remaining_seconds=_time_remaining(session.expires_at),
            is_ready=is_ready,
            vpn_download_available=self.can_download_vpn(session) and self.vpn_downloads_remaining(session) > 0,
            vpn_downloads_remaining=self.vpn_downloads_remaining(session),
        )

    async def cleanup_expired_sessions(self, db: AsyncSession) -> int:
        now = datetime.now(timezone.utc)
        query = select(GameSession).where(
            GameSession.status.in_(ACTIVE_STATUSES),
            or_(GameSession.expires_at <= now, GameSession.status == SessionStatus.STOPPING,
                (GameSession.ready_at.is_(None)) & (GameSession.created_at <= now - timedelta(minutes=3))),
        )
        sessions = (await db.execute(query)).scalars().all()
        count = 0
        for session in sessions:
            final = SessionStatus.EXPIRED if _to_utc(session.expires_at) <= now else SessionStatus.TERMINATED
            count += int(await self._end_session(db, session, final))
        return count

    async def reconcile_orphaned_sessions(self, db: AsyncSession) -> int:
        sessions = (await db.execute(select(GameSession).where(
            GameSession.status.in_(ACTIVE_STATUSES)
        ))).scalars().all()
        count = 0
        for session in sessions:
            before = (session.status, session.mirage_ip)
            await self._reconcile_single_session(db, session)
            count += int(before != (session.status, session.mirage_ip))
        return count


session_service = SessionService()
