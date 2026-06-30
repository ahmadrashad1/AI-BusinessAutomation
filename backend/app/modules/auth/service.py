"""
Auth service — all business logic for authentication.

Rules:
- All functions are async.
- No HTTP concerns (no Request, no Response, no status codes).
- All errors raised as AppException subclasses from core/exceptions.py.
- organization_id always comes from the JWT / service parameters, never from request body.
- Tokens are always SHA-256 hashed before storage.
"""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    UnprocessableError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_token,
    hash_password,
    hash_token,
    redis_session_key,
    verify_password,
)
from app.modules.auth.models import (
    EmailVerificationToken,
    PasswordResetToken,
    User,
)
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    MessageResponse,
    OrganizationBrief,
    RefreshResponse,
    RegisterRequest,
    UserResponse,
)

logger = logging.getLogger(__name__)

# ── email stub ─────────────────────────────────────────────────────────────
# In production this delegates to a Celery task that calls SendGrid.
# In development it logs the token so tests can capture it.


async def send_verification_email(email: str, token: str) -> None:
    logger.info("send_verification_email to=%s token=%s", email, token)


async def send_password_reset_email(email: str, token: str) -> None:
    logger.info("send_password_reset_email to=%s token=%s", email, token)


# ── helpers ────────────────────────────────────────────────────────────────

async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(func.lower(User.email) == email.lower())
    )
    return result.scalar_one_or_none()


async def _get_user_memberships(db: AsyncSession, user_id: UUID) -> list[dict]:
    """
    Load org memberships for a user. Returns a list of dicts containing
    org_id, role, and the Organization ORM object.

    This stub returns an empty list until the organizations module exists.
    It is patched in tests that require org context.
    """
    # Import inline to avoid circular dependency before the organizations module exists
    try:
        from app.modules.organizations.models import OrgMember, Organization

        result = await db.execute(
            select(OrgMember, Organization)
            .join(Organization, OrgMember.organization_id == Organization.id)
            .where(OrgMember.user_id == user_id)
            .where(Organization.is_active == True)  # noqa: E712
        )
        rows = result.all()
        return [{"org_id": m.organization_id, "role": m.role, "org": o} for m, o in rows]
    except (ImportError, Exception):
        return []


async def _accept_invitation(db: AsyncSession, token: str, user_id: UUID) -> bool:
    """
    Accept a pending org invitation. Returns True if the invitation was valid
    and accepted, False otherwise.

    This stub always returns False until the organizations module exists.
    """
    try:
        from app.modules.organizations.models import Invitation, OrgMember

        plain_token = token
        token_h = hash_token(plain_token)
        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(Invitation)
            .where(Invitation.token_hash == token_h)
            .where(Invitation.accepted_at.is_(None))
            .where(Invitation.expires_at > now)
        )
        inv = result.scalar_one_or_none()
        if inv is None:
            return False

        member = OrgMember(organization_id=inv.organization_id, user_id=user_id, role=inv.role)
        db.add(member)
        inv.accepted_at = now
        await db.flush()
        return True
    except (ImportError, Exception):
        return False


async def _store_refresh_token(redis: aioredis.Redis, user_id: UUID, session_id: UUID, token: str) -> None:
    """Store the SHA-256 hash of a refresh token in Redis with 7-day TTL."""
    from app.core.config import get_settings

    settings = get_settings()
    key = redis_session_key(user_id, session_id)
    token_hash = hash_token(token)
    ttl = int(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
    await redis.set(key, token_hash, ex=ttl)


# ── register ───────────────────────────────────────────────────────────────

async def register(db: AsyncSession, redis: aioredis.Redis, body: RegisterRequest) -> UserResponse:
    existing = await _get_user_by_email(db, body.email)
    if existing is not None:
        raise ConflictError("An account with this email address already exists.")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        is_verified=False,
        is_active=True,
    )
    db.add(user)
    await db.flush()  # populate user.id

    invitation_accepted = False
    if body.invite_token:
        invitation_accepted = await _accept_invitation(db, body.invite_token, user.id)

    if invitation_accepted:
        user.is_verified = True
    else:
        # Issue email verification token
        plain = generate_token()
        evt = EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(plain),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(evt)
        await db.flush()
        await send_verification_email(user.email, plain)

    return UserResponse.model_validate(user)


