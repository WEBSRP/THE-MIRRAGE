import asyncio
import importlib.util
from importlib import import_module
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.core.flags import STAGE_SLUGS, flag_digest, get_shared_flags, load_shared_flags
from backend.app.models.activity import ActivityLog
from backend.app.models.challenge import Challenge, ChallengeSolve, FlagSubmission
from backend.app.models.user import User
from backend.app.services.challenge_service import challenge_service

ROOT = Path(__file__).resolve().parents[2]
SUBMIT = "/api/v1/challenges/submit"


@pytest.mark.asyncio
async def test_all_shared_flags_work_for_both_players_and_never_leave_answers_in_db(
    async_client, auth_headers, second_auth_headers, db_session
):
    await challenge_service.seed_default_challenges(db_session)
    flags = get_shared_flags()
    for headers in (auth_headers, second_auth_headers):
        for stage, slug in STAGE_SLUGS.items():
            response = await async_client.post(SUBMIT, headers=headers, json={
                "challenge_slug": slug, "flag": flags[stage],
            })
            assert response.status_code == 200
            assert response.json()["is_correct"]
            assert response.json()["points_awarded"] > 0
            assert not any(value in response.text for value in flags.values())
        repeat = await async_client.post(SUBMIT, headers=headers, json={
            "challenge_slug": STAGE_SLUGS["web"], "flag": flags["web"],
        })
        assert repeat.json()["already_solved"]
        assert repeat.json()["points_awarded"] == 0
        wrong_stage = await async_client.post(SUBMIT, headers=headers, json={
            "challenge_slug": STAGE_SLUGS["root"], "flag": flags["web"],
        })
        assert not wrong_stage.json()["is_correct"]

    assert (await db_session.execute(select(func.count()).select_from(ChallengeSolve))).scalar() == 6
    challenges = (await db_session.execute(select(Challenge))).scalars().all()
    assert {c.flag for c in challenges} == {flag_digest(v) for v in flags.values()}
    attempts = (await db_session.execute(select(FlagSubmission))).scalars().all()
    assert all(attempt.submitted_flag == "[REDACTED]" for attempt in attempts)
    logs = (await db_session.execute(select(ActivityLog))).scalars().all()
    assert not any(flag in str([(log.summary, log.payload) for log in logs]) for flag in flags.values())


@pytest.mark.asyncio
async def test_submission_limit_is_account_wide_returns_retry_and_resets(
    async_client, auth_headers, second_auth_headers, db_session, monkeypatch
):
    await challenge_service.seed_default_challenges(db_session)
    monkeypatch.setattr(settings, "FLAG_SUBMISSIONS_PER_WINDOW", 2)
    clock = SimpleNamespace(time=lambda: 120.0)
    monkeypatch.setattr(import_module("backend.app.services.challenge_service"), "time", clock)
    for stage in ("web", "user"):
        response = await async_client.post(SUBMIT, headers=auth_headers, json={
            "challenge_slug": STAGE_SLUGS[stage], "flag": "MIRRAGE{wrong}",
        })
        assert response.status_code == 200
    blocked = await async_client.post(SUBMIT, headers=auth_headers, json={
        "challenge_slug": STAGE_SLUGS["root"], "flag": get_shared_flags()["root"],
    })
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"
    assert blocked.json()["code"] == "FLAG_RATE_LIMIT"
    other = await async_client.post(SUBMIT, headers=second_auth_headers, json={
        "challenge_slug": STAGE_SLUGS["root"], "flag": get_shared_flags()["root"],
    })
    assert other.status_code == 200
    clock.time = lambda: 180.0
    resumed = await async_client.post(SUBMIT, headers=auth_headers, json={
        "challenge_slug": STAGE_SLUGS["root"], "flag": get_shared_flags()["root"],
    })
    assert resumed.status_code == 200 and resumed.json()["is_correct"]


@pytest.mark.asyncio
async def test_disabled_and_missing_challenges_rejected_and_auth_required(
    async_client, auth_headers, db_session
):
    await challenge_service.seed_default_challenges(db_session)
    challenge = (await db_session.execute(select(Challenge).where(
        Challenge.slug == STAGE_SLUGS["web"]
    ))).scalar_one()
    challenge.is_active = False
    await db_session.commit()
    for slug in (challenge.slug, "missing"):
        response = await async_client.post(SUBMIT, headers=auth_headers, json={
            "challenge_slug": slug, "flag": get_shared_flags()["web"],
        })
        assert response.status_code == 404
    unauthenticated = await async_client.post(SUBMIT, json={
        "challenge_slug": STAGE_SLUGS["web"], "flag": get_shared_flags()["web"],
    })
    assert unauthenticated.status_code == 401


