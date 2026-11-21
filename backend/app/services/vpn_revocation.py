"""Durable VPN deny/retry workflow; requests never claim external success early."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import re
import uuid

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.app.core.config import settings
from backend.app.core.exceptions import EntityNotFoundError
from backend.app.models.activity import ActivityEventType, ActivityLog
from backend.app.models.session import GameSession, SessionStatus
from backend.app.models.user import User
from backend.app.models.vpn import VpnCrlMaintenance, VpnProfile, VpnRevocation

logger = logging.getLogger("mirrage.vpn.revocation")


def insert(db, model):
    return (pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert)(model)


def now():
    return datetime.now(timezone.utc)


class VPNRevocationService:
    def __init__(self):
        self._request_lock = asyncio.Lock()

    async def request(self, db, user_id, actor_id):
        async with self._request_lock:
            target = (await db.execute(select(User.id).where(User.id == user_id).with_for_update())).scalar_one_or_none()
            if target is None:
                raise EntityNotFoundError("User", user_id)
            profile = (await db.execute(select(VpnProfile).where(
                VpnProfile.user_id == user_id
            ).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
            if profile is None:
                raise EntityNotFoundError("VPN profile for user", user_id)
            timestamp = now()
            section = re.search(r"<cert>(.*?)</cert>", profile.config_data, re.DOTALL)
            public = re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
                               section.group(1), re.DOTALL) if section else None
            profile.revoked_at = profile.revoked_at or timestamp
            profile.is_connected = False
            profile.connected_since = None
            profile.config_data = ""  # No downloadable private bundle remains in this row.
            result = await db.execute(insert(db, VpnRevocation).values(
                client_name=profile.client_name, user_id=user_id, requested_by=actor_id,
                requested_at=timestamp, next_attempt_at=timestamp, attempts=0,
                certificate_pem=public.group(0) if public else None,
            ).on_conflict_do_nothing(index_elements=["client_name"]).returning(VpnRevocation.client_name))
            if result.scalar_one_or_none() is not None:
                db.add(ActivityLog(
                    user_id=user_id, event_type=ActivityEventType.VPN_DISCONNECT,
                    summary="Administrator requested VPN revocation",
                    payload={"action": "vpn_revocation_requested", "administrator_id": actor_id},
                ))
            await db.commit()  # Permanent deny is durable before any external operation.
            return await self.get(db, user_id)

    async def get(self, db, user_id):
        job = (await db.execute(select(VpnRevocation).where(VpnRevocation.user_id == user_id)
                               .order_by(VpnRevocation.requested_at.desc()).limit(1)
                               .execution_options(populate_existing=True))).scalar_one_or_none()
        if job is None:
            raise EntityNotFoundError("VPN revocation for user", user_id)
        return job

    async def close_sessions(self, db, user_id):
        from backend.app.services.session_service import ACTIVE_STATUSES, session_service
        sessions = (await db.execute(select(GameSession).where(
            GameSession.user_id == user_id, GameSession.status.in_(ACTIVE_STATUSES)
        ))).scalars().all()
        closed = True
        for session in sessions:
            if not await session_service._end_session(db, session, SessionStatus.TERMINATED):
                closed = False
        return closed

    async def process_one(self, db, client_name):
        timestamp, token = now(), str(uuid.uuid4())
        claimed = (await db.execute(update(VpnRevocation).execution_options(synchronize_session="fetch").where(
            VpnRevocation.client_name == client_name, VpnRevocation.completed_at.is_(None),
            VpnRevocation.next_attempt_at <= timestamp,
            or_(VpnRevocation.claimed_until.is_(None), VpnRevocation.claimed_until <= timestamp),
        ).values(claim_token=token, claimed_until=timestamp + timedelta(seconds=max(300, 4 * settings.VPN_PKI_TIMEOUT_SECONDS + 120)),
                 attempts=VpnRevocation.attempts + 1).returning(VpnRevocation.user_id))).scalar_one_or_none()
        await db.commit()
        if claimed is None:
            return False
        certificate = (await db.execute(select(VpnRevocation.certificate_pem).where(
            VpnRevocation.client_name == client_name
        ))).scalar_one()
        error = None
        try:
            try:
                if not await self.close_sessions(db, claimed):
                    error = "SESSION_CLEANUP_PENDING"
            except Exception:
                await db.rollback()
                error = "SESSION_CLEANUP_PENDING"
            if settings.VPN_MODE == "production":
                from backend.app.services.vpn_control import vpn_control
                from backend.app.services.vpn_provisioner import revoke_client_certificate
                stage = "VPN_BLOCK_FAILED"
                try:
                    # Cache the public certificate before Easy-RSA can move it.
                    await vpn_control.block(client_name, certificate)
                    stage = "PKI_REVOKE_FAILED"
                    await revoke_client_certificate(client_name)
                    stage = "CRL_PUBLISH_FAILED"
                    await vpn_control.publish(client_name)
                    stage = "VPN_DISCONNECT_FAILED"
                    await vpn_control.block(client_name, certificate)  # Close a reconnect racing CRL publication.
                except Exception:
                    error = stage
            finished = now()
            await db.execute(update(VpnRevocation).execution_options(synchronize_session="fetch").where(
                VpnRevocation.client_name == client_name, VpnRevocation.claim_token == token
            ).values(
                completed_at=finished if error is None else None,
                next_attempt_at=finished + timedelta(seconds=settings.VPN_REVOCATION_RETRY_SECONDS),
                claimed_until=None, claim_token=None, last_error=error,
            ))
            await db.commit()
            if error:
                logger.warning("VPN revocation pending for user %s (%s)", claimed, error)
            return error is None
        except Exception:
            # An interrupted/failed state update leaves a claim that another worker
            # can reclaim after its deadline. Never undo the permanent deny.
            await db.rollback()
            logger.error("VPN revocation worker failed; durable retry retained")
            return False

    async def process_pending(self, db):
        timestamp = now()
        clients = (await db.execute(select(VpnRevocation.client_name).where(
            VpnRevocation.completed_at.is_(None), VpnRevocation.next_attempt_at <= timestamp,
            or_(VpnRevocation.claimed_until.is_(None), VpnRevocation.claimed_until <= timestamp),
        ).order_by(VpnRevocation.requested_at).limit(20))).scalars().all()
        for client in clients:
            await self.process_one(db, client)

    async def run_background(self, client_name):
        from backend.app.core.database import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as db:
                await self.process_one(db, client_name)
        except Exception:
            logger.error("Immediate VPN revocation attempt failed; periodic worker will retry")

    async def maintain_crl(self, db):
        if settings.VPN_MODE != "production":
            return
        from backend.app.services.vpn_control import vpn_control
        from backend.app.services.vpn_provisioner import refresh_certificate_revocation_list
        timestamp, token = now(), str(uuid.uuid4())
        await db.execute(insert(db, VpnCrlMaintenance).values(id=1, next_check_at=timestamp)
                         .on_conflict_do_nothing(index_elements=["id"]))
        claimed = (await db.execute(update(VpnCrlMaintenance).execution_options(synchronize_session="fetch").where(
            VpnCrlMaintenance.id == 1, VpnCrlMaintenance.next_check_at <= timestamp,
            or_(VpnCrlMaintenance.claimed_until.is_(None), VpnCrlMaintenance.claimed_until <= timestamp),
        ).values(claim_token=token, claimed_until=timestamp + timedelta(seconds=max(300, 4 * settings.VPN_PKI_TIMEOUT_SECONDS + 120)))
            .returning(VpnCrlMaintenance.id))).scalar_one_or_none()
        await db.commit()
        if claimed is None:
            return
        expiry, error = None, None
        try:
            try:
                health = await vpn_control.health()
                expiry = datetime.fromtimestamp(health["expires_at"], timezone.utc)
            except Exception:
                pass  # Missing/expired CRL can be repaired using the authoritative PKI.
            if expiry is None or expiry <= timestamp + timedelta(seconds=settings.VPN_CRL_REFRESH_MARGIN_SECONDS):
                await refresh_certificate_revocation_list()
                health = await vpn_control.refresh()
                expiry = datetime.fromtimestamp(health["expires_at"], timezone.utc)
                if expiry <= now() + timedelta(seconds=settings.VPN_CRL_REFRESH_MARGIN_SECONDS):
                    raise RuntimeError("Refreshed CRL is still near expiry")
        except Exception:
            error = "CRL_MAINTENANCE_FAILED"
            logger.error("CRL refresh/health check failed; operator attention required")
        await db.execute(update(VpnCrlMaintenance).execution_options(synchronize_session="fetch").where(
            VpnCrlMaintenance.id == 1, VpnCrlMaintenance.claim_token == token,
        ).values(
            checked_at=now(), expires_at=expiry, last_error=error, claim_token=None, claimed_until=None,
            next_check_at=now() + timedelta(seconds=(settings.VPN_REVOCATION_RETRY_SECONDS if error
                                                     else settings.VPN_CRL_CHECK_INTERVAL_SECONDS)),
        ))
        await db.commit()


vpn_revocation_service = VPNRevocationService()
