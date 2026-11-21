"""Real separate transactions/services, rather than concurrent use of one session."""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
from importlib import import_module
import itertools
import os
from unittest.mock import AsyncMock
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.core.exceptions import AuthenticationError, MirrageException
from backend.app.models.otp import OtpCode
from backend.app.models.user import User
from backend.app.schemas.otp import OtpTokenResponse
from backend.app.services.auth_service import AuthService, _code_hash

auth_module = import_module("backend.app.services.auth_service")


@pytest_asyncio.fixture(params=["sqlite", "postgresql"])
async def otp_db(request, tmp_path, monkeypatch):
    if request.param == "postgresql":
        url = os.environ.get("MIRRAGE_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("Requires disposable PostgreSQL")
    else:
        url = f"sqlite+aiosqlite:///{tmp_path / 'otp.db'}"
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    sent = []
    async def send(email, code):
        sent.append((email, code))
    monkeypatch.setattr(auth_module.email_service, "send_otp", send)
    provision = AsyncMock()
    monkeypatch.setattr(auth_module.vpn_service, "generate_or_get_profile", provision)
    sequence = itertools.count(123400)
    monkeypatch.setattr(auth_module.secrets, "randbelow", lambda bound: next(sequence))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield sessions, uuid.uuid4().hex + "@example.com", sent, provision, request.param
    await engine.dispose()


async def issue(context, resend=False):
    sessions, email, sent, *_ = context
    async with sessions() as db:
        service = AuthService()
        result = await (service.resend_otp(db, email) if resend else service.request_otp(db, email))
    return sent[-1][1], result


async def verify(context, code, service=None):
    sessions, email, *_ = context
    async with sessions() as db:
        try:
            return await (service or AuthService()).verify_otp(db, email, code)
        except AuthenticationError as error:
            return error


async def rows(context):
    sessions, email, *_ = context
    async with sessions() as db:
        return list((await db.execute(select(OtpCode).where(OtpCode.email == email)
                                     .order_by(OtpCode.created_at, OtpCode.id))).scalars())


@pytest.mark.asyncio
async def test_same_code_has_exactly_one_winner_and_one_account(otp_db):
    code, _ = await issue(otp_db)
    results = await asyncio.gather(*(verify(otp_db, code) for _ in range(8)))
    winners = [result for result in results if isinstance(result, OtpTokenResponse)]
    assert len(winners) == 1 and sum(isinstance(result, AuthenticationError) for result in results) == 7
    sessions, email, _, provision, _ = otp_db
    async with sessions() as db:
        assert (await db.execute(select(func.count()).select_from(User).where(User.email == email))).scalar_one() == 1
    record, = await rows(otp_db)
    assert record.is_used and record.attempts == 1 and record.user_id == winners[0].user.id
    provision.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_bad_guesses_count_and_last_allowed_correct_guess_succeeds(otp_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_MAX_ATTEMPTS", 5)
    code, _ = await issue(otp_db)
    assert all(isinstance(result, AuthenticationError) for result in
               await asyncio.gather(*(verify(otp_db, "999999") for _ in range(4))))
    record, = await rows(otp_db)
    assert record.attempts == 4 and not record.is_used
    assert isinstance(await verify(otp_db, code), OtpTokenResponse)
    record, = await rows(otp_db)
    assert record.attempts == 5 and record.is_used


@pytest.mark.asyncio
async def test_exhausted_code_is_closed_immediately_without_attempt_overflow(otp_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_MAX_ATTEMPTS", 3)
    code, _ = await issue(otp_db)
    results = await asyncio.gather(*(verify(otp_db, "999999") for _ in range(8)))
    assert all(isinstance(result, AuthenticationError) for result in results)
    record, = await rows(otp_db)
    assert record.attempts == 3 and record.is_used
    assert isinstance(await verify(otp_db, code), AuthenticationError)
    otp_db[3].assert_not_awaited()


@pytest.mark.asyncio
async def test_correct_and_incorrect_guess_compete_for_one_remaining_attempt(otp_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_MAX_ATTEMPTS", 1)
    code, _ = await issue(otp_db)
    results = await asyncio.gather(verify(otp_db, "999999"), verify(otp_db, code))
    assert sum(isinstance(result, OtpTokenResponse) for result in results) <= 1
    record, = await rows(otp_db)
    assert record.attempts == 1 and record.is_used
    assert isinstance(await verify(otp_db, code), AuthenticationError)


@pytest.mark.asyncio
async def test_resend_invalidates_old_code_even_with_cached_old_row(otp_db):
    sessions, email, *_ = otp_db
    old, _ = await issue(otp_db)
    async with sessions() as stale:
        cached = (await stale.execute(select(OtpCode).where(OtpCode.email == email))).scalar_one()
        new, _ = await issue(otp_db, resend=True)
        assert old != new and not cached.is_used
        with pytest.raises(AuthenticationError):
            await AuthService().verify_otp(stale, "  " + email.upper() + "  ", old)
    assert isinstance(await verify(otp_db, new), OtpTokenResponse)
    records = await rows(otp_db)
    assert len(records) == 2 and all(record.is_used for record in records)


@pytest.mark.asyncio
async def test_parallel_requests_cannot_exceed_window_budget(otp_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(settings, "OTP_MAX_REQUESTS_PER_WINDOW", 3)
    results = await asyncio.gather(*(issue(otp_db) for _ in range(8)), return_exceptions=True)
    assert sum(isinstance(result, tuple) for result in results) == 3
    errors = [result for result in results if isinstance(result, MirrageException)]
    assert len(errors) == 5 and all(error.code == "OTP_RATE_LIMIT" for error in errors)
    assert all(int(error.headers["Retry-After"]) > 0 for error in errors)
    records = await rows(otp_db)
    assert len(records) == len(otp_db[2]) == 3 and sum(not record.is_used for record in records) == 1


@pytest.mark.asyncio
async def test_parallel_resends_share_one_immediate_allowance(otp_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)
    await issue(otp_db)
    results = await asyncio.gather(*(issue(otp_db, resend=True) for _ in range(6)), return_exceptions=True)
    assert sum(isinstance(result, tuple) for result in results) == 1
    errors = [result for result in results if isinstance(result, MirrageException)]
    assert len(errors) == 5 and all(error.code == "OTP_COOLDOWN" for error in errors)
    assert all(0 < int(error.headers["Retry-After"]) <= 60 for error in errors)
    assert len(otp_db[2]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("winner", ["verify", "resend"])
async def test_postgres_verify_and_resend_share_the_same_lock(otp_db, monkeypatch, winner):
    if otp_db[4] != "postgresql":
        pytest.skip("Tests PostgreSQL cross-worker lock ordering")
    monkeypatch.setattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0)
    old, _ = await issue(otp_db)
    entered, release, contender_started = asyncio.Event(), asyncio.Event(), asyncio.Event()
    sessions, email, *_ = otp_db
    class PausedService(AuthService):
        async def _consume_otp(self, *args, **kwargs):
            if winner == "verify":
                entered.set()
                await release.wait()
            return await super()._consume_otp(*args, **kwargs)
        async def _issue_otp(self, *args, **kwargs):
            if winner == "resend":
                entered.set()
                await release.wait()
            return await super()._issue_otp(*args, **kwargs)
    async def resend(service, contender=False):
        async with sessions() as db:
            if contender:
                contender_started.set()
            return await service.resend_otp(db, email)
    async def competing_verify():
        contender_started.set()
        return await verify(otp_db, old)
    first = asyncio.create_task(verify(otp_db, old, PausedService()) if winner == "verify"
                                else resend(PausedService()))
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 5)
        second = asyncio.create_task(resend(AuthService(), True) if winner == "verify" else competing_verify())
        await asyncio.wait_for(contender_started.wait(), 5)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(second), 0.05)
    finally:
        release.set()
        results = await asyncio.gather(first, *([second] if second else []))
    outcome = results[0] if winner == "verify" else results[1]
    assert isinstance(outcome, OtpTokenResponse if winner == "verify" else AuthenticationError)
    new = otp_db[2][-1][1]
    assert old != new and isinstance(await verify(otp_db, old), AuthenticationError)
    assert isinstance(await verify(otp_db, new), OtpTokenResponse)


@pytest.mark.asyncio
async def test_disabled_account_cannot_reuse_code_after_reactivation(otp_db):
    sessions, email, *_ = otp_db
    async with sessions() as db:
        user = User(email=email, username=uuid.uuid4().hex, is_active=False)
        db.add(user)
        await db.commit()
        user_id = user.id
    code, _ = await issue(otp_db)
    assert isinstance(await verify(otp_db, code), AuthenticationError)
    record, = await rows(otp_db)
    assert record.is_used and record.attempts == 1
    async with sessions() as db:
        user = await db.get(User, user_id)
        user.is_active = True
        await db.commit()
    assert isinstance(await verify(otp_db, code), AuthenticationError)


@pytest.mark.asyncio
async def test_vpn_failure_cannot_undo_consumption_or_duplicate_account(otp_db):
    code, _ = await issue(otp_db)
    otp_db[3].side_effect = RuntimeError("simulated provisioning failure")
    with pytest.raises(RuntimeError, match="simulated"):
        await verify(otp_db, code)
    assert isinstance(await verify(otp_db, code), AuthenticationError)
    record, = await rows(otp_db)
    assert record.is_used and record.attempts == 1 and record.user_id


@pytest.mark.asyncio
async def test_failed_account_transaction_rolls_back_claim_and_releases_lock(otp_db, monkeypatch):
    code, _ = await issue(otp_db)
    sessions, email, *_ = otp_db
    async with sessions() as db:
        monkeypatch.setattr(db, "flush", AsyncMock(side_effect=RuntimeError("simulated database failure")))
        with pytest.raises(RuntimeError, match="simulated"):
            await AuthService().verify_otp(db, email, code)
    record, = await rows(otp_db)
    assert not record.is_used and record.attempts == 0
    assert isinstance(await verify(otp_db, code), OtpTokenResponse)


@pytest.mark.asyncio
async def test_resend_does_not_repeat_previous_numeric_code(otp_db, monkeypatch):
    sequence = iter([111111, 111111, 222222])
    monkeypatch.setattr(auth_module.secrets, "randbelow", lambda bound: next(sequence))
    assert (await issue(otp_db))[0] == "111111"
    assert (await issue(otp_db, resend=True))[0] == "222222"
    assert isinstance(await verify(otp_db, "111111"), AuthenticationError)


@pytest.mark.asyncio
async def test_generation_failure_keeps_previous_code_usable(otp_db, monkeypatch):
    code, _ = await issue(otp_db)
    monkeypatch.setattr(auth_module.secrets, "randbelow", lambda bound: int(code))
    with pytest.raises(MirrageException) as error:
        await issue(otp_db, resend=True)
    assert error.value.code == "OTP_GENERATION_FAILED"
    assert len(otp_db[2]) == 1
    assert isinstance(await verify(otp_db, code), OtpTokenResponse)


@pytest.mark.asyncio
async def test_consumed_latest_code_never_falls_back_to_older_unused_record(otp_db):
    code, _ = await issue(otp_db)
    sessions, email, *_ = otp_db
    current, = await rows(otp_db)
    # Simulate inconsistent legacy data without using the new serialized issuer.
    async with sessions() as db:
        db.add(OtpCode(email=email, code_hash=_code_hash("777777"),
            created_at=current.created_at - timedelta(seconds=10),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
        await db.commit()
    assert isinstance(await verify(otp_db, code), OtpTokenResponse)
    assert isinstance(await verify(otp_db, "777777"), AuthenticationError)
    records = await rows(otp_db)
    assert records[0].attempts == 0 and records[1].is_used


@pytest.mark.asyncio
async def test_slow_email_delivery_does_not_hold_otp_locks(otp_db, monkeypatch):
    sessions, email, *_ = otp_db
    entered, release = asyncio.Event(), asyncio.Event()
    captured = []
    async def blocked_send(recipient, code):
        captured.append(code)
        entered.set()
        await release.wait()
    monkeypatch.setattr(auth_module.email_service, "send_otp", blocked_send)
    service = AuthService()
    async def request():
        async with sessions() as db:
            await service.request_otp(db, email)
    pending = asyncio.create_task(request())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        result = await asyncio.wait_for(verify(otp_db, captured[0], service), 5)
        assert isinstance(result, OtpTokenResponse)
    finally:
        release.set()
        await pending


@pytest.mark.asyncio
async def test_postgres_expiry_is_checked_after_waiting_for_lock(otp_db, monkeypatch):
    if otp_db[4] != "postgresql":
        pytest.skip("Tests PostgreSQL transaction-lock wait")
    code, _ = await issue(otp_db)
    sessions, email, *_ = otp_db
    before = datetime.now(timezone.utc)
    clock = [before]
    class ControlledClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]
    monkeypatch.setattr(auth_module, "datetime", ControlledClock)
    async with sessions() as db:
        record = (await db.execute(select(OtpCode).where(OtpCode.email == email))).scalar_one()
        record.expires_at = before + timedelta(seconds=1)
        await db.commit()
        lock_id = int.from_bytes(hashlib.sha256(email.encode()).digest()[:8], "big", signed=True)
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
        waiting = asyncio.create_task(verify(otp_db, code))
        try:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(waiting), 0.05)
            clock[0] = before + timedelta(seconds=2)
        finally:
            await db.commit()
        assert isinstance(await asyncio.wait_for(waiting, 5), AuthenticationError)
    record, = await rows(otp_db)
    assert record.attempts == 0 and not record.is_used
