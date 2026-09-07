import pytest
from httpx import AsyncClient
from backend.app.core.config import settings
from backend.app.services.challenge_service import challenge_service


@pytest.mark.asyncio
async def test_list_and_solve_challenge(async_client: AsyncClient, auth_headers: dict, db_session):
    """Test challenge listing and correct/incorrect flag submissions."""
    # Seed default challenges
    await challenge_service.seed_default_challenges(db_session)

    # 1. List challenges
    list_resp = await async_client.get(
        f"{settings.API_V1_STR}/challenges/",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    challenges = list_resp.json()
    assert len(challenges) >= 3
    first_chal = challenges[0]
    assert first_chal["is_solved"] is False

    # 2. Submit wrong flag
    wrong_sub = await async_client.post(
        f"{settings.API_V1_STR}/challenges/submit",
        headers=auth_headers,
        json={
            "challenge_slug": first_chal["slug"],
            "flag": "MIRRAGE{invalid_flag_guess}",
        },
    )
    assert wrong_sub.status_code == 200
    wrong_data = wrong_sub.json()
    assert wrong_data["is_correct"] is False
    assert wrong_data["points_awarded"] == 0

    # 3. Submit correct flag for first reflection
    correct_sub = await async_client.post(
        f"{settings.API_V1_STR}/challenges/submit",
        headers=auth_headers,
        json={
            "challenge_slug": "first-reflection",
            "flag": "MIRRAGE{r3fl3ct10n_1s_n0t_r34l1ty_7f9a}",
        },
    )
    assert correct_sub.status_code == 200
    correct_data = correct_sub.json()
    assert correct_data["is_correct"] is True
    assert correct_data["points_awarded"] == 100

    # 4. Check list again - challenge should now be marked solved
    list_resp2 = await async_client.get(
        f"{settings.API_V1_STR}/challenges/",
        headers=auth_headers,
    )
    chals2 = list_resp2.json()
    solved = next(c for c in chals2 if c["slug"] == "first-reflection")
    assert solved["is_solved"] is True
