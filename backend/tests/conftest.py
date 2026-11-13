import os
# Configure testing environment before any app modules are loaded
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("SECRET_KEY", "test-only-jwt-secret-key-not-for-production-use-minimum-32-characters")
os.environ.setdefault("OTP_HMAC_SECRET", "test-only-otp-hmac-secret-not-for-production-use-32-chars")
os.environ.setdefault("K8S_MODE", "mock")
os.environ.setdefault("VPN_MODE", "mock")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db
from backend.app.core.security import hash_password, create_access_token
from backend.app.main import app
from backend.app.models.user import User

# Test Database Engine (in-memory SQLite async)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_test_database():
    """Create clean tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async session for tests."""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an authenticated/unauthenticated async test client."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create and return a standard test user."""
    user = User(
        email="player@mirrage.io",
        username="operative_zero",
        hashed_password=hash_password("CyberSecret2026!"),
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, test_user: User) -> dict:
    """Authenticate test user and return Bearer auth headers."""
    token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_user(db_session: AsyncSession) -> User:
    """Create and return a second test user for cross-user isolation tests."""
    user = User(
        email="player2@mirrage.io",
        username="operative_two",
        hashed_password=hash_password("CyberSecret2026!"),
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def second_auth_headers(async_client: AsyncClient, second_user: User) -> dict:
    """Authenticate second user and return Bearer auth headers."""
    token = create_access_token(subject=second_user.id)
    return {"Authorization": f"Bearer {token}"}
