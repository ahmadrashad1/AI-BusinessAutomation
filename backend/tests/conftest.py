"""
Shared pytest fixtures for unit and integration tests.

Integration tests use a real PostgreSQL database (bpa_test) and a real Redis instance.
Unit tests use AsyncMock to avoid external dependencies entirely.

Environment: pytest-asyncio in "auto" mode (set in pyproject.toml).
"""
import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.core.security import create_access_token, hash_password
from app.modules.auth.models import User
from app.modules.organizations.models import Organization, OrgMember
from app.main import create_app


# ── test settings override ─────────────────────────────────────────────────

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def settings():
    s = get_settings()
    s.RATE_LIMIT_ENABLED = False  # disable rate limiting in all tests
    return s


# ── database fixtures (integration) ───────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def test_engine(settings):
    """Create an async engine pointed at the test database."""
    engine = create_async_engine(settings.TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)

    import sqlalchemy as _sa
    async with engine.begin() as conn:
        await conn.execute(_sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(_sa.text('CREATE EXTENSION IF NOT EXISTS "pg_trgm"'))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Each test gets its own transaction that is rolled back on completion."""
    async with test_engine.connect() as conn:
        await conn.begin()
        session_factory = async_sessionmaker(bind=conn, expire_on_commit=False, autoflush=False)
        async with session_factory() as session:
            yield session
        await conn.rollback()


# ── Redis fixture (integration) ────────────────────────────────────────────

@pytest_asyncio.fixture
async def redis_client():
    """Real Redis client connected to local Redis. Flushes test keys after each test."""
    import redis.asyncio as aioredis
    client = aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)
    yield client
    # Clean up all session: and rate_limit: keys created during the test
    async for key in client.scan_iter("session:*"):
        await client.delete(key)
    async for key in client.scan_iter("rate_limit:*"):
        await client.delete(key)
    await client.aclose()


# ── FastAPI test client (integration) ─────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_session, redis_client) -> AsyncGenerator[AsyncClient, None]:
    """
    httpx.AsyncClient that talks directly to the FastAPI ASGI app.
    Overrides get_db and get_redis to use the test fixtures.
    """
    app = create_app()

    async def override_db():
        yield db_session

    async def override_redis():
        yield redis_client

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# ── Mock fixtures (unit tests) ─────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Async mock for AsyncSession used in unit tests."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_redis():
    """Async mock for Redis used in unit tests."""
    return AsyncMock()


# ── Common test data ───────────────────────────────────────────────────────

@pytest.fixture
def user_password() -> str:
    return "SecurePass123!"


@pytest.fixture
def user_data(user_password) -> dict[str, Any]:
    return {
        "email": "alice@example.com",
        "password": user_password,
        "full_name": "Alice Smith",
    }


@pytest_asyncio.fixture
async def verified_user(db_session, user_password) -> User:
    """A verified, active user already persisted in the test DB."""
    user = User(
        email="verified@example.com",
        hashed_password=hash_password(user_password),
        full_name="Verified User",
        is_verified=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def unverified_user(db_session, user_password) -> User:
    """An unverified (newly registered) user."""
    user = User(
        email="unverified@example.com",
        hashed_password=hash_password(user_password),
        full_name="Unverified User",
        is_verified=False,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ── Organization fixtures ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def org_owner(db_session) -> tuple[User, Organization, OrgMember, str]:
    """An org with a verified owner user. Returns (user, org, member, access_token)."""
    user = User(
        email="owner@orgtest.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="Org Owner",
        is_verified=True, is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    org = Organization(
        name="Test Org", slug="test-org", plan="free", is_active=True,
        settings={}, storage_used_bytes=0,
    )
    db_session.add(org)
    await db_session.flush()

    member = OrgMember(organization_id=org.id, user_id=user.id, role="owner")
    db_session.add(member)
    await db_session.flush()

    token = create_access_token(
        user_id=user.id, org_id=org.id, session_id=uuid4(),
        role="owner", scope="org",
    )
    return user, org, member, token


@pytest_asyncio.fixture
async def org_admin(db_session, org_owner) -> tuple[User, Organization, OrgMember, str]:
    """An admin member in the same org as org_owner."""
    _, org, _, _ = org_owner

    user = User(
        email="admin@orgtest.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="Org Admin",
        is_verified=True, is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    member = OrgMember(organization_id=org.id, user_id=user.id, role="admin")
    db_session.add(member)
    await db_session.flush()

    token = create_access_token(
        user_id=user.id, org_id=org.id, session_id=uuid4(),
        role="admin", scope="org",
    )
    return user, org, member, token


@pytest_asyncio.fixture
async def org_viewer(db_session, org_owner) -> tuple[User, Organization, OrgMember, str]:
    """A viewer member in the same org as org_owner."""
    _, org, _, _ = org_owner

    user = User(
        email="viewer@orgtest.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="Org Viewer",
        is_verified=True, is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    member = OrgMember(organization_id=org.id, user_id=user.id, role="viewer")
    db_session.add(member)
    await db_session.flush()

    token = create_access_token(
        user_id=user.id, org_id=org.id, session_id=uuid4(),
        role="viewer", scope="org",
    )
    return user, org, member, token