@pytest.mark.asyncio
async def test_legacy_upgrade_preserves_ids_solves_points_and_redacts_answers(db_session, test_user):
    old = Challenge(slug=STAGE_SLUGS["web"], title="Old title", category="Old",
                    description="Old", points=125, flag="MIRRAGE{old_answer}")
    custom = Challenge(slug="custom", title="Custom", category="Web", description="Custom",
                       points=70, flag="MIRRAGE{custom_answer}")
    db_session.add_all([old, custom])
    await db_session.flush()
    old_id, custom_id = old.id, custom.id
    for _ in range(2):
        db_session.add(FlagSubmission(user_id=test_user.id, challenge_id=old.id,
                                     submitted_flag=old.flag, is_correct=True))
    await db_session.commit()
    await challenge_service.seed_default_challenges(db_session)
    await challenge_service.seed_default_challenges(db_session)
    await db_session.refresh(old)
    await db_session.refresh(custom)
    assert old.id == old_id and old.points == 125
    assert old.flag == flag_digest(get_shared_flags()["web"])
    assert custom.id == custom_id and custom.flag == flag_digest("MIRRAGE{custom_answer}")
    solves = (await db_session.execute(select(ChallengeSolve))).scalars().all()
    assert len(solves) == 1 and solves[0].points == 125
    assert all(v == "[REDACTED]" for v in (await db_session.execute(
        select(FlagSubmission.submitted_flag)
    )).scalars())
    repeated = await challenge_service.submit_flag(db_session, test_user, old.slug, get_shared_flags()["web"])
    assert repeated.already_solved and repeated.points_awarded == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
