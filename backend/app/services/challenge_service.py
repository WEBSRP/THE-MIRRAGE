import hmac
import math
import time
from datetime import datetime, timezone
from typing import List

from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.exceptions import EntityNotFoundError, MirrageException
from backend.app.core.flags import DIGEST_PATTERN, STAGE_SLUGS, flag_digest, get_shared_flags
from backend.app.models.activity import ActivityEventType, ActivityLog
from backend.app.models.challenge import Challenge, ChallengeSolve, FlagSubmission, FlagSubmissionQuota
from backend.app.models.session import GameSession, SessionStatus
from backend.app.models.user import User
from backend.app.schemas.challenge import ChallengeOut, FlagSubmitResponse


# Keep existing slugs/IDs and solve history, while describing the actual lab.
PLAYER_CHALLENGE_TEXT = {
    "first-reflection": {
        "category": "Web",
        "description": "Investigate the target web application and recover its web-stage flag.",
        "hint": "Explore the application's features and how it processes your input.",
    },
    "sub-stratum-breach": {
        "category": "Linux",
        "description": "Explore the target system and recover the player account's flag.",
        "hint": "Investigate file permissions and recurring system tasks.",
    },
    "oasis-evaporation": {
        "category": "Linux",
        "description": "Investigate privileged system operations and recover the root-stage flag.",
        "hint": "Consider which configuration files privileged processes trust.",
    },
}


def _insert(db: AsyncSession, model):
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        return pg_insert(model)
    if dialect == "sqlite":
        return sqlite_insert(model)
    raise RuntimeError("Flag submissions require PostgreSQL or SQLite")


