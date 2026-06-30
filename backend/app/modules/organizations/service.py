"""
Organizations service — all business logic.

Rules:
- `requesting_org_id` is always taken from the caller's JWT (never from request body)
- Cross-tenant access returns NotFoundError (404), not ForbiddenError (403)
- Caller cannot assign roles >= their own rank
- API key plaintext is returned once; only the hash is stored
"""
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import generate_token, hash_token
from app.modules.organizations.models import (
    APIKey,
    Department,
    Invitation,
    OrgMember,
    Organization,
    ROLE_RANK,
)
from app.modules.organizations.schemas import (
    APIKeyCreate,
    DepartmentCreate,
    DepartmentUpdate,
    InvitationCreate,
    MemberUpdate,
    OrgCreate,
    OrgUpdate,
)


_SLUG_STRIP_RE = re.compile(r"[^a-z0-9\-]+")
_MULTI_DASH_RE = re.compile(r"-{2,}")

INVITATION_TTL_HOURS = 48
API_KEY_PREFIX = "bpa_sk_"


# ── slug helper ────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    slug = name.lower().replace(" ", "-")
    slug = _SLUG_STRIP_RE.sub("", slug)
    slug = _MULTI_DASH_RE.sub("-", slug).strip("-")
    return slug[:100] or "org"


# ── Organization CRUD ──────────────────────────────────────────────────────────

async def create_org(db: AsyncSession, *, user_id: UUID, payload: OrgCreate) -> Organization:
    slug = payload.slug or _slugify(payload.name)

    result = await db.execute(select(Organization).where(Organization.slug == slug))
    if result.scalar_one_or_none():
        raise ConflictError(f"An organization with slug '{slug}' already exists.")

    org = Organization(
        name=payload.name,
        slug=slug,
        plan="free",
        is_active=True,
        settings={},
        storage_used_bytes=0,
    )
    db.add(org)
    await db.flush()

    member = OrgMember(organization_id=org.id, user_id=user_id, role="owner")
    db.add(member)
    await db.flush()

    return org


async def get_org(db: AsyncSession, *, org_id: UUID, requesting_org_id: UUID) -> Organization:
    if org_id != requesting_org_id:
        raise NotFoundError("Organization not found.")

    org = await db.get(Organization, org_id)
    if org is None:
        raise NotFoundError("Organization not found.")
    return org


async def update_org(
    db: AsyncSession,
    *,
    org_id: UUID,
    requesting_org_id: UUID,
    payload: OrgUpdate,
) -> Organization:
    org = await get_org(db, org_id=org_id, requesting_org_id=requesting_org_id)

    if payload.name is not None:
        org.name = payload.name
    if payload.plan is not None:
        org.plan = payload.plan
    if payload.is_active is not None:
        org.is_active = payload.is_active
    if payload.settings is not None:
        org.settings = payload.settings

    await db.flush()
    await db.refresh(org)
    return org


async def delete_org(
    db: AsyncSession,
    *,
    org_id: UUID,
    requesting_org_id: UUID,
    confirmation: str,
) -> None:
    org = await get_org(db, org_id=org_id, requesting_org_id=requesting_org_id)

    if confirmation != org.slug:
        raise ForbiddenError("CONFIRMATION_MISMATCH", "Confirmation must match the organization slug.")

    await db.delete(org)
    await db.flush()


# ── Members ────────────────────────────────────────────────────────────────────

async def list_members(
    db: AsyncSession, *, org_id: UUID, requesting_org_id: UUID
) -> list[OrgMember]:
    if org_id != requesting_org_id:
        raise NotFoundError("Organization not found.")

    result = await db.execute(select(OrgMember).where(OrgMember.organization_id == org_id))
    return list(result.scalars().all())