async def test_concurrent_correct_submissions_have_one_winner(tmp_path, monkeypatch, database):
    """Separate transactions/connections, as opposed to sharing one AsyncSession."""
    monkeypatch.setattr(settings, "FLAG_SUBMISSIONS_PER_WINDOW", 50)
    if database == "postgresql":
        url = os.environ.get("MIRRAGE_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("Set MIRRAGE_TEST_POSTGRES_URL to an isolated disposable PostgreSQL DB")
    else:
        url = f"sqlite+aiosqlite:///{tmp_path / 'concurrency.db'}"
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            user = User(email="concurrent@example.com", username="concurrent", is_active=True)
            db.add(user)
            await db.commit()
            await challenge_service.seed_default_challenges(db)
            user_id = user.id

        async def submit():
            async with sessions() as db:
                # Endpoint auth also loads the user before consuming the quota.
                user = await db.get(User, user_id)
                return await challenge_service.submit_flag(
                    db, user, STAGE_SLUGS["web"], get_shared_flags()["web"]
                )
        results = await asyncio.gather(*(submit() for _ in range(6)))
        assert sum(result.points_awarded for result in results) == 100
        assert sum(not result.already_solved for result in results) == 1
        async with sessions() as db:
            assert (await db.execute(select(func.count()).select_from(ChallengeSolve))).scalar() == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
async def test_concurrent_quota_cannot_exceed_limit(tmp_path, monkeypatch, database):
    from backend.app.core.exceptions import MirrageException

    if database == "postgresql":
        url = os.environ.get("MIRRAGE_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("Set MIRRAGE_TEST_POSTGRES_URL to an isolated disposable PostgreSQL DB")
    else:
        url = f"sqlite+aiosqlite:///{tmp_path / 'quota.db'}"
    monkeypatch.setattr(settings, "FLAG_SUBMISSIONS_PER_WINDOW", 3)
    monkeypatch.setattr(import_module("backend.app.services.challenge_service"), "time",
                        SimpleNamespace(time=lambda: 120.0))
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            user = User(email="quota@example.com", username="quota", is_active=True)
            db.add(user)
            await db.commit()
            user_id = user.id

        async def attempt():
            async with sessions() as db:
                try:
                    await challenge_service._consume_submission_budget(db, user_id)
                    return True
                except MirrageException as error:
                    assert error.status_code == 429
                    return False
        results = await asyncio.gather(*(attempt() for _ in range(12)))
        assert sum(results) == 3
    finally:
        await engine.dispose()


def test_config_rejects_missing_duplicate_dummy_production_and_secret_in_errors(tmp_path):
    path = tmp_path / "flags.json"
    with pytest.raises(ValueError, match="Cannot read"):
        load_shared_flags(path)
    flags = get_shared_flags().copy()
    path.write_text(json.dumps(flags))
    with pytest.raises(ValueError, match="Production") as error:
        load_shared_flags(path, production=True)
    assert not any(value in str(error.value) for value in flags.values())
    flags["root"] = flags["user"]
    path.write_text(json.dumps(flags))
    with pytest.raises(ValueError, match="different"):
        load_shared_flags(path)
    path.write_text('{"web": "sensitive invalid JSON')
    with pytest.raises(ValueError) as error:
        load_shared_flags(path)
    assert "sensitive" not in str(error.value)


def test_runtime_writer_matches_verifiers_and_enforces_stage_file_modes(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("ctf_entrypoint", ROOT / "containers/ctf/entrypoint.py")
    entrypoint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entrypoint)
    source = tmp_path / "flags.json"
    source.write_text(json.dumps(get_shared_flags()))
    flags = entrypoint.load_flags(source)
    paths = {stage: (tmp_path / f"{stage}.txt", stage) for stage in STAGE_SLUGS}
    monkeypatch.setattr(entrypoint, "FLAG_TARGETS", paths)
    monkeypatch.setattr(entrypoint.pwd, "getpwnam", lambda _: SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid()))
    entrypoint.install_flags(flags)
    for stage, (path, _) in paths.items():
        assert path.stat().st_mode & 0o777 == 0o600
        assert flag_digest(path.read_text()) == flag_digest(get_shared_flags()[stage])
    # Restart refuses symlinks rather than overwriting another file as root.
    paths["web"][0].unlink()
    paths["web"][0].symlink_to(paths["root"][0])
    with pytest.raises(OSError):
        entrypoint.install_flags(flags)


def test_k8s_flag_secret_is_immutable_reused_and_verified():
    import base64
    from kubernetes.client.rest import ApiException
    from backend.app.services.k8s_service import ProductionKubernetesService

    service = object.__new__(ProductionKubernetesService)
    service.namespace = "test-only"
    service.core_v1 = Mock()
    service.core_v1.read_namespaced_secret.side_effect = ApiException(status=404)
    name = service._ensure_flags_secret()
    body = service.core_v1.create_namespaced_secret.call_args.kwargs["body"]
    assert name.startswith("mirrage-ctf-flags-") and body.immutable
    assert json.loads(body.string_data["flags.json"]) == get_shared_flags()
    service.core_v1.read_namespaced_secret.side_effect = None
    service.core_v1.read_namespaced_secret.return_value = SimpleNamespace(data={
        "flags.json": base64.b64encode(body.string_data["flags.json"].encode()).decode(),
    })
    assert service._ensure_flags_secret() == name
    assert service.core_v1.create_namespaced_secret.call_count == 1
    service.core_v1.read_namespaced_secret.return_value = SimpleNamespace(data={"flags.json": "e30="})
    with pytest.raises(RuntimeError, match="does not match"):
        service._ensure_flags_secret()


@pytest.mark.asyncio
async def test_provisioner_mounts_root_only_flags_into_ctf_not_mirage():
    from backend.app.services.k8s_service import ProductionKubernetesService

    service = object.__new__(ProductionKubernetesService)
    service.namespace = "test-only"
    service._ensure_namespace_and_sa = Mock()
    service._ensure_flags_secret = Mock(return_value="private-flag-revision")
    service.networking_v1 = Mock()
    service.networking_v1.list_namespaced_network_policy.return_value = SimpleNamespace(items=[])
    service.core_v1 = Mock()
    service.core_v1.read_namespaced_pod.return_value = SimpleNamespace(status=SimpleNamespace(
        phase="Running", pod_ip="10.42.0.10",
        conditions=[SimpleNamespace(type="Ready", status="True")],
        container_statuses=[SimpleNamespace(ready=True), SimpleNamespace(ready=True)],
    ))
    await service.provision_player_pod("test-session", "test-player", "player", "10.8.0.10")
    pod = service.core_v1.create_namespaced_pod.call_args.kwargs["body"]
    mirage, ctf = pod.spec.containers
    assert mirage.volume_mounts is None
    assert ctf.volume_mounts[0].read_only
    assert ctf.volume_mounts[0].mount_path == "/run/mirrage-flags"
    assert pod.spec.volumes[0].secret.default_mode == 0o400
    assert pod.spec.volumes[0].secret.secret_name == "private-flag-revision"
    assert not any(flag in json.dumps(pod.to_dict()) for flag in get_shared_flags().values())


def test_production_requires_private_configuration_and_generated_flags_are_valid(tmp_path, monkeypatch):
    get_shared_flags.cache_clear()
    try:
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "CTF_FLAGS_FILE", "")
        with pytest.raises(ValueError, match="required in production"):
            get_shared_flags()
        path = tmp_path / "ctf-flags.json"
        result = subprocess.run([
            sys.executable, str(ROOT / "backend/scripts/generate_ctf_flags.py"),
            "--output", str(path),
        ], check=True, capture_output=True, text=True)
        flags = load_shared_flags(path, production=True)
        assert path.stat().st_mode & 0o777 == 0o600
        assert all(flag not in result.stdout + result.stderr for flag in flags.values())
        monkeypatch.setattr(settings, "CTF_FLAGS_FILE", str(path))
        assert get_shared_flags() == flags
        original = path.read_text()
        repeated = subprocess.run([
            sys.executable, str(ROOT / "backend/scripts/generate_ctf_flags.py"),
            "--output", str(path),
        ], capture_output=True)
        assert repeated.returncode != 0 and path.read_text() == original
    finally:
        get_shared_flags.cache_clear()
