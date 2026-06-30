"""
FastAPI dependency functions for auth.

Dependency chain:
    get_db()  →  get_current_user()  →  require_verified_email()
                 ↓
              get_current_member()   →  require_role(...)
"""
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.modules.auth.models import User


async def _bearer_token(request: Request) -> str:
    """Extract the raw JWT from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise UnauthorizedError("UNAUTHORIZED", "Missing or invalid Authorization header.")
    token = auth[7:]
    if not token:
        raise UnauthorizedError("UNAUTHORIZED", "Missing token.")
    return token


async def get_current_user(
    token: str = Depends(_bearer_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate the access token and return the User ORM object.

    Raises UnauthorizedError for expired, tampered, or missing tokens,
    or if the user no longer exists / is inactive.
    """
    payload = decode_access_token(token)
    user_id: str = payload.get("user_id", "")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise UnauthorizedError("ACCOUNT_DISABLED", "Account not found or disabled.")

    # Attach the full token payload so downstream deps can read scope/session_id
    user._token_payload = payload  # type: ignore[attr-defined]
    return user


async def require_verified_email(
    user: User = Depends(get_current_user),
) -> User:
    """Extend get_current_user — additionally require that the user's email is verified."""
    if not user.is_verified:
        raise UnauthorizedError("EMAIL_NOT_VERIFIED", "Please verify your email address before using this feature.")
    return user


def require_scope(scope: str):
    """Dependency factory: ensures the token carries the required scope ('org' or 'platform')."""
    async def _check(user: User = Depends(get_current_user)) -> User:
        token_scope = getattr(user, "_token_payload", {}).get("scope")
        if token_scope != scope:
            raise UnauthorizedError("FORBIDDEN", f"This endpoint requires {scope!r} scope.")
        return user
    return _check


def require_role(*roles: str):
    """
    Dependency factory: ensures the token role is in the allowed list.
    Must be used after get_current_user.
    """
    async def _check(user: User = Depends(get_current_user)) -> User:
        token_role = getattr(user, "_token_payload", {}).get("role")
        if token_role not in roles:
            raise UnauthorizedError("FORBIDDEN", f"This endpoint requires one of roles: {roles}.")
        return user
    return _check