class ChallengeService:
    async def seed_default_challenges(self, db: AsyncSession) -> None:
        """Synchronize verifiers and migrate legacy data without changing IDs/solves.

        Versioned migrations create the required tables first. Raw historical submissions are
        intentionally redacted. Existing points and active state are retained.
        """
        flags = get_shared_flags()
        titles = ["The First Reflection", "Sub-Stratum Breach", "The Dried Riverbed"]
        for (stage, slug), title, points in zip(STAGE_SLUGS.items(), titles, (100, 250, 300)):
            challenge = (await db.execute(select(Challenge).where(Challenge.slug == slug))).scalars().first()
            if challenge is None:
                challenge = Challenge(slug=slug, title=title, points=points)
                db.add(challenge)
            challenge.flag = flag_digest(flags[stage])
            for key, value in PLAYER_CHALLENGE_TEXT[slug].items():
                setattr(challenge, key, value)

        await db.flush()
        for challenge in (await db.execute(select(Challenge))).scalars().all():
            if not DIGEST_PATTERN.fullmatch(challenge.flag):
                challenge.flag = flag_digest(challenge.flag)

        # Backfill historic solves, collapsing duplicate correct attempts.
        legacy = await db.execute(
            select(FlagSubmission.user_id, FlagSubmission.challenge_id,
                   func.min(FlagSubmission.timestamp), Challenge.points)
            .join(Challenge, Challenge.id == FlagSubmission.challenge_id)
            .where(FlagSubmission.is_correct.is_(True))
            .group_by(FlagSubmission.user_id, FlagSubmission.challenge_id, Challenge.points)
        )
        for user_id, challenge_id, solved_at, points in legacy:
            await db.execute(_insert(db, ChallengeSolve).values(
                user_id=user_id, challenge_id=challenge_id, solved_at=solved_at, points=points
            ).on_conflict_do_nothing(index_elements=["user_id", "challenge_id"]))
        await db.execute(update(FlagSubmission).where(
            FlagSubmission.submitted_flag != "[REDACTED]"
        ).values(submitted_flag="[REDACTED]"))
        await db.commit()

    async def list_challenges(self, db: AsyncSession, user: User) -> List[ChallengeOut]:
        challenges = (await db.execute(
            select(Challenge).where(Challenge.is_active.is_(True)).order_by(Challenge.points, Challenge.slug)
        )).scalars().all()
        solved_ids = set((await db.execute(
            select(ChallengeSolve.challenge_id).where(ChallengeSolve.user_id == user.id)
        )).scalars().all())
        return [ChallengeOut(
            id=c.id, slug=c.slug, title=c.title, points=c.points,
            category=PLAYER_CHALLENGE_TEXT.get(c.slug, {}).get("category", c.category),
            description=PLAYER_CHALLENGE_TEXT.get(c.slug, {}).get("description", c.description),
            hint=PLAYER_CHALLENGE_TEXT.get(c.slug, {}).get("hint", c.hint),
            is_solved=c.id in solved_ids,
        ) for c in challenges]

    async def _consume_submission_budget(self, db: AsyncSession, user_id: str) -> None:
        now = time.time()
        seconds = settings.FLAG_SUBMISSION_WINDOW_SECONDS
        window = int(now // seconds)
        table = FlagSubmissionQuota
        statement = _insert(db, table).values(user_id=user_id, window=window, attempts=1)
        statement = statement.on_conflict_do_update(
            index_elements=["user_id"],
            set_={"window": window, "attempts": case(
                (table.window != window, 1), else_=table.attempts + 1
            )},
            where=(table.window != window) | (table.attempts < settings.FLAG_SUBMISSIONS_PER_WINDOW),
        ).returning(table.attempts)
        allowed = (await db.execute(statement)).scalar_one_or_none()
        # Consume budget independently of subsequent validation failures.
        await db.commit()
        if allowed is None:
            raise MirrageException(
                status_code=429, code="FLAG_RATE_LIMIT",
                detail="Too many flag submissions. Please try again shortly.",
                headers={"Retry-After": str(max(1, math.ceil((window + 1) * seconds - now)))},
            )

    async def submit_flag(
        self, db: AsyncSession, user: User, challenge_slug: str, submitted_flag: str
    ) -> FlagSubmitResponse:
        await self._consume_submission_budget(db, user.id)
        challenge = (await db.execute(select(Challenge).where(
            Challenge.slug == challenge_slug, Challenge.is_active.is_(True)
        ))).scalars().first()
        if challenge is None:
            raise EntityNotFoundError("Challenge", challenge_slug)

        if not DIGEST_PATTERN.fullmatch(challenge.flag):
            raise MirrageException(503, "Challenge verifier is not configured", "FLAG_NOT_CONFIGURED")
        is_correct = hmac.compare_digest(flag_digest(submitted_flag), challenge.flag)
        now = datetime.now(timezone.utc)
        if is_correct:
            result = await db.execute(_insert(db, ChallengeSolve).values(
                user_id=user.id, challenge_id=challenge.id, solved_at=now, points=challenge.points
            ).on_conflict_do_nothing(index_elements=["user_id", "challenge_id"])
                .returning(ChallengeSolve.user_id))
            already_solved = result.scalar_one_or_none() is None
        else:
            already_solved = (await db.execute(select(ChallengeSolve.user_id).where(
                ChallengeSolve.user_id == user.id, ChallengeSolve.challenge_id == challenge.id
            ))).scalar_one_or_none() is not None

        db.add(FlagSubmission(user_id=user.id, challenge_id=challenge.id,
                              submitted_flag="[REDACTED]", is_correct=is_correct))
        db.add(ActivityLog(
            user_id=user.id, event_type=ActivityEventType.FLAG_SUBMISSION,
            summary=f"Flag submission for '{challenge.title}': {'CORRECT' if is_correct else 'INCORRECT'}",
            payload={"challenge_slug": challenge_slug, "is_correct": is_correct},
        ))
        await db.execute(update(GameSession).where(
            GameSession.user_id == user.id,
            GameSession.status.in_([SessionStatus.PENDING, SessionStatus.INITIALIZING,
                                   SessionStatus.PROVISIONING, SessionStatus.READY]),
            GameSession.expires_at > now,
        ).values(last_active_at=now))
        # Solve, attempt and activity commit together; no helper commits in between.
        await db.commit()
        if not is_correct:
            message = "Incorrect flag. Question what you found."
        elif already_solved:
            message = "Flag is correct, but you have already solved this challenge."
        else:
            message = f"Congratulations! You solved '{challenge.title}'."
        return FlagSubmitResponse(
            is_correct=is_correct, message=message, already_solved=already_solved,
            points_awarded=challenge.points if is_correct and not already_solved else 0,
        )


challenge_service = ChallengeService()
