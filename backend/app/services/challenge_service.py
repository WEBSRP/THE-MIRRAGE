from typing import List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.exceptions import EntityNotFoundError
from backend.app.models.activity import ActivityEventType
from backend.app.models.challenge import Challenge, FlagSubmission
from backend.app.models.user import User
from backend.app.schemas.challenge import ChallengeOut, FlagSubmitResponse
from backend.app.services.activity_service import activity_service


# Public copy is separate from persisted challenge data so older installations
# also receive spoiler-free descriptions without changing flags or solve records.
PLAYER_CHALLENGE_TEXT = {
    "sub-stratum-breach": {
        "category": "Network",
        "description": "Enumerate the assigned target and investigate its services to recover the flag.",
        "hint": "Start with the target address in your Session Console and inspect available services.",
    },
    "oasis-evaporation": {
        "category": "Forensics",
        "description": "Examine application records and system artifacts to reconstruct the missing evidence.",
        "hint": "Check timestamps, archived records, and rotated logs.",
    },
}


class ChallengeService:
    async def seed_default_challenges(self, db: AsyncSession) -> None:
        """Seed foundational MIRRAGE deception & CTF challenges if not present."""
        default_challenges = [
            {
                "slug": "first-reflection",
                "title": "The First Reflection",
                "category": "Perception",
                "description": (
                    "Investigate the initial survey records. Discard the apparent monument "
                    "and find the underlying coordinates left by the secondary survey team."
                ),
                "points": 100,
                "flag": "MIRRAGE{r3fl3ct10n_1s_n0t_r34l1ty_7f9a}",
                "hint": "Inspect Archive 003 cross-references and the sub-stratum echo.",
            },
            {
                "slug": "sub-stratum-breach",
                "title": "Sub-Stratum Breach",
                **PLAYER_CHALLENGE_TEXT["sub-stratum-breach"],
                "points": 250,
                "flag": "MIRRAGE{b3y0nd_th3_d3c0y_c0nt41n3r_82k1}",
            },
            {
                "slug": "oasis-evaporation",
                "title": "The Dried Riverbed",
                **PLAYER_CHALLENGE_TEXT["oasis-evaporation"],
                "points": 300,
                "flag": "MIRRAGE{p4rch3d_34rth_r3v34ls_4ll_491d}",
            },
        ]

        for chal_data in default_challenges:
            query = select(Challenge).where(Challenge.slug == chal_data["slug"])
            result = await db.execute(query)
            existing = result.scalars().first()
            if not existing:
                challenge = Challenge(**chal_data)
                db.add(challenge)

        await db.commit()

    async def list_challenges(self, db: AsyncSession, user: User) -> List[ChallengeOut]:
        """List active challenges with player's solve status."""
        query = select(Challenge).where(Challenge.is_active.is_(True))
        result = await db.execute(query)
        challenges = list(result.scalars().all())

        # Fetch solved challenge IDs for this user
        sub_query = select(FlagSubmission.challenge_id).where(
            FlagSubmission.user_id == user.id,
            FlagSubmission.is_correct.is_(True)
        )
        sub_result = await db.execute(sub_query)
        solved_ids = set(sub_result.scalars().all())

        out = []
        for c in challenges:
            public_text = PLAYER_CHALLENGE_TEXT.get(c.slug, {})
            out.append(
                ChallengeOut(
                    id=c.id,
                    slug=c.slug,
                    title=c.title,
                    category=public_text.get("category", c.category),
                    description=public_text.get("description", c.description),
                    points=c.points,
                    hint=public_text.get("hint", c.hint),
                    is_solved=c.id in solved_ids,
                )
            )
        return out

    async def submit_flag(
        self,
        db: AsyncSession,
        user: User,
        challenge_slug: str,
        submitted_flag: str
    ) -> FlagSubmitResponse:
        """Verify submitted flag, record attempt, and award points."""
        query = select(Challenge).where(Challenge.slug == challenge_slug)
        result = await db.execute(query)
        challenge = result.scalars().first()

        if not challenge:
            raise EntityNotFoundError("Challenge", challenge_slug)

        # Check if already solved
        sub_query = select(FlagSubmission).where(
            FlagSubmission.user_id == user.id,
            FlagSubmission.challenge_id == challenge.id,
            FlagSubmission.is_correct.is_(True)
        )
        sub_result = await db.execute(sub_query)
        already_solved = sub_result.scalars().first() is not None

        import hmac
        is_correct = hmac.compare_digest(submitted_flag.strip(), challenge.flag.strip())

        # Record submission
        submission = FlagSubmission(
            user_id=user.id,
            challenge_id=challenge.id,
            submitted_flag=submitted_flag.strip(),
            is_correct=is_correct,
        )
        db.add(submission)

        # Extend player's active session lifetime on meaningful action
        from backend.app.services.session_service import session_service
        await session_service.record_activity_for_user(db, user.id)

        # Log activity (never log the actual flag or secret values)
        await activity_service.log_event(
            db=db,
            user_id=user.id,
            event_type=ActivityEventType.FLAG_SUBMISSION,
            summary=f"Flag submission for '{challenge.title}': {'CORRECT' if is_correct else 'INCORRECT'}",
            payload={"challenge_slug": challenge_slug, "is_correct": is_correct}
        )

        await db.commit()

        if is_correct:
            if already_solved:
                return FlagSubmitResponse(
                    is_correct=True,
                    message="Flag is correct, but you have already solved this challenge.",
                    points_awarded=0,
                    already_solved=True,
                )
            return FlagSubmitResponse(
                is_correct=True,
                message=f"Congratulations! You solved '{challenge.title}' .",
                points_awarded=challenge.points,
                already_solved=False,
            )
        else:
            return FlagSubmitResponse(
                is_correct=False,
                message="Incorrect flag. Question what you found.",
                points_awarded=0,
                already_solved=already_solved,
            )


challenge_service = ChallengeService()
