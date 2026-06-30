import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


# ── password validation ────────────────────────────────────────────────────

_PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")


def validate_password_strength(v: str) -> str:
    if not _PASSWORD_RE.match(v):
        raise ValueError(
            "Password must be at least 8 characters and contain at least one uppercase letter, "
            "one lowercase letter, and one digit."
        )
    return v


# ── request schemas ────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    invite_token: str | None = None

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("full_name must not be blank.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    org_id: UUID | None = None


class RefreshRequest(BaseModel):
    """Body is empty; refresh token arrives via HttpOnly cookie."""


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validate_password_strength(v)


# ── response schemas ───────────────────────────────────────────────────────

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    avatar_url: str | None = None
    is_verified: bool
    created_at: datetime


class OrganizationBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    plan: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900
    user: UserResponse
    organization: OrganizationBrief | None = None
    role: str | None = None
    # Returned only when the user belongs to multiple orgs and no org_id was given
    organizations: list[OrganizationBrief] | None = None


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserResponse
    organization: OrganizationBrief | None = None
    role: str | None = None
    department: dict | None = None


class MessageResponse(BaseModel):
    message: str
