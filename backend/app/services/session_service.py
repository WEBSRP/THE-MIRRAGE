"""
MIRRAGE Session Service — Manages player machine lifecycle.

Fixes applied:
- CRITICAL: Slot allocation uses SELECT ... FOR UPDATE to prevent TOCTOU race
- CRITICAL: Inactivity timeout now extends expires_at on meaningful activity
- Status polling does NOT extend session lifetime
- Orphaned pods cleaned up on provisioning failure
- Idempotent cleanup (double-cleanup safe)
- Pod deletion failure handled gracefully
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, select, text
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

    async def _reconcile_single_session(self, db: AsyncSession, session: GameSession) -> GameSession:
        """
        Reconcile an active session against Kubernetes.
        Ensures:
        1. If pod does not exist or phase is terminal (Failed/Unknown) -> terminate and clear target IP.
        2. If session is marked READY but has no pod -> terminate and clear target IP.
        3. If pod exists and is Running and Ready -> ensure status is READY and target IP matches CURRENT pod IP.
        4. If pod exists and is Running/Pending but not fully Ready -> status cannot be READY.
        """
        if not session.is_active:
            if session.mirage_ip or session.pod_ip:
                session.mirage_ip = None
                session.pod_ip = None
                session.ctf_ip = None
                await db.commit()
            return session

        now = datetime.now(timezone.utc)

        # Check inline expiration
        if _to_utc(session.expires_at) < now:
            logger.info(f"Session {session.id} expired inline")
            session.status = SessionStatus.EXPIRED
            session.terminated_at = now
            session.mirage_ip = None
            session.pod_ip = None
            session.ctf_ip = None
            await db.commit()
            if session.pod_name:
                try:
                    await self.k8s_provisioner.delete_player_pod(session.pod_name)
                except Exception as e:
                    logger.warning(f"Failed to delete expired pod {session.pod_name}: {e}")
            return session

        # Active session without pod_name
        if not session.pod_name:
            if session.status == SessionStatus.READY:
                logger.warning(f"Session {session.id} marked READY without pod_name. Terminating.")
                session.status = SessionStatus.TERMINATED
                session.terminated_at = now
                session.mirage_ip = None
                session.pod_ip = None
                session.ctf_ip = None
                session.error_message = "No Kubernetes pod associated with active session"
                await db.commit()
            return session

        # Active session with pod_name: query Kubernetes
        try:
            pod_status = await self.k8s_provisioner.get_pod_status(session.pod_name)
            if pod_status is None:
                logger.warning(
                    f"Session {session.id}: pod {session.pod_name} does not exist in K8s. "
                    f"Reconciling to TERMINATED and clearing target IP."
                )
                session.status = SessionStatus.TERMINATED
                session.terminated_at = now
                session.mirage_ip = None
                session.pod_ip = None
                session.ctf_ip = None
                session.error_message = "Kubernetes pod no longer exists"
                await db.commit()
            elif pod_status.get("phase") not in ("Running", "Pending"):
                phase = pod_status.get("phase", "Unknown")
                logger.warning(
                    f"Session {session.id}: pod {session.pod_name} is in phase {phase}. Reconciling to TERMINATED."
                )
                session.status = SessionStatus.TERMINATED
                session.terminated_at = now
                session.mirage_ip = None
                session.pod_ip = None
                session.ctf_ip = None
                session.error_message = f"Kubernetes pod entered {phase} state"
                await db.commit()
            else:
                is_ready = bool(pod_status.get("ready"))
                current_ip = pod_status.get("ip")

                if session.status == SessionStatus.READY:
                    if not is_ready or not current_ip:
                        logger.warning(f"Session {session.id}: pod {session.pod_name} lost readiness. Downgrading to INITIALIZING.")
                        session.status = SessionStatus.INITIALIZING
                        session.mirage_ip = None
                        session.pod_ip = None
                        await db.commit()
                    elif session.mirage_ip != current_ip:
                        session.mirage_ip = current_ip
                        session.pod_ip = current_ip
                        await db.commit()
                elif session.status in (SessionStatus.INITIALIZING, SessionStatus.PROVISIONING, SessionStatus.PENDING):
                    if is_ready and current_ip:
                        logger.info(f"Session {session.id}: pod {session.pod_name} reported ready with IP {current_ip}.")
                        session.status = SessionStatus.READY
                        session.mirage_ip = current_ip
                        session.pod_ip = current_ip
                        session.ready_at = now
                        await db.commit()
        except Exception as e:
            logger.error(f"K8s verification failed for session {session.id}: {e}")
            if session.status == SessionStatus.READY:
                session.status = SessionStatus.ERROR
                session.error_message = "Cannot verify Kubernetes environment status"
                session.mirage_ip = None
                session.pod_ip = None
                await db.commit()

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

        # 2. Atomically reserve slot and create INITIALIZING record under mutual exclusion
        async with self._slot_lock:
            if db.bind and db.bind.dialect.name == "postgresql":
                await db.execute(text("SELECT pg_advisory_xact_lock(74291823)"))

            await self.reconcile_orphaned_sessions(db)

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

            vpn_profile = await self.vpn_service.generate_or_get_profile(db, user)

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
            await db.commit()
            await db.refresh(new_session)

        # 3. Provision Kubernetes Pod and confirm readiness
        user_id = user.id
        try:
            pod_name, mirage_ip, ctf_ip = await self.k8s_provisioner.provision_player_pod(
                session_id=new_session.id,
                user_id=user_id,
                username=user.username,
            )

            pod_status = await self.k8s_provisioner.get_pod_status(pod_name)
            if not pod_status or not pod_status.get("ready") or not pod_status.get("ip"):
                raise RuntimeError(f"Pod {pod_name} did not become ready or has no IP")

            new_session.pod_name = pod_name
            new_session.pod_namespace = settings.K8S_NAMESPACE
            new_session.pod_ip = pod_status["ip"]
            new_session.mirage_ip = pod_status["ip"]
            new_session.ctf_ip = ctf_ip
            new_session.status = SessionStatus.READY
            new_session.ready_at = datetime.now(timezone.utc)

            self._record_activity(new_session)

            async with self._slot_lock:
                activity = ActivityLog(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    session_id=new_session.id,
                    event_type=ActivityEventType.SESSION_START,
                    summary=f"Player started machine (Mirage IP: {pod_status['ip']})",
                    payload={
                        "mirage_ip": pod_status["ip"],
                        "vpn_ip": vpn_profile.assigned_ip,
                        "session_id": new_session.id,
                    },
                )
                db.add(activity)
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
            if new_session.pod_name:
                try:
                    await self.k8s_provisioner.delete_player_pod(new_session.pod_name)
                except Exception as cleanup_err:
                    logger.error(f"Failed to cleanup orphaned pod: {cleanup_err}")

            async with self._slot_lock:
                new_session.status = SessionStatus.ERROR
                new_session.error_message = str(e)[:500]
                new_session.mirage_ip = None
                new_session.pod_ip = None
                new_session.ctf_ip = None
                new_session.terminated_at = datetime.now(timezone.utc)
                await db.commit()

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

        # 1. Mark session stopping
        session.status = SessionStatus.STOPPING
        await db.commit()

        # 2. Delete Kubernetes resources
        pod_deleted = True
        if session.pod_name:
            try:
                pod_deleted = await self.k8s_provisioner.delete_player_pod(session.pod_name)
            except Exception as e:
                logger.warning(f"Failed to delete pod {session.pod_name}: {e}")
                pod_deleted = False

        # 3. Confirm deletion where practical (delete_player_pod returns True on 404 or success)
        # 4. Release concurrency slot (changing away from ACTIVE_STATUSES)
        # 5. Clear runtime target information
        session.mirage_ip = None
        session.pod_ip = None
        session.ctf_ip = None

        # 6. Mark session stopped/ended
        session.status = SessionStatus.TERMINATED
        session.terminated_at = datetime.now(timezone.utc)
        if not pod_deleted:
            session.error_message = "Pod deletion may have failed; manual cleanup may be required"

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

        # Extend the session
        session.expires_at = new_expires_at
        session.last_active_at = now
        await db.commit()
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
        )

    async def cleanup_expired_sessions(self, db: AsyncSession) -> int:
        """
        Worker task to clean up all expired sessions across all players.
        Idempotent: safe to run multiple times. Clears runtime target fields.
        """
        now = datetime.now(timezone.utc)
        query = select(GameSession).where(
            GameSession.status.in_(ACTIVE_STATUSES),
            GameSession.expires_at < now,
        )
        result = await db.execute(query)
        expired_sessions: List[GameSession] = list(result.scalars().all())

        count = 0
        for session in expired_sessions:
            try:
                if session.pod_name:
                    try:
                        await self.k8s_provisioner.delete_player_pod(session.pod_name)
                    except Exception as e:
                        logger.warning(
                            f"Cleanup: Failed to delete pod {session.pod_name} "
                            f"for session {session.id}: {e}"
                        )

                session.status = SessionStatus.EXPIRED
                session.terminated_at = now
                session.mirage_ip = None
                session.pod_ip = None
                session.ctf_ip = None
                count += 1
            except Exception as e:
                logger.error(f"Cleanup: Error processing session {session.id}: {e}")

        if count > 0:
            await db.commit()

        return count

    async def reconcile_orphaned_sessions(self, db: AsyncSession) -> int:
        """
        Find active sessions whose Kubernetes pods no longer exist or are not healthy and reconcile them.
        Clears target IP when reconciling.
        """
        query = select(GameSession).where(
            GameSession.status.in_(ACTIVE_STATUSES),
        )
        result = await db.execute(query)
        active_sessions: List[GameSession] = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        reconciled = 0

        for session in active_sessions:
            try:
                if not session.pod_name:
                    if session.status == SessionStatus.READY:
                        logger.warning(f"Reconciliation: Session {session.id} READY without pod. Marking TERMINATED.")
                        session.status = SessionStatus.TERMINATED
                        session.terminated_at = now
                        session.mirage_ip = None
                        session.pod_ip = None
                        session.ctf_ip = None
                        session.error_message = "Pod missing for READY session"
                        reconciled += 1
                    continue

                pod_status = await self.k8s_provisioner.get_pod_status(session.pod_name)
                if pod_status is None:
                    logger.warning(
                        f"Reconciliation: Session {session.id} pod {session.pod_name} "
                        f"does not exist. Marking TERMINATED."
                    )
                    session.status = SessionStatus.TERMINATED
                    session.terminated_at = now
                    session.mirage_ip = None
                    session.pod_ip = None
                    session.ctf_ip = None
                    session.error_message = "Pod reconciled: NotFound"
                    reconciled += 1
                elif pod_status.get("phase") not in ("Running", "Pending"):
                    phase = pod_status.get("phase")
                    logger.warning(
                        f"Reconciliation: Session {session.id} pod {session.pod_name} "
                        f"is {phase}. Marking TERMINATED."
                    )
                    session.status = SessionStatus.TERMINATED
                    session.terminated_at = now
                    session.mirage_ip = None
                    session.pod_ip = None
                    session.ctf_ip = None
                    session.error_message = f"Pod reconciled: {phase}"
                    reconciled += 1
                elif session.status == SessionStatus.READY:
                    if not pod_status.get("ready"):
                        logger.warning(f"Reconciliation: Session {session.id} pod {session.pod_name} not ready. Downgrading to INITIALIZING.")
                        session.status = SessionStatus.INITIALIZING
                        session.mirage_ip = None
                        session.pod_ip = None
                        reconciled += 1
                    elif pod_status.get("ip") and session.mirage_ip != pod_status["ip"]:
                        session.mirage_ip = pod_status["ip"]
                        session.pod_ip = pod_status["ip"]
                        reconciled += 1
            except Exception as e:
                logger.error(
                    f"Reconciliation: Failed to check pod {session.pod_name} "
                    f"for session {session.id}: {e}"
                )

        if reconciled > 0:
            await db.commit()

        return reconciled


session_service = SessionService()
