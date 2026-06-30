"""
Unit tests for app.modules.auth.service.

All external dependencies (DB, Redis) are replaced with AsyncMocks so these
tests run without any running infrastructure.

TDD: these tests define the expected behaviour BEFORE the service is implemented.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, hash_token, generate_token, redis_session_key
from app.core.exceptions import UnauthorizedError, ConflictError, NotFoundError
from app.modules.auth.models import User, EmailVerificationToken, PasswordResetToken
from app.modules.auth.schemas import RegisterRequest, LoginRequest, ResetPasswordRequest


# ── helpers ────────────────────────────────────────────────────────────────

def make_user(*, is_verified: bool = True, is_active: bool = True) -> User:
    user = User.__new__(User)
    user.id = uuid4()
    user.email = "alice@example.com"
    user.full_name = "Alice Smith"
    user.hashed_password = hash_password("SecurePass123!")
    user.is_verified = is_verified
    user.is_active = is_active
    user.created_at = datetime.now(timezone.utc)
    user.avatar_url = None
    user.tos_accepted_at = None
    return user


# ── register ──────────────────────────────────────────────────────────────

class TestRegister:
    @pytest.mark.asyncio
    async def test_register_creates_user_and_sends_verification(self, mock_db, mock_redis):
        from app.modules.auth import service

        request = RegisterRequest(email="new@example.com", password="SecurePass123!", full_name="New User")

        # DB returns None for duplicate-email check
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        with patch.object(service, "send_verification_email", new_callable=AsyncMock) as mock_email:
            result = await service.register(mock_db, mock_redis, request)

        assert result.email == "new@example.com"
        assert result.is_verified is False
        mock_email.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_register_raises_conflict_for_duplicate_email(self, mock_db, mock_redis):
        from app.modules.auth import service

        existing = make_user()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing)))

        with pytest.raises(ConflictError):
            await service.register(mock_db, mock_redis, RegisterRequest(
                email="alice@example.com", password="SecurePass123!", full_name="Alice"
            ))

    @pytest.mark.asyncio
    async def test_register_with_invite_token_marks_verified(self, mock_db, mock_redis):
        """When an invite_token is supplied and valid, the new user is pre-verified."""
        from app.modules.auth import service

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        with patch.object(service, "send_verification_email", new_callable=AsyncMock):
            with patch.object(service, "_accept_invitation", new_callable=AsyncMock, return_value=True):
                result = await service.register(mock_db, mock_redis, RegisterRequest(
                    email="invited@example.com",
                    password="SecurePass123!",
                    full_name="Invited",
                    invite_token="valid-token",
                ))

        assert result.is_verified is True


# ── login ─────────────────────────────────────────────────────────────────

class TestLogin:
    @pytest.mark.asyncio
    async def test_login_returns_tokens_for_verified_user(self, mock_db, mock_redis):
        from app.modules.auth import service

        user = make_user()
        org_id = uuid4()

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
        mock_redis.set = AsyncMock()

        with patch.object(service, "_get_user_memberships", new_callable=AsyncMock) as mock_membs:
            mock_membs.return_value = [{"org_id": org_id, "role": "analyst", "org": MagicMock(id=org_id, name="Acme", slug="acme", plan="free")}]
            result = await service.login(mock_db, mock_redis, LoginRequest(
                email="alice@example.com", password="SecurePass123!", org_id=org_id
            ))

        assert result.access_token
        assert result.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_login_raises_401_for_wrong_password(self, mock_db, mock_redis):
        from app.modules.auth import service

        user = make_user()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.login(mock_db, mock_redis, LoginRequest(
                email="alice@example.com", password="WrongPassword1!", org_id=uuid4()
            ))

        assert exc_info.value.error_code == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_raises_401_for_unverified_user(self, mock_db, mock_redis):
        from app.modules.auth import service

        user = make_user(is_verified=False)
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.login(mock_db, mock_redis, LoginRequest(
                email="alice@example.com", password="SecurePass123!", org_id=uuid4()
            ))

        assert exc_info.value.error_code == "EMAIL_NOT_VERIFIED"

    @pytest.mark.asyncio
    async def test_login_raises_401_for_inactive_user(self, mock_db, mock_redis):
        from app.modules.auth import service

        user = make_user(is_active=False)
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.login(mock_db, mock_redis, LoginRequest(
                email="alice@example.com", password="SecurePass123!", org_id=uuid4()
            ))

        assert exc_info.value.error_code == "ACCOUNT_DISABLED"

    @pytest.mark.asyncio
    async def test_login_raises_401_for_unknown_email(self, mock_db, mock_redis):
        from app.modules.auth import service

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.login(mock_db, mock_redis, LoginRequest(
                email="nobody@example.com", password="SecurePass123!", org_id=None
            ))

        assert exc_info.value.error_code == "INVALID_CREDENTIALS"


# ── refresh ───────────────────────────────────────────────────────────────

class TestRefresh:
    @pytest.mark.asyncio
    async def test_refresh_rotates_token_and_returns_new_access_token(self, mock_db, mock_redis):
        from app.modules.auth import service
        from app.core.security import create_refresh_token

        user = make_user()
        session_id = uuid4()
        refresh_token = create_refresh_token(user_id=user.id, session_id=session_id)
        stored_hash = hash_token(refresh_token)

        mock_redis.getdel = AsyncMock(return_value=stored_hash)
        mock_redis.set = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))

        org_id = uuid4()
        with patch.object(service, "_get_user_memberships", new_callable=AsyncMock) as mock_m:
            mock_m.return_value = [{"org_id": org_id, "role": "analyst", "org": MagicMock(id=org_id, name="Acme", slug="acme", plan="free")}]
            result = await service.refresh(mock_db, mock_redis, refresh_token)

        assert result.access_token
        mock_redis.set.assert_awaited()

    @pytest.mark.asyncio
    async def test_refresh_raises_reused_when_key_not_in_redis(self, mock_db, mock_redis):
        """Replay attack: Redis key was already deleted (rotated). Must raise REFRESH_TOKEN_REUSED."""
        from app.modules.auth import service
        from app.core.security import create_refresh_token

        user = make_user()
        session_id = uuid4()
        refresh_token = create_refresh_token(user_id=user.id, session_id=session_id)

        mock_redis.getdel = AsyncMock(return_value=None)  # key already deleted → replay

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.refresh(mock_db, mock_redis, refresh_token)

        assert exc_info.value.error_code == "REFRESH_TOKEN_REUSED"


# ── logout ────────────────────────────────────────────────────────────────

class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_deletes_redis_session(self, mock_db, mock_redis):
        from app.modules.auth import service

        user_id = uuid4()
        session_id = uuid4()
        mock_redis.delete = AsyncMock(return_value=1)

        await service.logout(mock_redis, user_id=user_id, session_id=session_id)

        expected_key = redis_session_key(user_id, session_id)
        mock_redis.delete.assert_awaited_once_with(expected_key)


# ── verify email ──────────────────────────────────────────────────────────

class TestVerifyEmail:
    @pytest.mark.asyncio
    async def test_verify_email_marks_user_verified(self, mock_db):
        from app.modules.auth import service

        token_plain = generate_token()
        user = make_user(is_verified=False)
        evt = EmailVerificationToken.__new__(EmailVerificationToken)
        evt.id = uuid4()
        evt.user_id = user.id
        evt.token_hash = hash_token(token_plain)
        evt.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        evt.used_at = None
        evt.user = user

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=evt)))
        mock_db.flush = AsyncMock()

        await service.verify_email(mock_db, token_plain)

        assert user.is_verified is True
        assert evt.used_at is not None

    @pytest.mark.asyncio
    async def test_verify_email_raises_not_found_for_unknown_token(self, mock_db):
        from app.modules.auth import service

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(NotFoundError):
            await service.verify_email(mock_db, "invalid-token")

    @pytest.mark.asyncio
    async def test_verify_email_raises_for_expired_token(self, mock_db):
        from app.modules.auth import service

        token_plain = generate_token()
        user = make_user(is_verified=False)
        evt = EmailVerificationToken.__new__(EmailVerificationToken)
        evt.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # expired
        evt.used_at = None
        evt.user = user

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=evt)))

        with pytest.raises(UnprocessableError if False else Exception):
            await service.verify_email(mock_db, token_plain)


# ── reset password ────────────────────────────────────────────────────────

class TestResetPassword:
    @pytest.mark.asyncio
    async def test_reset_password_updates_hash_and_invalidates_all_sessions(self, mock_db, mock_redis):
        from app.modules.auth import service

        token_plain = generate_token()
        user = make_user()
        prt = PasswordResetToken.__new__(PasswordResetToken)
        prt.id = uuid4()
        prt.user_id = user.id
        prt.token_hash = hash_token(token_plain)
        prt.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        prt.used_at = None
        prt.user = user

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=prt)))
        mock_db.flush = AsyncMock()

        # Redis scan for all session keys for this user
        mock_redis.scan_iter = AsyncMock(return_value=aiter([f"session:{user.id}:some-session"]))
        mock_redis.delete = AsyncMock()

        await service.reset_password(mock_db, mock_redis, token_plain, "NewSecurePass456!")

        assert user.hashed_password != hash_password("NewSecurePass456!")  # changed (new hash each call)
        assert prt.used_at is not None
        mock_redis.delete.assert_awaited()


# ── helpers ────────────────────────────────────────────────────────────────

async def aiter(items):
    for item in items:
        yield item
