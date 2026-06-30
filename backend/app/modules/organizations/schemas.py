import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,98}[a-z0-9]$")

ASSIGNABLE_ROLES = ("admin", "manager", "analyst", "employee", "viewer")
VALID_SCOPES = {
    "workflow:read",
    "workflow:execute",
    "analytics:read",
    "reports:read",
}


# ── Organization ───────────────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str
    slug: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank.")
        if len(v) > 255:
            raise ValueError("name must be 255 characters or fewer.")
        return v

    @field_validator("slug")
    @classmethod
    def slug_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not _SLUG_RE.match(v):
            raise ValueError("slug must be 3-100 lowercase alphanumeric characters and hyphens.")
        return v


class OrgUpdate(BaseModel):
    name: str | None = None
    plan: str | None = None
    is_active: bool | None = None
    settings: dict | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("name must not be blank.")
        return v


class OrgResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    plan: str
    is_active: bool
    settings: dict
    storage_used_bytes: int
    created_at: datetime
    updated_at: datetime


class DeleteOrgRequest(BaseModel):
    confirmation: str


class TransferOwnershipRequest(BaseModel):
    new_owner_user_id: UUID


# ── Members ────────────────────────────────────────────────────────────────────

class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    user_id: UUID
    role: str
    department_id: UUID | None = None
    joined_at: datetime


class MemberUpdate(BaseModel):
    role: str
    department_id: UUID | None = None

    @field_validator("role")
    @classmethod
    def role_not_owner(cls, v: str) -> str:
        if v not in ASSIGNABLE_ROLES:
            raise ValueError(
                f"role must be one of: {', '.join(ASSIGNABLE_ROLES)}. "
                "Use transfer-ownership to change the owner."
            )
        return v


# ── Departments ────────────────────────────────────────────────────────────────

class DepartmentCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank.")
        return v


class DepartmentUpdate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank.")
        return v


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    created_at: datetime


# ── Invitations ────────────────────────────────────────────────────────────────

class InvitationCreate(BaseModel):
    email: EmailStr
    role: str

    @field_validator("role")
    @classmethod
    def role_not_owner(cls, v: str) -> str:
        if v not in ASSIGNABLE_ROLES:
            raise ValueError(f"Cannot invite to role '{v}'. Valid roles: {', '.join(ASSIGNABLE_ROLES)}.")
        return v


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    email: str
    role: str
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime


class AcceptInvitationRequest(BaseModel):
    token: str


class AcceptInvitationResponse(BaseModel):
    organization: OrgResponse
    role: str


# ── API Keys ───────────────────────────────────────────────────────────────────

class APIKeyCreate(BaseModel):
    label: str
    scopes: list[str]
    expires_at: datetime | None = None

    @field_validator("label")
    @classmethod
    def label_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("label must not be blank.")
        return v

    @field_validator("scopes")
    @classmethod
    def valid_scopes(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_SCOPES
        if invalid:
            raise ValueError(f"Unknown scopes: {invalid}. Valid: {VALID_SCOPES}")
        if not v:
            raise ValueError("At least one scope is required.")
        return v


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    label: str
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class APIKeyCreatedResponse(APIKeyResponse):
    """Returned once on creation — includes the plaintext key (never stored)."""
    key: str
