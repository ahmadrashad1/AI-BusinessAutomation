"""
Auth router — all HTTP concerns live here. No business logic.

All endpoints are under the prefix /api/v1/auth (set in api/v1/router.py).
"""
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.rate_limit import check_rate_limit
from app.core.redis import get_redis
from app.modules.auth import service
from app.modules.auth.dependencies import get_current_user, require_verified_email
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    MessageResponse,
    RefreshResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
    VerifyEmailRequest,
    ResendVerificationRequest,
)

router = APIRouter(tags=["auth"])
settings = get_settings()

_REFRESH_COOKIE = "refresh_token"
_COOKIE_MAX_AGE = int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/api/v1/auth/refresh",
        max_age=_COOKIE_MAX_AGE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE, path="/api/v1/auth/refresh")


# ── POST /register ─────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await service.register(db, redis, body)


# ── POST /login ────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate and receive access + refresh tokens",
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(redis, key=f"login:{client_ip}", limit=5, window_seconds=900)

    result = await service.login(db, redis, body)

    # service.login returns (LoginResponse, refresh_token) for successful auth
    # and just LoginResponse (with empty access_token + organizations list) for org-picker
    if isinstance(result, tuple):
        login_response, refresh_token = result
        _set_refresh_cookie(response, refresh_token)
        return login_response

    return result  # org-picker path — no refresh token set yet


# ── POST /refresh ──────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Rotate refresh token and get a new access token",
)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    if not refresh_token:
        raise UnauthorizedError("UNAUTHORIZED", "Refresh token cookie is missing.")

    refresh_response, new_refresh_token = await service.refresh(db, redis, refresh_token)
    _set_refresh_cookie(response, new_refresh_token)
    return refresh_response


# ── POST /logout ───────────────────────────────────────────────────────────

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidate the current session",
)
async def logout(
    response: Response,
    user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    payload = getattr(user, "_token_payload", {})
    session_id = payload.get("session_id")
    if session_id:
        await service.logout(redis, user_id=user.id, session_id=UUID(session_id))
    _clear_refresh_cookie(response)


# ── GET /me ────────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=MeResponse,
    summary="Return the current user's profile and org membership",
)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = getattr(user, "_token_payload", {})
    org_id_str = payload.get("org_id")
    org_id = UUID(org_id_str) if org_id_str else None
    return await service.me(db, user.id, org_id)


# ── POST /verify-email ─────────────────────────────────────────────────────

@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify a user's email address using the token from the verification email",
)
async def verify_email(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    await service.verify_email(db, body.token)
    return MessageResponse(message="Email address verified successfully.")


# ── POST /resend-verification ──────────────────────────────────────────────

@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Resend the email verification link",
)
async def resend_verification(
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    await service.resend_verification(db, body.email)
    return MessageResponse(message="If that email is registered and unverified, a new link has been sent.")


# ── POST /forgot-password ──────────────────────────────────────────────────

@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset link",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await service.forgot_password(db, body.email)
    return MessageResponse(message="If that email is registered, a password reset link has been sent.")


# ── POST /reset-password ───────────────────────────────────────────────────

@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using the token from the reset email",
)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    await service.reset_password(db, redis, body.token, body.new_password)
    return MessageResponse(message="Password reset successfully. Please log in with your new password.")
