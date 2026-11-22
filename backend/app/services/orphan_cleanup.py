"""Reconcile actual resources even when their session database row is gone."""
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import logging
import re

from sqlalchemy import select, text

from backend.app.core.config import settings
from backend.app.models.session import GameSession, SessionStatus
from backend.app.models.user import User
from backend.app.services.session_service import ACTIVE_STATUSES, _to_utc, mark_session_stopping, session_service
from backend.app.services.vpn_access import vpn_access_revoked

logger = logging.getLogger("mirrage.orphan_cleanup")


class OrphanCleanupService:
    def __init__(self, sessions=None):
        self.sessions = sessions or session_service
        self._lock = asyncio.Lock()

    async def sweep(self, db):
        async with self._lock:
            k8s, gateway = self.sessions.k8s_provisioner, self.sessions.gateway
            # Both inventories must succeed completely before any mutation. An
            # unavailable dependency is never interpreted as an empty inventory.
            inventory = await k8s.list_session_resources()
            bindings = await gateway.inventory()
            if not isinstance(bindings, dict) or any(
                not re.fullmatch(r"[a-z0-9-]{1,100}", key) or not isinstance(value, dict)
                or set(value) != {"vpn_ip", "pod_ip", "expires_at"}
                for key, value in bindings.items()
            ):
                raise RuntimeError("Invalid gateway inventory")
            grouped = defaultdict(list)
            for resource in inventory.resources:
                grouped[resource.session_id].append(resource)
            result = dict(cleaned=0, preserved=0, pending=0, ignored=inventory.ignored)
            for session_id in sorted(set(grouped) | set(bindings)):
                session = None
                try:
                    # Same transaction lock used to insert session/slot records:
                    # a missing row cannot race a newly committed start. Existing
                    # rows stay locked against extension until deletion completes.
                    if db.bind.dialect.name == "postgresql":
                        await db.execute(text("SELECT pg_advisory_xact_lock(74291823)"))
                    session = (await db.execute(select(GameSession).where(
                        GameSession.id == session_id
                    ).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
                    resources = grouped[session_id]
                    owners = {resource.user_id for resource in resources}
                    if len(owners) > 1 or (session and owners and owners != {session.user_id}):
                        raise RuntimeError("Resource ownership is ambiguous")
                    now = datetime.now(timezone.utc)
                    if session:
                        owner = await db.get(User, session.user_id)
                        initializing = session.status in (SessionStatus.PENDING, SessionStatus.INITIALIZING,
                                                          SessionStatus.PROVISIONING) and session.ready_at is None
                        valid = (session.status in ACTIVE_STATUSES and session.status != SessionStatus.STOPPING
                                 and _to_utc(session.expires_at) > now and owner is not None and owner.is_active
                                 and not await vpn_access_revoked(db, session.user_id)
                                 and (not initializing or _to_utc(session.created_at) + timedelta(minutes=3) > now))
                        if valid:
                            result["preserved"] += 1
                            await db.commit()
                            continue
                        final = (session.status if session.status not in ACTIVE_STATUSES else
                                 SessionStatus.EXPIRED if _to_utc(session.expires_at) <= now else SessionStatus.TERMINATED)
                        mark_session_stopping(session, now)
                        session.mirage_ip = session.ctf_ip = session.pod_ip = None
                        # Persist the cleanup barrier before external effects so
                        # cancellation/restart cannot make a partially cleaned
                        # environment eligible for a new grant.
                        await db.commit()
                        if db.bind.dialect.name == "postgresql":
                            await db.execute(text("SELECT pg_advisory_xact_lock(74291823)"))
                        await db.refresh(session, with_for_update=True)
                        if session.status != SessionStatus.STOPPING:
                            raise RuntimeError("Session changed during cleanup")
                    await gateway.revoke(session_id)
                    # Never remove a policy/source block while its pod survives.
                    for resource in sorted(resources, key=lambda item: item.kind != "Pod"):
                        if not await k8s.delete_session_resource(resource):
                            raise RuntimeError("Resource deletion is not confirmed")
                    # Fresh complete read covers stale snapshots, terminating
                    # pods, and replacements after a successful delete request.
                    remaining = await k8s.list_session_resources()
                    # A grant may have completed after our initial inventory and
                    # before its DB row was removed. Inspect the current binding
                    # before releasing its source block.
                    binding = (await gateway.inventory()).get(session_id)
                    if (any(item.session_id == session_id for item in remaining.resources)
                            or (binding and binding["pod_ip"] in remaining.occupied_ips)):
                        raise RuntimeError("Resources still exist; retain the source block")
                    await gateway.forget(session_id)
                    if session:
                        session.status = final
                        session.terminated_at = session.terminated_at or now
                        session.error_message = None
                    await db.commit()
                    result["cleaned"] += 1
                except Exception:
                    await db.rollback()
                    # Kubernetes objects/root state are the durable retry ledger;
                    # do not depend on recreating a missing database row.
                    result["pending"] += 1
                    logger.warning("Orphan cleanup pending for session %s; rescan scheduled", session_id)
            if result["cleaned"] or result["pending"] or result["ignored"]:
                logger.info("Resource sweep: %s", result)
            return result


orphan_cleanup_service = OrphanCleanupService()