# ── login ──────────────────────────────────────────────────────────────────

async def login(db: AsyncSession, redis: aioredis.Redis, body: LoginRequest) -> LoginResponse:
    user = await _get_user_by_email(db, body.email)

    # Use constant-time comparison even when user is None to prevent timing attacks
    dummy_hash = "$2b$12$" + "x" * 53
    candidate_hash = user.hashed_password if (user and user.hashed_password) else dummy_hash
    password_ok = verify_password(body.password, candidate_hash)

    if user is None or not password_ok:
        raise UnauthorizedError("INVALID_CREDENTIALS", "Invalid email or password.")

    if not user.is_active:
        raise UnauthorizedError("ACCOUNT_DISABLED", "This account has been disabled.")

    if not user.is_verified:
        raise UnauthorizedError("EMAIL_NOT_VERIFIED", "Please verify your email before logging in.")

    memberships = await _get_user_memberships(db, user.id)

    # If user belongs to multiple orgs and no org_id provided, return org list for client to choose
    if not body.org_id and len(memberships) > 1:
        return LoginResponse(
            access_token="",
            user=UserResponse.model_validate(user),
            organizations=[OrganizationBrief.model_validate(m["org"]) for m in memberships],
        )

    # Resolve the target org membership
    if body.org_id:
        membership = next((m for m in memberships if str(m["org_id"]) == str(body.org_id)), None)
        if membership is None:
            raise UnauthorizedError("INVALID_CREDENTIALS", "User is not a member of the requested organization.")
    elif len(memberships) == 1:
        membership = memberships[0]
    else:
        membership = None  # No org yet — allowed; access token has no org_id

    session_id = uuid4()

    if membership:
        org = membership["org"]
        if not getattr(org, "is_active", True):
            raise UnauthorizedError("ORG_SUSPENDED", "This organization has been suspended.")

        access_token = create_access_token(
            user_id=user.id,
            org_id=membership["org_id"],
            session_id=session_id,
            role=membership["role"],
        )
        refresh_token = create_refresh_token(user_id=user.id, session_id=session_id)
        await _store_refresh_token(redis, user.id, session_id, refresh_token)

        return LoginResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user),
            organization=OrganizationBrief.model_validate(org),
            role=membership["role"],
        ), refresh_token  # type: ignore[return-value]
    else:
        # User with no org — issue a limited access token (org_id="")
        access_token = create_access_token(
            user_id=user.id,
            org_id=uuid4(),  # placeholder; UI redirects to org creation
            session_id=session_id,
            role="owner",
        )
        refresh_token = create_refresh_token(user_id=user.id, session_id=session_id)
        await _store_refresh_token(redis, user.id, session_id, refresh_token)
        return LoginResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user),
        ), refresh_token  # type: ignore[return-value]


# ── refresh ────────────────────────────────────────────────────────────────

async def refresh(db: AsyncSession, redis: aioredis.Redis, refresh_token: str) -> tuple[RefreshResponse, str]:
    """
    Rotate the refresh token. Returns (RefreshResponse, new_refresh_token).
    Raises UnauthorizedError(REFRESH_TOKEN_REUSED) if the token was already used.
    """
    from app.core.security import decode_refresh_token

    payload = decode_refresh_token(refresh_token)
    user_id = payload["user_id"]
    session_id = payload["session_id"]

    # Atomically get-and-delete — if nil, token was already rotated (replay attack)
    stored_hash = await redis.getdel(redis_session_key(user_id, session_id))
    if stored_hash is None:
        raise UnauthorizedError("REFRESH_TOKEN_REUSED", "Refresh token has already been used or was revoked.")

    # Verify hash matches (defence in depth — should always match if token is legitimate)
    if stored_hash != hash_token(refresh_token):
        raise UnauthorizedError("REFRESH_TOKEN_REUSED", "Refresh token hash mismatch.")

    # Load the user to confirm they are still active
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError("ACCOUNT_DISABLED", "Account is disabled.")

    memberships = await _get_user_memberships(db, user.id)
    membership = memberships[0] if memberships else None

    new_session_id = uuid4()

    if membership:
        access_token = create_access_token(
            user_id=user.id,
            org_id=membership["org_id"],
            session_id=new_session_id,
            role=membership["role"],
        )
    else:
        access_token = create_access_token(
            user_id=user.id,
            org_id=uuid4(),
            session_id=new_session_id,
            role="owner",
        )

    new_refresh = create_refresh_token(user_id=user.id, session_id=new_session_id)
    await _store_refresh_token(redis, user.id, new_session_id, new_refresh)

    return RefreshResponse(access_token=access_token), new_refresh


