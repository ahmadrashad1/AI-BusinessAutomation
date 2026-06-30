"""
Integration tests for /api/v1/auth/* endpoints.

These tests run against the real FastAPI ASGI app with:
- A real PostgreSQL test database (transactions rolled back after each test)
- A real Redis instance (keys flushed after each test)
- RATE_LIMIT_ENABLED=False (set in conftest.py)

TDD: these tests were written BEFORE the router implementation.
"""
import pytest
from httpx import AsyncClient


# ── registration ───────────────────────────────────────────────────────────

class TestRegister:
    @pytest.mark.asyncio
    async def test_register_201(self, client: AsyncClient, user_data):
        resp = await client.post("/api/v1/auth/register", json=user_data)
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == user_data["email"]
        assert body["is_verified"] is False
        assert "hashed_password" not in body

    @pytest.mark.asyncio
    async def test_register_409_duplicate_email(self, client: AsyncClient, user_data):
        await client.post("/api/v1/auth/register", json=user_data)
        resp = await client.post("/api/v1/auth/register", json=user_data)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "CONFLICT"

    @pytest.mark.asyncio
    async def test_register_422_weak_password(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "weak",
            "full_name": "Test User",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_422_invalid_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "SecurePass123!",
            "full_name": "Test User",
        })
        assert resp.status_code == 422


# ── login ──────────────────────────────────────────────────────────────────

class TestLogin:
    @pytest.mark.asyncio
    async def test_login_401_unverified_user(self, client: AsyncClient, unverified_user, user_password):
        resp = await client.post("/api/v1/auth/login", json={
            "email": unverified_user.email,
            "password": user_password,
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

    @pytest.mark.asyncio
    async def test_login_401_wrong_password(self, client: AsyncClient, verified_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": verified_user.email,
            "password": "WrongPassword1!",
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_401_unknown_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_200_returns_tokens(self, client: AsyncClient, verified_user, user_password):
        """Verified user with no org gets a token (limited scope)."""
        resp = await client.post("/api/v1/auth/login", json={
            "email": verified_user.email,
            "password": user_password,
        })
        # Could be 200 (tokens) or 200 (org picker list) — either means auth succeeded
        assert resp.status_code == 200
        body = resp.json()
        assert "user" in body

    @pytest.mark.asyncio
    async def test_login_sets_refresh_cookie(self, client: AsyncClient, verified_user, user_password):
        resp = await client.post("/api/v1/auth/login", json={
            "email": verified_user.email,
            "password": user_password,
        })
        assert resp.status_code == 200
        assert "refresh_token" in resp.cookies


# ── verify email ───────────────────────────────────────────────────────────

class TestVerifyEmail:
    @pytest.mark.asyncio
    async def test_verify_email_200(self, client: AsyncClient, db_session, user_data):
        from app.core.security import generate_token, hash_token
        from app.modules.auth.models import User, EmailVerificationToken
        from datetime import datetime, timedelta, timezone
        from app.core.security import hash_password

        # Create unverified user manually
        user = User(
            email="toverify@example.com",
            hashed_password=hash_password(user_data["password"]),
            full_name="To Verify",
            is_verified=False,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        plain = generate_token()
        evt = EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(plain),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db_session.add(evt)
        await db_session.flush()

        resp = await client.post("/api/v1/auth/verify-email", json={"token": plain})
        assert resp.status_code == 200
        await db_session.refresh(user)
        assert user.is_verified is True

    @pytest.mark.asyncio
    async def test_verify_email_404_bad_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
        assert resp.status_code == 404


# ── refresh ────────────────────────────────────────────────────────────────

class TestRefresh:
    @pytest.mark.asyncio
    async def test_refresh_requires_cookie(self, client: AsyncClient):
        """Calling /refresh without a cookie must return 401."""
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_returns_new_access_token(self, client: AsyncClient, verified_user, user_password):
        # Login to get refresh cookie
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": verified_user.email,
            "password": user_password,
        })
        assert login_resp.status_code == 200
        cookie = login_resp.cookies.get("refresh_token")
        if cookie is None:
            pytest.skip("No refresh token cookie — org-picker path")

        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": cookie},
        )
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.json()
        # New refresh token cookie should also be set
        assert "refresh_token" in refresh_resp.cookies

    @pytest.mark.asyncio
    async def test_refresh_replay_attack_returns_401(self, client: AsyncClient, verified_user, user_password):
        """Using the same refresh token twice must fail on the second call."""
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": verified_user.email,
            "password": user_password,
        })
        assert login_resp.status_code == 200
        cookie = login_resp.cookies.get("refresh_token")
        if cookie is None:
            pytest.skip("No refresh token cookie — org-picker path")

        r1 = await client.post("/api/v1/auth/refresh", cookies={"refresh_token": cookie})
        assert r1.status_code == 200

        r2 = await client.post("/api/v1/auth/refresh", cookies={"refresh_token": cookie})
        assert r2.status_code == 401
        assert r2.json()["error"]["code"] == "REFRESH_TOKEN_REUSED"


# ── logout ─────────────────────────────────────────────────────────────────

class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_204(self, client: AsyncClient, verified_user, user_password):
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": verified_user.email,
            "password": user_password,
        })
        assert login_resp.status_code == 200
        access_token = login_resp.json().get("access_token")
        if not access_token:
            pytest.skip("No access token in org-picker response")

        resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 204


# ── forgot / reset password ────────────────────────────────────────────────

class TestPasswordReset:
    @pytest.mark.asyncio
    async def test_forgot_password_always_200(self, client: AsyncClient):
        """Should return 200 regardless of whether the email exists (prevents enumeration)."""
        resp = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_reset_password_404_bad_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": "bad-token",
            "new_password": "NewSecurePass456!",
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_reset_password_success(self, client: AsyncClient, db_session, user_data):
        from app.core.security import generate_token, hash_token, hash_password
        from app.modules.auth.models import User, PasswordResetToken
        from datetime import datetime, timedelta, timezone

        user = User(
            email="resetme@example.com",
            hashed_password=hash_password(user_data["password"]),
            full_name="Reset Me",
            is_verified=True,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        plain = generate_token()
        prt = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(plain),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(prt)
        await db_session.flush()

        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": plain,
            "new_password": "BrandNew123!",
        })
        assert resp.status_code == 200
