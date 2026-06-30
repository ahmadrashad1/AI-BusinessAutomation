"""
Workflow service — all business logic for Milestone 3.

Rules:
- organization_id comes from JWT (OrgMember), never from request body
- Cross-tenant access returns NotFoundError (404)
- Graph validation at publish time; INVALID_GRAPH -> 422
- Version numbers assigned MAX+1 inside the same transaction
- status: "draft" | "published" | "archived"
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, NotFoundError
from app.modules.workflows.models import Workflow, WorkflowEdge, WorkflowNode, WorkflowVersion
from app.modules.workflows.schemas import (
    DuplicateRequest,
    PublishRequest,
    WorkflowCreate,
    WorkflowGraph,
    WorkflowUpdate,
)
from app.modules.workflows.validator import validate_graph


# ── internal helpers ───────────────────────────────────────────────────────────

def _graph_to_dict(graph: WorkflowGraph) -> dict[str, Any]:
    return graph.model_dump(mode="json")


async def _get_workflow(db: AsyncSession, workflow_id: str, org_id: str) -> Workflow:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None or str(wf.organization_id) != str(org_id):
        raise NotFoundError("Workflow not found.")
    return wf


async def _next_version_number(db: AsyncSession, workflow_id: str) -> int:
    result = await db.execute(
        select(func.max(WorkflowVersion.version_number)).where(
            WorkflowVersion.workflow_id == workflow_id
        )
    )
    max_ver: int | None = result.scalar()
    return (max_ver or 0) + 1


async def _persist_graph_rows(
    db: AsyncSession, version_id: str, graph: WorkflowGraph
) -> None:
    for node in graph.nodes:
        db.add(WorkflowNode(
            id=str(uuid.uuid4()),
            version_id=version_id,
            node_id=node.id,
            node_type=node.type,
            label=node.label,
            position_x=int(node.position.x),
            position_y=int(node.position.y),
            config=node.config,
        ))
    for edge in graph.edges:
        db.add(WorkflowEdge(
            id=str(uuid.uuid4()),
            version_id=version_id,
            edge_id=edge.id,
            source=edge.source,
            target=edge.target,
            source_handle=edge.sourceHandle,
            target_handle=edge.targetHandle,
        ))


# ── CRUD ───────────────────────────────────────────────────────────────────────

async def create_workflow(
    db: AsyncSession, *, org_id: str, payload: WorkflowCreate
) -> Workflow:
    wf = Workflow(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        name=payload.name,
        description=payload.description,
        status="draft",
    )
    db.add(wf)
    await db.flush()
    await db.refresh(wf)
    return wf


async def list_workflows(db: AsyncSession, *, org_id: str) -> list[Workflow]:
    result = await db.execute(
        select(Workflow).where(Workflow.organization_id == org_id)
    )
    return list(result.scalars().all())


async def get_workflow(
    db: AsyncSession, *, org_id: str, workflow_id: str
) -> Workflow:
    return await _get_workflow(db, workflow_id, org_id)


async def update_workflow(
    db: AsyncSession, *, org_id: str, workflow_id: str, payload: WorkflowUpdate
) -> Workflow:
    wf = await _get_workflow(db, workflow_id, org_id)
    if payload.name is not None:
        wf.name = payload.name
    if payload.description is not None:
        wf.description = payload.description
    if payload.definition is not None:
        wf.draft_definition = _graph_to_dict(payload.definition)
    await db.flush()
    await db.refresh(wf)
    return wf


async def delete_workflow(
    db: AsyncSession, *, org_id: str, workflow_id: str
) -> None:
    wf = await _get_workflow(db, workflow_id, org_id)
    await db.delete(wf)
    await db.flush()


# ── publish ────────────────────────────────────────────────────────────────────

async def publish_workflow(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    workflow_id: str,
    payload: PublishRequest,
) -> tuple[Workflow, WorkflowVersion]:
    wf = await _get_workflow(db, workflow_id, org_id)

    # Body definition takes priority over stored draft
    if payload.definition is not None:
        graph = payload.definition
    elif wf.draft_definition is not None:
        graph = WorkflowGraph.model_validate(wf.draft_definition)
    else:
        raise AppException(422, "NO_DEFINITION", "No workflow definition to publish. Save a draft first.")

    graph_dict = _graph_to_dict(graph)
    errors = validate_graph(graph_dict)
    if errors:
        raise AppException(422, "INVALID_GRAPH", "Workflow graph failed validation.", {"errors": errors})

    next_ver = await _next_version_number(db, workflow_id)

    version = WorkflowVersion(
        id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        version_number=next_ver,
        definition=graph_dict,
        created_by=user_id,
    )
    db.add(version)
    await db.flush()

    await _persist_graph_rows(db, version.id, graph)

    wf.current_version = next_ver
    wf.active_version_id = version.id
    wf.status = "published"
    wf.draft_definition = None
    await db.flush()
    await db.refresh(wf)
    await db.refresh(version)
    return wf, version


# ── versions ───────────────────────────────────────────────────────────────────

async def list_versions(
    db: AsyncSession, *, org_id: str, workflow_id: str
) -> list[WorkflowVersion]:
    await _get_workflow(db, workflow_id, org_id)
    result = await db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.version_number.asc())
    )
    return list(result.scalars().all())


async def get_version_by_number(
    db: AsyncSession, *, org_id: str, workflow_id: str, version_number: int
) -> WorkflowVersion:
    await _get_workflow(db, workflow_id, org_id)
    result = await db.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == version_number,
        )
    )
    ver = result.scalar_one_or_none()
    if ver is None:
        raise NotFoundError(f"Version {version_number} not found.")
    return ver


async def revert_workflow(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    workflow_id: str,
    version_number: int,
) -> tuple[Workflow, WorkflowVersion]:
    """Republish a previous version's graph as the next version number."""
    source = await get_version_by_number(
        db, org_id=org_id, workflow_id=workflow_id, version_number=version_number
    )
    graph = WorkflowGraph.model_validate(source.definition)
    return await publish_workflow(
        db,
        org_id=org_id,
        user_id=user_id,
        workflow_id=workflow_id,
        payload=PublishRequest(definition=graph),
    )


# ── duplicate ──────────────────────────────────────────────────────────────────

async def duplicate_workflow(
    db: AsyncSession, *, org_id: str, workflow_id: str, payload: DuplicateRequest
) -> Workflow:
    source = await _get_workflow(db, workflow_id, org_id)
    new_wf = Workflow(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        name=payload.name,
        description=source.description,
        status="draft",
        draft_definition=source.draft_definition,
    )
    db.add(new_wf)
    await db.flush()
    await db.refresh(new_wf)
    return new_wf


# ── archive ────────────────────────────────────────────────────────────────────

async def archive_workflow(
    db: AsyncSession, *, org_id: str, workflow_id: str
) -> Workflow:
    wf = await _get_workflow(db, workflow_id, org_id)
    if wf.status == "archived":
        raise AppException(409, "CONFLICT", "Workflow is already archived.")
    wf.status = "archived"
    await db.flush()
    await db.refresh(wf)
    return wf
