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

    async def get_active_session_for_user(
        self, db: AsyncSession, user_id: str
    ) -> Optional[GameSession]:
        """Fetch currently active session for the given user, if any."""
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

        # Check for inline expiration
        if session:
            now = datetime.now(timezone.utc)
            if _to_utc(session.expires_at) < now:
                session.status = SessionStatus.EXPIRED
                session.terminated_at = now
                await db.commit()
                # Clean up pod (best-effort)
                if session.pod_name:
                    try:
                        await self.k8s_provisioner.delete_player_pod(session.pod_name)
                    except Exception as e:
                        logger.warning(f"Failed to delete expired pod {session.pod_name}: {e}")
                return None

        return session

    def _extend_session_expiry(self, session: GameSession) -> None:
        """
        Extend session expiry on meaningful activity.

        This implements the TRUE inactivity timeout: each meaningful action
        resets the 30-minute countdown from the current time.
        """
        now = datetime.now(timezone.utc)
        session.last_active_at = now
        session.expires_at = now + timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)

    async def start_session(
        self,
        db: AsyncSession,
        user: User,
        request: Optional[SessionStartRequest] = None,
    ) -> SessionResponse:
        """
        Start machine:
        1. Atomically check active slots (< 3) and user uniqueness
        2. Provision Pod (Mirage + CTF)
        3. Obtain Mirage endpoint (10.42.0.x)
        4. Return session details
        """
        # 1. Check for existing active session (fast path before locking)
        existing_session = await self.get_active_session_for_user(db, user.id)
        if existing_session:
            if existing_session.status == SessionStatus.READY:
                # Verify the pod still exists before returning the session as active
                if existing_session.pod_name:
                    try:
                        pod_status = await self.k8s_provisioner.get_pod_status(existing_session.pod_name)
                        if pod_status is None or pod_status.get("phase") not in ("Running", "Pending"):
                            # Pod is gone — terminate the stale session and allow a new start
                            logger.warning(
                                f"Existing session {existing_session.id}: pod {existing_session.pod_name} "
                                f"no longer exists. Terminating stale session."
                            )
                            existing_session.status = SessionStatus.TERMINATED
                            existing_session.terminated_at = datetime.now(timezone.utc)
                            existing_session.error_message = "Pod no longer exists"
                            await db.commit()
                            # Fall through to create a new session
                            existing_session = None
                        else:
                            return SessionResponse(
                                session_id=existing_session.id,
                                mirage_ip=existing_session.mirage_ip,
                                status=existing_session.status,
                                mirage_port=existing_session.mirage_port,
                                player_vpn_ip=existing_session.player_vpn_ip,
                                expires_at=existing_session.expires_at,
                                time_remaining_seconds=_time_remaining(existing_session.expires_at),
                                message="Active session restored",
                            )
                    except Exception as e:
                        logger.error(f"Failed to verify pod for existing session: {e}")
                        # Can't verify — return the existing session but don't claim it's definitively ready
                        return SessionResponse(
                            session_id=existing_session.id,
                            mirage_ip=existing_session.mirage_ip,
                            status=existing_session.status,
                            mirage_port=existing_session.mirage_port,
                            player_vpn_ip=existing_session.player_vpn_ip,
                            expires_at=existing_session.expires_at,
                            time_remaining_seconds=_time_remaining(existing_session.expires_at),
                            message="Active session restored (pod verification unavailable)",
                        )
                else:
                    return SessionResponse(
                        session_id=existing_session.id,
                        mirage_ip=existing_session.mirage_ip,
                        status=existing_session.status,
                        mirage_port=existing_session.mirage_port,
                        player_vpn_ip=existing_session.player_vpn_ip,
                        expires_at=existing_session.expires_at,
                        time_remaining_seconds=_time_remaining(existing_session.expires_at),
                        message="Active session restored",
                    )
            if existing_session:  # Guard: may have been set to None above after termination
                raise ActiveSessionExistsError(existing_session.id)

        # 2. Atomically reserve slot and create INITIALIZING record under mutual exclusion
        async with self._slot_lock:
            # Multi-process PostgreSQL advisory lock if PostgreSQL is the database engine
            if db.bind and db.bind.dialect.name == "postgresql":
                await db.execute(text("SELECT pg_advisory_xact_lock(74291823)"))

            # Re-check active slots inside the lock
            count_query = select(func.count(GameSession.id)).where(
                GameSession.status.in_(ACTIVE_STATUSES)
            )
            result = await db.execute(count_query)
            active_count = result.scalar() or 0

            if active_count >= settings.MAX_CONCURRENT_SESSIONS:
                raise SlotLimitExceededError(settings.MAX_CONCURRENT_SESSIONS)

            # Re-check user doesn't already have an active session inside the lock
            user_query = select(GameSession).where(
                GameSession.user_id == user.id,
                GameSession.status.in_(ACTIVE_STATUSES),
            )
            user_result = await db.execute(user_query)
            existing = user_result.scalars().first()
            if existing:
                raise ActiveSessionExistsError(existing.id)

            # Retrieve or generate user VPN profile
            vpn_profile = await self.vpn_service.generate_or_get_profile(db, user)

            # Create session record in INITIALIZING status (consumes slot immediately)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)

            new_session = GameSession(
                user_id=user.id,
                status=SessionStatus.INITIALIZING,
                player_vpn_ip=vpn_profile.assigned_ip,
                mirage_port=22,
                ctf_port=2222,
                created_at=now,
                expires_at=expires_at,
                last_active_at=now,
            )
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)

        # 5. Provision Kubernetes Pod
        try:
            pod_name, mirage_ip, ctf_ip = await self.k8s_provisioner.provision_player_pod(
                session_id=new_session.id,
                user_id=user.id,
                username=user.username,
            )

            new_session.pod_name = pod_name
            new_session.pod_namespace = settings.K8S_NAMESPACE
            new_session.pod_ip = mirage_ip
            new_session.mirage_ip = mirage_ip
            new_session.ctf_ip = ctf_ip
            new_session.status = SessionStatus.READY
            new_session.ready_at = datetime.now(timezone.utc)

            # Record activity log (this is a meaningful action)
            self._extend_session_expiry(new_session)

            activity = ActivityLog(
                user_id=user.id,
                session_id=new_session.id,
                event_type=ActivityEventType.SESSION_START,
                summary=f"Player started machine (Mirage IP: {mirage_ip})",
                payload={
                    "mirage_ip": mirage_ip,
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
                player_vpn_ip=new_session.player_vpn_ip,
                expires_at=new_session.expires_at,
                time_remaining_seconds=_time_remaining(new_session.expires_at),
                message="Mirage environment initialized successfully",
            )

        except Exception as e:
            # Clean up orphaned pod if it was partially created
            if new_session.pod_name:
                try:
                    await self.k8s_provisioner.delete_player_pod(new_session.pod_name)
                except Exception as cleanup_err:
                    logger.error(f"Failed to cleanup orphaned pod: {cleanup_err}")

            # Release the slot by marking session as ERROR
            new_session.status = SessionStatus.ERROR
            new_session.error_message = str(e)[:500]  # Truncate for safety
            new_session.terminated_at = datetime.now(timezone.utc)
            await db.commit()

            logger.error(f"Session provisioning failed for user {user.id}: {e}")
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

        IMPORTANT: Status polling (is_activity=False) does NOT extend the
        session lifetime. Only meaningful player actions extend it.
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
                # Get last session if any
                last_query = (
                    select(GameSession)
                    .where(GameSession.user_id == user.id)
                    .order_by(GameSession.created_at.desc())
                )
                last_res = await db.execute(last_query)
                session = last_res.scalars().first()
                if not session:
                    raise EntityNotFoundError("Active Session for User", user.username)

        # ── K8s Pod Reconciliation ──
        # If the session is supposedly active with a pod, verify the pod still exists.
        # This prevents stale "READY" states when the pod has been deleted externally.
        if session.is_active and session.pod_name:
            try:
                pod_status = await self.k8s_provisioner.get_pod_status(session.pod_name)
                if pod_status is None:
                    # Pod has vanished — reconcile DB state
                    logger.warning(
                        f"Session {session.id}: pod {session.pod_name} no longer exists. "
                        f"Reconciling session state from {session.status} to TERMINATED."
                    )
                    session.status = SessionStatus.TERMINATED
                    session.terminated_at = datetime.now(timezone.utc)
                    session.error_message = "Environment pod was terminated externally"
                    await db.commit()
                elif pod_status.get("phase") not in ("Running", "Pending"):
                    # Pod exists but is in a terminal state (Failed, Succeeded, Unknown)
                    logger.warning(
                        f"Session {session.id}: pod {session.pod_name} is in phase "
                        f"{pod_status.get('phase')}. Reconciling to TERMINATED."
                    )
                    session.status = SessionStatus.TERMINATED
                    session.terminated_at = datetime.now(timezone.utc)
                    session.error_message = f"Environment pod entered {pod_status.get('phase')} state"
                    await db.commit()
            except Exception as e:
                # K8s API unavailable — fail closed: do NOT report ready if we can't verify
                logger.error(f"Session {session.id}: K8s verification failed: {e}")
                # If K8s is unreachable, mark session as failed rather than displaying stale READY
                session.status = SessionStatus.ERROR
                session.error_message = "Cannot verify environment status"
                await db.commit()

        # Compute remaining seconds
        time_rem = _time_remaining(session.expires_at) if session.is_active else 0

        # Only extend session lifetime on meaningful activity, NOT on polling
        if session.is_active and is_activity:
            self._extend_session_expiry(session)
            await db.commit()

        return SessionStatusResponse(
            session_id=session.id,
            status=session.status,
            mirage_ip=session.mirage_ip,
            mirage_port=session.mirage_port,
            player_vpn_ip=session.player_vpn_ip,
            created_at=session.created_at,
            ready_at=session.ready_at,
            expires_at=session.expires_at,
            last_active_at=session.last_active_at,
            time_remaining_seconds=time_rem,
            is_ready=session.status == SessionStatus.READY,
        )

    async def record_activity(
        self, db: AsyncSession, session: GameSession
    ) -> None:
        """
        Record meaningful player activity and extend session lifetime.

        Call this from endpoints that represent actual player actions:
        - Flag submission
        - SSH/VPN connection events
        - Challenge interactions

        Do NOT call this from status polling endpoints.
        """
        if session.is_active:
            self._extend_session_expiry(session)
            await db.commit()

    async def record_activity_for_user(
        self, db: AsyncSession, user_id: str
    ) -> None:
        """Find user's active session and record meaningful activity extending lifetime."""
        session = await self.get_active_session_for_user(db, user_id)
        if session and session.is_active:
            self._extend_session_expiry(session)
            await db.commit()

    async def stop_session(
        self,
        db: AsyncSession,
        user: User,
        session_id: Optional[str] = None,
    ) -> SessionResponse:
        """Stop and terminate an active session."""
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
                message="Session already stopped",
            )

        # Delete Pod (best-effort, log failures)
        pod_deleted = True
        if session.pod_name:
            try:
                pod_deleted = await self.k8s_provisioner.delete_player_pod(session.pod_name)
            except Exception as e:
                logger.warning(f"Failed to delete pod {session.pod_name}: {e}")
                pod_deleted = False

        session.status = SessionStatus.TERMINATED
        session.terminated_at = datetime.now(timezone.utc)

        if not pod_deleted:
            session.error_message = "Pod deletion may have failed; manual cleanup may be required"

        # Log event
        activity = ActivityLog(
            user_id=user.id,
            session_id=session.id,
            event_type=ActivityEventType.SESSION_STOP,
            summary=f"Player stopped machine (Session: {session.id})",
        )
        db.add(activity)
        await db.commit()

        return SessionResponse(
            session_id=session.id,
            status=session.status,
            message="Session terminated successfully",
        )

    async def cleanup_expired_sessions(self, db: AsyncSession) -> int:
        """
        Worker task to clean up all expired sessions across all players.
        Idempotent: safe to run multiple times. Handles partial failures.
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
                # Best-effort pod deletion
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
                count += 1
            except Exception as e:
                logger.error(f"Cleanup: Error processing session {session.id}: {e}")

        if count > 0:
            await db.commit()

        return count

    async def reconcile_orphaned_sessions(self, db: AsyncSession) -> int:
        """
        Find active sessions whose Kubernetes pods no longer exist and terminate them.
        This catches pods that were deleted externally (manual cleanup, node failure, etc.)
        without going through the normal stop flow.
        """
        query = select(GameSession).where(
            GameSession.status.in_(ACTIVE_STATUSES),
            GameSession.pod_name.isnot(None),
        )
        result = await db.execute(query)
        active_sessions: List[GameSession] = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        reconciled = 0

        for session in active_sessions:
            try:
                pod_status = await self.k8s_provisioner.get_pod_status(session.pod_name)
                if pod_status is None or pod_status.get("phase") not in ("Running", "Pending"):
                    phase = pod_status.get("phase") if pod_status else "NotFound"
                    logger.warning(
                        f"Reconciliation: Session {session.id} pod {session.pod_name} "
                        f"is {phase}. Marking TERMINATED."
                    )
                    session.status = SessionStatus.TERMINATED
                    session.terminated_at = now
                    session.error_message = f"Pod reconciled: {phase}"
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
