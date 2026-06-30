"""
Pydantic v2 schemas for the Workflow Builder API (Milestone 3).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    draft_definition: Optional[WorkflowGraph] = None


class WorkflowResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str]
    status: str
    current_version: Optional[int]
    draft_definition: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Publish ────────────────────────────────────────────────────────────────────

class PublishRequest(BaseModel):
    definition: WorkflowGraph


class PublishResponse(BaseModel):
    workflow_id: str
    version_number: int


# ── Version ────────────────────────────────────────────────────────────────────

class WorkflowVersionResponse(BaseModel):
    id: str
    workflow_id: str
    version_number: int
    definition: dict[str, Any]
    created_by: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Duplicate ──────────────────────────────────────────────────────────────────

class DuplicateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
