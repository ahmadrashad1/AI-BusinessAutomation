"""
Workflow Builder router — 11 endpoints for Milestone 3.

RBAC:
  viewer  → GET only (list, get, list versions, get version)
  manager → viewer + create, update, publish, duplicate
  admin   → manager + delete, archive, revert
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.organizations.dependencies import require_org_member, require_org_role
from app.modules.organizations.models import OrgMember
from app.modules.workflows import service
from app.modules.workflows.schemas import (
    DuplicateRequest,
    PaginatedVersions,
    PaginatedWorkflows,
    PublishRequest,
    WorkflowCreate,
    WorkflowResponse,
    WorkflowUpdate,
    WorkflowVersionResponse,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _wf_response(wf: Any) -> dict:
    return WorkflowResponse.model_validate(wf).model_dump()


def _ver_response(ver: Any) -> dict:
    return WorkflowVersionResponse.model_validate(ver).model_dump()


def _publish_response(wf: Any, ver: Any) -> dict:
    return {
        **_wf_response(wf),
        "active_version": {
            "id": ver.id,
            "version_number": ver.version_number,
            "created_at": ver.created_at.isoformat(),
        },
    }


def _org_id(member: OrgMember) -> str:
    return str(member.organization_id)


def _user_id(user: User) -> str:
    return str(user.id)


# ── POST /workflows ────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_workflow(
    payload: WorkflowCreate,
    member: OrgMember = Depends(require_org_role("manager")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    wf = await service.create_workflow(db, org_id=_org_id(member), payload=payload)
    return _wf_response(wf)


# ── GET /workflows ─────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedWorkflows)
async def list_workflows(
    member: OrgMember = Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await service.list_workflows(db, org_id=_org_id(member))
    return {"items": [WorkflowResponse.model_validate(w) for w in items], "total": len(items)}


# ── GET /workflows/{wf_id} ─────────────────────────────────────────────────────

@router.get("/{wf_id}")
async def get_workflow(
    wf_id: str,
    member: OrgMember = Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    wf = await service.get_workflow(db, org_id=_org_id(member), workflow_id=wf_id)
    return _wf_response(wf)


# ── PATCH /workflows/{wf_id} ───────────────────────────────────────────────────

@router.patch("/{wf_id}")
async def update_workflow(
    wf_id: str,
    payload: WorkflowUpdate,
    member: OrgMember = Depends(require_org_role("manager")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    wf = await service.update_workflow(db, org_id=_org_id(member), workflow_id=wf_id, payload=payload)
    return _wf_response(wf)


# ── DELETE /workflows/{wf_id} ──────────────────────────────────────────────────

@router.delete("/{wf_id}", status_code=204)
async def delete_workflow(
    wf_id: str,
    member: OrgMember = Depends(require_org_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await service.delete_workflow(db, org_id=_org_id(member), workflow_id=wf_id)
    return Response(status_code=204)


# ── POST /workflows/{wf_id}/publish ───────────────────────────────────────────

@router.post("/{wf_id}/publish")
async def publish_workflow(
    wf_id: str,
    payload: PublishRequest = PublishRequest(),
    member: OrgMember = Depends(require_org_role("manager")),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    wf, ver = await service.publish_workflow(
        db, org_id=_org_id(member), user_id=_user_id(user), workflow_id=wf_id, payload=payload
    )
    return _publish_response(wf, ver)


# ── GET /workflows/{wf_id}/versions ───────────────────────────────────────────

@router.get("/{wf_id}/versions", response_model=PaginatedVersions)
async def list_versions(
    wf_id: str,
    member: OrgMember = Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await service.list_versions(db, org_id=_org_id(member), workflow_id=wf_id)
    return {"items": [WorkflowVersionResponse.model_validate(v) for v in items], "total": len(items)}


# ── GET /workflows/{wf_id}/versions/{version_number} ──────────────────────────

@router.get("/{wf_id}/versions/{version_number}")
async def get_version(
    wf_id: str,
    version_number: int,
    member: OrgMember = Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ver = await service.get_version_by_number(
        db, org_id=_org_id(member), workflow_id=wf_id, version_number=version_number
    )
    return _ver_response(ver)


# ── POST /workflows/{wf_id}/revert/{version_number} ───────────────────────────

@router.post("/{wf_id}/revert/{version_number}")
async def revert_workflow(
    wf_id: str,
    version_number: int,
    member: OrgMember = Depends(require_org_role("admin")),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    wf, ver = await service.revert_workflow(
        db, org_id=_org_id(member), user_id=_user_id(user),
        workflow_id=wf_id, version_number=version_number,
    )
    return _publish_response(wf, ver)


# ── POST /workflows/{wf_id}/duplicate ─────────────────────────────────────────

@router.post("/{wf_id}/duplicate", status_code=201)
async def duplicate_workflow(
    wf_id: str,
    payload: DuplicateRequest,
    member: OrgMember = Depends(require_org_role("manager")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    wf = await service.duplicate_workflow(
        db, org_id=_org_id(member), workflow_id=wf_id, payload=payload
    )
    return _wf_response(wf)


# ── POST /workflows/{wf_id}/archive ───────────────────────────────────────────

@router.post("/{wf_id}/archive")
async def archive_workflow(
    wf_id: str,
    member: OrgMember = Depends(require_org_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    wf = await service.archive_workflow(db, org_id=_org_id(member), workflow_id=wf_id)
    return _wf_response(wf)
