"""
Organizations router — all 19 M2 endpoints.

Tenant isolation: org_id from JWT only (via require_org_member), never from body.
RBAC: require_org_role(min_role) enforces rank hierarchy.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.organizations.dependencies import require_org_member, require_org_role
from app.modules.organizations.models import OrgMember
from app.modules.organizations.schemas import (
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    APIKeyCreate,
    APIKeyCreatedResponse,
    APIKeyResponse,
    DeleteOrgRequest,
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    InvitationCreate,
    InvitationResponse,
    MemberResponse,
    MemberUpdate,
    OrgCreate,
    OrgResponse,
    OrgUpdate,
    TransferOwnershipRequest,
)
from app.modules.organizations import service

router = APIRouter(tags=["organizations"])


def _org_id_from_member(member: OrgMember) -> UUID:
    return member.organization_id


# ── Organization CRUD ──────────────────────────────────────────────────────────

@router.post("/orgs", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    payload: OrgCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    org = await service.create_org(db, user_id=user.id, payload=payload)
    await db.commit()
    return OrgResponse.model_validate(org)


@router.get("/orgs/{org_id}", response_model=OrgResponse)
async def get_org(
    org_id: UUID,
    member: OrgMember = Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    org = await service.get_org(db, org_id=org_id, requesting_org_id=_org_id_from_member(member))
    return OrgResponse.model_validate(org)


@router.patch("/orgs/{org_id}", response_model=OrgResponse)
async def update_org(
    org_id: UUID,
    payload: OrgUpdate,
    member: OrgMember = Depends(require_org_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    org = await service.update_org(
        db, org_id=org_id, requesting_org_id=_org_id_from_member(member), payload=payload
    )
    await db.commit()
    return OrgResponse.model_validate(org)


@router.delete("/orgs/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(
    org_id: UUID,
    payload: DeleteOrgRequest,
    member: OrgMember = Depends(require_org_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_org(
        db,
        org_id=org_id,
        requesting_org_id=_org_id_from_member(member),
        confirmation=payload.confirmation,
    )
    await db.commit()


# ── Ownership transfer ─────────────────────────────────────────────────────────

@router.post("/orgs/{org_id}/transfer-ownership", response_model=OrgResponse)
async def transfer_ownership(
    org_id: UUID,
    payload: TransferOwnershipRequest,
    member: OrgMember = Depends(require_org_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    await service.transfer_ownership(
        db,
        org_id=_org_id_from_member(member),
        new_owner_user_id=payload.new_owner_user_id,
        caller_user_id=member.user_id,
    )
    await db.commit()
    org = await service.get_org(db, org_id=org_id, requesting_org_id=_org_id_from_member(member))
    return OrgResponse.model_validate(org)


# ── Members ────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/members", response_model=list[MemberResponse])
async def list_members(
    org_id: UUID,
    member: OrgMember = Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
) -> list[MemberResponse]:
    members = await service.list_members(db, org_id=org_id, requesting_org_id=_org_id_from_member(member))
    return [MemberResponse.model_validate(m) for m in members]


@router.patch("/orgs/{org_id}/members/{user_id}", response_model=MemberResponse)
async def update_member(
    org_id: UUID,
    user_id: UUID,
    payload: MemberUpdate,
    caller: OrgMember = Depends(require_org_role("manager")),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    if org_id != _org_id_from_member(caller):
        raise NotFoundError("Organization not found.")

    updated = await service.update_member(
        db,
        org_id=org_id,
        target_user_id=user_id,
        payload=payload,
        caller_member=caller,
    )
    await db.commit()
    return MemberResponse.model_validate(updated)


@router.delete("/orgs/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    caller: OrgMember = Depends(require_org_role("manager")),
    db: AsyncSession = Depends(get_db),
) -> None:
    if org_id != _org_id_from_member(caller):
        raise NotFoundError("Organization not found.")

    await service.remove_member(
        db, org_id=org_id, target_user_id=user_id, caller_user_id=caller.user_id
    )
    await db.commit()


# ── Invitations ────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    org_id: UUID,
    member: OrgMember = Depends(require_org_role("manager")),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationResponse]:
    invitations = await service.list_invitations(
        db, org_id=org_id, requesting_org_id=_org_id_from_member(member)
    )
    return [InvitationResponse.model_validate(i) for i in invitations]


@router.post("/orgs/{org_id}/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    org_id: UUID,
    payload: InvitationCreate,
    member: OrgMember = Depends(require_org_role("manager")),
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    if org_id != _org_id_from_member(member):
        raise NotFoundError("Organization not found.")

    inv, _plaintext = await service.invite_member(
        db, org_id=org_id, invited_by=member.user_id, payload=payload
    )
    await db.commit()
    return InvitationResponse.model_validate(inv)


@router.delete("/orgs/{org_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    org_id: UUID,
    invitation_id: UUID,
    member: OrgMember = Depends(require_org_role("manager")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.revoke_invitation(
        db,
        org_id=org_id,
        invitation_id=invitation_id,
        requesting_org_id=_org_id_from_member(member),
    )
    await db.commit()


@router.post("/invitations/accept", response_model=AcceptInvitationResponse)
async def accept_invitation(
    payload: AcceptInvitationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AcceptInvitationResponse:
    org, role = await service.accept_invitation(
        db, token=payload.token, user_id=user.id, user_email=user.email
    )
    await db.commit()
    return AcceptInvitationResponse(
        organization=OrgResponse.model_validate(org),
        role=role,
    )


# ── Departments ────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/departments", response_model=list[DepartmentResponse])
async def list_departments(
    org_id: UUID,
    member: OrgMember = Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
) -> list[DepartmentResponse]:
    depts = await service.list_departments(
        db, org_id=org_id, requesting_org_id=_org_id_from_member(member)
    )
    return [DepartmentResponse.model_validate(d) for d in depts]


@router.post("/orgs/{org_id}/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    org_id: UUID,
    payload: DepartmentCreate,
    member: OrgMember = Depends(require_org_role("manager")),
    db: AsyncSession = Depends(get_db),
) -> DepartmentResponse:
    dept = await service.create_department(
        db, org_id=org_id, requesting_org_id=_org_id_from_member(member), payload=payload
    )
    await db.commit()
    return DepartmentResponse.model_validate(dept)


@router.patch("/orgs/{org_id}/departments/{dept_id}", response_model=DepartmentResponse)
async def update_department(
    org_id: UUID,
    dept_id: UUID,
    payload: DepartmentUpdate,
    member: OrgMember = Depends(require_org_role("manager")),
    db: AsyncSession = Depends(get_db),
) -> DepartmentResponse:
    dept = await service.update_department(
        db,
        org_id=org_id,
        dept_id=dept_id,
        requesting_org_id=_org_id_from_member(member),
        payload=payload,
    )
    await db.commit()
    return DepartmentResponse.model_validate(dept)


@router.delete("/orgs/{org_id}/departments/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    org_id: UUID,
    dept_id: UUID,
    member: OrgMember = Depends(require_org_role("manager")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_department(
        db,
        org_id=org_id,
        dept_id=dept_id,
        requesting_org_id=_org_id_from_member(member),
    )
    await db.commit()


# ── API Keys ───────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    org_id: UUID,
    member: OrgMember = Depends(require_org_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> list[APIKeyResponse]:
    keys = await service.list_api_keys(
        db, org_id=org_id, requesting_org_id=_org_id_from_member(member)
    )
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.post("/orgs/{org_id}/api-keys", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    org_id: UUID,
    payload: APIKeyCreate,
    member: OrgMember = Depends(require_org_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> APIKeyCreatedResponse:
    if org_id != _org_id_from_member(member):
        raise NotFoundError("Organization not found.")

    created = await service.create_api_key(
        db, org_id=org_id, created_by=member.user_id, payload=payload
    )
    await db.commit()

    base = APIKeyResponse.model_validate(created.api_key)
    return APIKeyCreatedResponse(**base.model_dump(), key=created.key)


@router.delete("/orgs/{org_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    org_id: UUID,
    key_id: UUID,
    member: OrgMember = Depends(require_org_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.revoke_api_key(
        db,
        org_id=org_id,
        key_id=key_id,
        requesting_org_id=_org_id_from_member(member),
    )
    await db.commit()
