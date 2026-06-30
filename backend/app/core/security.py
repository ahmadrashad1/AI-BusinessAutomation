import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, ExpiredSignatureError, jwt

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError


# ── password hashing ──────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return a bcrypt hash (cost 12) of the plaintext password."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison of plaintext against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── random token generation & hashing ─────────────────────────────────────

def generate_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure URL-safe random token (hex string)."""
    return secrets.token_hex(nbytes)


def hash_token(plain: str) -> str:
    """SHA-256 hash of a plaintext token. Used to store email/reset tokens safely."""
    return hashlib.sha256(plain.encode()).hexdigest()


# ── symmetric encryption (Fernet / AES-128-CBC + HMAC-SHA256) ─────────────

def _get_fernet() -> Fernet:
    settings = get_settings()
    # Fernet requires a URL-safe base64-encoded 32-byte key.
    # In dev the key is a base64 placeholder; production uses a real derived key.
    key = settings.ENCRYPTION_KEY.encode()
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    """AES encrypt a plaintext secret for storage. Returns a Fernet token string."""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted secret. Raises UnauthorizedError on tampered data."""
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise UnauthorizedError("INVALID_TOKEN", "Encrypted value is invalid or tampered.") from exc


# ── JWT ───────────────────────────────────────────────────────────────────

def create_access_token(
    *,
    user_id: UUID,
    org_id: UUID,
    session_id: UUID,
    role: str,
    scope: str = "org",
) -> str:
    """Create a signed access token (15-minute lifetime)."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": str(user_id),
        "org_id": str(org_id),
        "session_id": str(session_id),
        "role": role,
        "scope": scope,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(*, user_id: UUID, session_id: UUID) -> str:
    """Create a signed refresh token (7-day lifetime). Stored hash in Redis for rotation."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": str(user_id),
        "session_id": str(session_id),
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate an access token.
    Raises UnauthorizedError with a specific error_code on any failure.
    """
    settings = get_settings()
    try:
        payload: dict = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise UnauthorizedError("TOKEN_EXPIRED", "Access token has expired.")
    except JWTError:
        raise UnauthorizedError("INVALID_TOKEN", "Access token is invalid or tampered.")

    if payload.get("type") != "access":
        raise UnauthorizedError("INVALID_TOKEN", "Token type mismatch.")

    return payload


def decode_refresh_token(token: str) -> dict:
    """
    Decode and validate a refresh token structure.
    Raises UnauthorizedError on failure.
    """
    settings = get_settings()
    try:
        payload: dict = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise UnauthorizedError("REFRESH_TOKEN_EXPIRED", "Refresh token has expired.")
    except JWTError:
        raise UnauthorizedError("INVALID_TOKEN", "Refresh token is invalid.")

    if payload.get("type") != "refresh":
        raise UnauthorizedError("INVALID_TOKEN", "Token type mismatch.")

    return payload


def redis_session_key(user_id: str | UUID, session_id: str | UUID) -> str:
    return f"session:{user_id}:{session_id}"
