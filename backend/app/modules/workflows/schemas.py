"""
Pydantic v2 schemas for the Workflow Builder API (Milestone 3).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Graph primitives ───────────────────────────────────────────────────────────

class NodePosition(BaseModel):
    x: float
    y: float


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    position: NodePosition
    config: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: str = "output"
    targetHandle: str = "input"


class WorkflowGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ── Workflow CRUD ──────────────────────────────────────────────────────────────

class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[list[str]] = None  # stored externally in M5; accepted now for forward compat


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    definition: Optional[WorkflowGraph] = None  # saved as draft_definition


class WorkflowResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str] = None
    status: str  # draft | published | archived
    active_version_id: Optional[str] = None
    current_version: Optional[int] = None
    draft_definition: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Publish body ───────────────────────────────────────────────────────────────

class PublishRequest(BaseModel):
    """All fields optional — definition falls back to stored draft_definition."""
    definition: Optional[WorkflowGraph] = None
    change_summary: Optional[str] = None


# ── Version ────────────────────────────────────────────────────────────────────

class WorkflowVersionResponse(BaseModel):
    id: str
    workflow_id: str
    version_number: int
    definition: dict[str, Any]
    created_by: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Paginated lists ────────────────────────────────────────────────────────────

class PaginatedWorkflows(BaseModel):
    items: list[WorkflowResponse]
    total: int


class PaginatedVersions(BaseModel):
    items: list[WorkflowVersionResponse]
    total: int


# ── Duplicate ──────────────────────────────────────────────────────────────────

class DuplicateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
