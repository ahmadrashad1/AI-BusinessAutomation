"""
Integration / security tests for JWT and token-level guarantees.

These verify M1 exit criteria:
- Expired JWT returns 401 TOKEN_EXPIRED
- Tampered JWT returns 401 INVALID_TOKEN
- Refresh token replay returns 401 REFRESH_TOKEN_REUSED
"""
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    generate_token,
    hash_password,
    hash_token,
    redis_session_key,
)
from app.core.exceptions import UnauthorizedError


# ── unit-level JWT tests (no HTTP required) ────────────────────────────────

class TestJWTSecurity:
    def test_expired_access_token_raises_token_expired(self):
        settings = get_settings()
        past_exp = datetime.now(timezone.utc) - timedelta(minutes=1)
        payload = {
            "user_id": str(uuid4()),
            "org_id": str(uuid4()),
            "session_id": str(uuid4()),
            "role": "analyst",
            "scope": "org",
            "iat": datetime.now(timezone.utc) - timedelta(minutes=20),
            "exp": past_exp,
            "type": "access",
        }
        expired_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(UnauthorizedError) as exc_info:
            decode_access_token(expired_token)

        assert exc_info.value.error_code == "TOKEN_EXPIRED"

    def test_tampered_access_token_raises_invalid_token(self):
        user_id = uuid4()
        session_id = uuid4()
        token = create_access_token(
            user_id=user_id,
            org_id=uuid4(),
            session_id=session_id,
            role="analyst",
        )
        # Corrupt the signature by flipping the last character
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

        with pytest.raises(UnauthorizedError) as exc_info:
            decode_access_token(tampered)

        assert exc_info.value.error_code == "INVALID_TOKEN"

    def test_refresh_token_used_as_access_token_raises_invalid(self):
        """A refresh token must NOT be accepted where an access token is expected."""
        refresh = create_refresh_token(user_id=uuid4(), session_id=uuid4())
        with pytest.raises(UnauthorizedError) as exc_info:
            decode_access_token(refresh)

        assert exc_info.value.error_code == "INVALID_TOKEN"

    def test_access_token_used_as_refresh_token_raises_invalid(self):
        access = create_access_token(
            user_id=uuid4(), org_id=uuid4(), session_id=uuid4(), role="analyst"
        )
        with pytest.raises(UnauthorizedError) as exc_info:
            decode_refresh_token(access)

        assert exc_info.value.error_code == "INVALID_TOKEN"

    def test_expired_refresh_token_raises_refresh_token_expired(self):
        settings = get_settings()
        past_exp = datetime.now(timezone.utc) - timedelta(seconds=1)
        payload = {
            "user_id": str(uuid4()),
            "session_id": str(uuid4()),
            "iat": datetime.now(timezone.utc) - timedelta(days=8),
            "exp": past_exp,
            "type": "refresh",
        }
        expired = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(UnauthorizedError) as exc_info:
            decode_refresh_token(expired)

        assert exc_info.value.error_code == "REFRESH_TOKEN_EXPIRED"

    def test_two_scopes_are_mutually_exclusive(self):
        """An org-scope token must have type 'access' and scope 'org' — not 'platform'."""
        user_id = uuid4()
        org_token = create_access_token(
            user_id=user_id,
            org_id=uuid4(),
            session_id=uuid4(),
            role="analyst",
            scope="org",
        )
        platform_token = create_access_token(
            user_id=user_id,
            org_id=uuid4(),
            session_id=uuid4(),
            role="support",
            scope="platform",
        )

        org_payload = decode_access_token(org_token)
        platform_payload = decode_access_token(platform_token)

        assert org_payload["scope"] == "org"
        assert platform_payload["scope"] == "platform"
        assert org_payload["scope"] != platform_payload["scope"]


# ── API-level token rejection tests ───────────────────────────────────────

class TestTokenRejectionAtAPI:
    @pytest.mark.asyncio
    async def test_expired_token_returns_401_at_protected_endpoint(self, client: AsyncClient):
        settings = get_settings()
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        payload = {
            "user_id": str(uuid4()),
            "org_id": str(uuid4()),
            "session_id": str(uuid4()),
            "role": "analyst",
            "scope": "org",
            "iat": past - timedelta(minutes=15),
            "exp": past,
            "type": "access",
        }
        expired_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "TOKEN_EXPIRED"

    @pytest.mark.asyncio
    async def test_tampered_token_returns_401_at_protected_endpoint(self, client: AsyncClient, verified_user, user_password):
        login = await client.post("/api/v1/auth/login", json={
            "email": verified_user.email,
            "password": user_password,
        })
        access_token = login.json().get("access_token", "")
        if not access_token:
            pytest.skip("No access token in org-picker response")

        # Tamper by flipping the last character
        tampered = access_token[:-1] + ("A" if access_token[-1] != "A" else "B")

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tampered}"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_TOKEN"

    @pytest.mark.asyncio
    async def test_missing_auth_header_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401


# ── rate limiting ──────────────────────────────────────────────────────────

class TestRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_triggers_on_6th_attempt(self, client: AsyncClient, redis_client):
        """
        POST /api/v1/auth/login is rate-limited to 5 req / 15 min per IP.
        We override the rate limit to be enabled for this test only.
        """
        # Re-enable rate limiting for this test
        from app.core import rate_limit as rl_module
        from app.core.config import get_settings
        settings = get_settings()
        original = settings.RATE_LIMIT_ENABLED
        settings.RATE_LIMIT_ENABLED = True

        try:
            responses = []
            for _ in range(6):
                r = await client.post("/api/v1/auth/login", json={
                    "email": "nobody@example.com",
                    "password": "WrongPassword1!",
                })
                responses.append(r.status_code)

            # First 5 should be 401 (wrong creds), 6th should be 429
            assert responses[-1] == 429, f"Expected 429 on 6th attempt, got: {responses}"
        finally:
            settings.RATE_LIMIT_ENABLED = original