async def get_member(
    db: AsyncSession, *, org_id: UUID, user_id: UUID
) -> OrgMember:
    result = await db.execute(
        select(OrgMember).where(
            OrgMember.organization_id == org_id,
            OrgMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise NotFoundError("Member not found.")
    return member


async def update_member(
    db: AsyncSession,
    *,
    org_id: UUID,
    target_user_id: UUID,
    payload: MemberUpdate,
    caller_member: OrgMember,
) -> OrgMember:
    result = await db.execute(
        select(OrgMember).where(
            OrgMember.organization_id == org_id,
            OrgMember.user_id == target_user_id,
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise NotFoundError("Member not found.")

    # Caller cannot assign a role >= their own rank
    caller_rank = ROLE_RANK.get(caller_member.role, 0)
    new_rank = ROLE_RANK.get(payload.role, 0)
    if new_rank >= caller_rank:
        raise ForbiddenError("INSUFFICIENT_ROLE", "Cannot assign a role equal to or higher than your own.")

    target.role = payload.role
    if payload.department_id is not None:
        target.department_id = payload.department_id

    await db.flush()
    return target


async def remove_member(
    db: AsyncSession, *, org_id: UUID, target_user_id: UUID, caller_user_id: UUID
) -> None:
    result = await db.execute(
        select(OrgMember).where(
            OrgMember.organization_id == org_id,
            OrgMember.user_id == target_user_id,
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise NotFoundError("Member not found.")

    if target.role == "owner":
        raise ForbiddenError("CANNOT_REMOVE_OWNER", "Transfer ownership before removing the owner.")

    await db.delete(target)
    await db.flush()


async def transfer_ownership(
    db: AsyncSession,
    *,
    org_id: UUID,
    new_owner_user_id: UUID,
    caller_user_id: UUID,
) -> None:
    result = await db.execute(
        select(OrgMember).where(
            OrgMember.organization_id == org_id,
            OrgMember.user_id == caller_user_id,
        )
    )
    caller = result.scalar_one_or_none()

    result2 = await db.execute(
        select(OrgMember).where(
            OrgMember.organization_id == org_id,
            OrgMember.user_id == new_owner_user_id,
        )
    )
    new_owner = result2.scalar_one_or_none()
    if new_owner is None:
        raise NotFoundError("New owner must already be a member of this organization.")

    if caller:
        caller.role = "admin"
    new_owner.role = "owner"
    await db.flush()


# ── Invitations ────────────────────────────────────────────────────────────────

async def list_invitations(
    db: AsyncSession, *, org_id: UUID, requesting_org_id: UUID
) -> list[Invitation]:
    if org_id != requesting_org_id:
        raise NotFoundError("Organization not found.")

    result = await db.execute(
        select(Invitation).where(
            Invitation.organization_id == org_id,
            Invitation.accepted_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def invite_member(
    db: AsyncSession,
    *,
    org_id: UUID,
    invited_by: UUID,
    payload: InvitationCreate,
) -> tuple[Invitation, str]:
    # Check for pending invite
    result = await db.execute(
        select(Invitation).where(
            Invitation.organization_id == org_id,
            Invitation.email == str(payload.email),
            Invitation.accepted_at.is_(None),
        )
    )
    if result.scalar_one_or_none():
        raise ConflictError(f"A pending invitation for {payload.email} already exists.")

    plaintext = generate_token()
    token_hash = hash_token(plaintext)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITATION_TTL_HOURS)

    inv = Invitation(
        organization_id=org_id,
        invited_by=invited_by,
        email=str(payload.email),
        role=payload.role,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(inv)
    await db.flush()

    return inv, plaintext


async def revoke_invitation(
    db: AsyncSession, *, org_id: UUID, invitation_id: UUID, requesting_org_id: UUID
) -> None:
    if org_id != requesting_org_id:
        raise NotFoundError("Organization not found.")

    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.organization_id == org_id,
        )
    )
    inv = result.scalar_one_or_none()
    if inv is None:
        raise NotFoundError("Invitation not found.")

    await db.delete(inv)
    await db.flush()


async def accept_invitation(
    db: AsyncSession,
    *,
    token: str,
    user_id: UUID,
    user_email: str,
) -> tuple[Organization, str]:
    token_hash = hash_token(token)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Invitation).where(
            Invitation.token_hash == token_hash,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > now,
        )
    )
    inv = result.scalar_one_or_none()
    if inv is None:
        raise NotFoundError("Invitation not found or expired.")

    if inv.email.lower() != user_email.lower():
        raise ForbiddenError("EMAIL_MISMATCH", "This invitation was sent to a different email address.")

    # Check if already a member
    result2 = await db.execute(
        select(OrgMember).where(
            OrgMember.organization_id == inv.organization_id,
            OrgMember.user_id == user_id,
        )
    )
    if result2.scalar_one_or_none():
        raise ConflictError("You are already a member of this organization.")

    role = inv.role
    member = OrgMember(organization_id=inv.organization_id, user_id=user_id, role=role)
    db.add(member)

    inv.accepted_at = now
    await db.flush()

    org = await db.get(Organization, inv.organization_id)
    return org, role  # type: ignore[return-value]


# ── Departments ────────────────────────────────────────────────────────────────

async def list_departments(
    db: AsyncSession, *, org_id: UUID, requesting_org_id: UUID
) -> list[Department]:
    if org_id != requesting_org_id:
        raise NotFoundError("Organization not found.")

    result = await db.execute(
        select(Department).where(Department.organization_id == org_id)
    )
    return list(result.scalars().all())


async def create_department(
    db: AsyncSession,
    *,
    org_id: UUID,
    requesting_org_id: UUID,
    payload: DepartmentCreate,
) -> Department:
    if org_id != requesting_org_id:
        raise NotFoundError("Organization not found.")

    dept = Department(organization_id=org_id, name=payload.name)
    db.add(dept)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"A department named '{payload.name}' already exists in this organization.")
    return dept


async def update_department(
    db: AsyncSession,
    *,
    org_id: UUID,
    dept_id: UUID,
    requesting_org_id: UUID,
    payload: DepartmentUpdate,
) -> Department:
    if org_id != requesting_org_id:
        raise NotFoundError("Organization not found.")

    result = await db.execute(
        select(Department).where(
            Department.id == dept_id,
            Department.organization_id == org_id,
        )
    )
    dept = result.scalar_one_or_none()
    if dept is None:
        raise NotFoundError("Department not found.")

    dept.name = payload.name
    await db.flush()
    return dept


async def delete_department(
    db: AsyncSession, *, org_id: UUID, dept_id: UUID, requesting_org_id: UUID
) -> None:
    if org_id != requesting_org_id:
        raise NotFoundError("Organization not found.")

    result = await db.execute(
        select(Department).where(
            Department.id == dept_id,
            Department.organization_id == org_id,
        )
    )
    dept = result.scalar_one_or_none()
    if dept is None:
        raise NotFoundError("Department not found.")

    await db.delete(dept)
    await db.flush()


# ── API Keys ───────────────────────────────────────────────────────────────────

@dataclass
class APIKeyCreated:
    api_key: APIKey
    key: str
    key_prefix: str


async def list_api_keys(
    db: AsyncSession, *, org_id: UUID, requesting_org_id: UUID
) -> list[APIKey]:
    if org_id != requesting_org_id:
        raise NotFoundError("Organization not found.")

    result = await db.execute(
        select(APIKey).where(
            APIKey.organization_id == org_id,
            APIKey.revoked_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def create_api_key(
    db: AsyncSession,
    *,
    org_id: UUID,
    created_by: UUID,
    payload: APIKeyCreate,
) -> APIKeyCreated:
    raw = secrets.token_urlsafe(32)
    plaintext_key = f"{API_KEY_PREFIX}{raw}"
    key_hash = hash_token(plaintext_key)
    key_prefix = plaintext_key[:10]

    api_key = APIKey(
        organization_id=org_id,
        created_by=created_by,
        label=payload.label,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=payload.scopes,
        expires_at=payload.expires_at,
    )
    db.add(api_key)
    await db.flush()

    return APIKeyCreated(api_key=api_key, key=plaintext_key, key_prefix=key_prefix)


async def revoke_api_key(
    db: AsyncSession, *, org_id: UUID, key_id: UUID, requesting_org_id: UUID
) -> None:
    if org_id != requesting_org_id:
        raise NotFoundError("Organization not found.")

    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.organization_id == org_id,
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise NotFoundError("API key not found.")

    api_key.revoked_at = datetime.now(timezone.utc)
    await db.flush()


async def get_org_by_api_key(
    db: AsyncSession, *, plaintext_key: str
) -> tuple[APIKey, Organization]:
    """Used by API key authentication dependency."""
    key_hash = hash_token(plaintext_key)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.revoked_at.is_(None),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise NotFoundError("API key not found or revoked.")

    if api_key.expires_at and api_key.expires_at < now:
        raise NotFoundError("API key has expired.")

    org = await db.get(Organization, api_key.organization_id)
    if org is None or not org.is_active:
        raise NotFoundError("Organization not found or suspended.")

    # Record last use
    api_key.last_used_at = now
    await db.flush()

    return api_key, org