# ── logout ─────────────────────────────────────────────────────────────────

async def logout(redis: aioredis.Redis, *, user_id: UUID, session_id: UUID) -> None:
    await redis.delete(redis_session_key(user_id, session_id))


# ── me ─────────────────────────────────────────────────────────────────────

async def me(db: AsyncSession, user_id: UUID, org_id: UUID | None) -> MeResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError("ACCOUNT_DISABLED", "Account not found or disabled.")

    user_resp = UserResponse.model_validate(user)

    if org_id is None:
        return MeResponse(user=user_resp)

    memberships = await _get_user_memberships(db, user_id)
    membership = next((m for m in memberships if str(m["org_id"]) == str(org_id)), None)
    if membership is None:
        return MeResponse(user=user_resp)

    org = membership["org"]
    return MeResponse(
        user=user_resp,
        organization=OrganizationBrief.model_validate(org),
        role=membership["role"],
    )


# ── verify email ───────────────────────────────────────────────────────────

async def verify_email(db: AsyncSession, token: str) -> None:
    token_hash = hash_token(token)
    result = await db.execute(
        select(EmailVerificationToken)
        .options(selectinload(EmailVerificationToken.user))
        .where(EmailVerificationToken.token_hash == token_hash)
        .where(EmailVerificationToken.used_at.is_(None))
    )
    evt = result.scalar_one_or_none()
    if evt is None:
        raise NotFoundError("Verification token is invalid or has already been used.")

    if evt.expires_at < datetime.now(timezone.utc):
        raise UnprocessableError("Verification token has expired. Please request a new one.")

    evt.user.is_verified = True
    evt.used_at = datetime.now(timezone.utc)
    await db.flush()


# ── resend verification ────────────────────────────────────────────────────

async def resend_verification(db: AsyncSession, email: str) -> None:
    """Always returns success — never confirms whether the email exists (prevents enumeration)."""
    user = await _get_user_by_email(db, email)
    if user is None or user.is_verified:
        return  # silent no-op

    # Invalidate any prior unused tokens for this user
    from sqlalchemy import update as sa_update

    await db.execute(
        sa_update(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id)
        .where(EmailVerificationToken.used_at.is_(None))
        .values(used_at=datetime.now(timezone.utc))
    )

    plain = generate_token()
    evt = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_token(plain),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(evt)
    await db.flush()
    await send_verification_email(user.email, plain)


# ── forgot password ────────────────────────────────────────────────────────

async def forgot_password(db: AsyncSession, email: str) -> None:
    """Always returns success — prevents email enumeration."""
    user = await _get_user_by_email(db, email)
    if user is None or not user.is_active:
        return

    # Invalidate previous reset tokens for this user
    from sqlalchemy import update as sa_update

    await db.execute(
        sa_update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id)
        .where(PasswordResetToken.used_at.is_(None))
        .values(used_at=datetime.now(timezone.utc))
    )

    plain = generate_token()
    prt = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(plain),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(prt)
    await db.flush()
    await send_password_reset_email(user.email, plain)


# ── reset password ─────────────────────────────────────────────────────────

async def reset_password(db: AsyncSession, redis: aioredis.Redis, token: str, new_password: str) -> None:
    token_hash = hash_token(token)
    result = await db.execute(
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.user))
        .where(PasswordResetToken.token_hash == token_hash)
        .where(PasswordResetToken.used_at.is_(None))
    )
    prt = result.scalar_one_or_none()
    if prt is None:
        raise NotFoundError("Reset token is invalid or has already been used.")

    if prt.expires_at < datetime.now(timezone.utc):
        raise UnprocessableError("Reset token has expired. Please request a new password reset.")

    prt.user.hashed_password = hash_password(new_password)
    prt.used_at = datetime.now(timezone.utc)
    await db.flush()

    # Invalidate ALL active sessions for this user
    async for key in redis.scan_iter(f"session:{prt.user_id}:*"):
        await redis.delete(key)
