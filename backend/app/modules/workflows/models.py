"""
SQLAlchemy models for the workflow builder (Milestone 3).
Tables: workflows, workflow_versions, workflow_nodes, workflow_edges.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Workflow(Base):
    __tablename__ = "workflows"
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    organization_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    current_version = Column(Integer, nullable=True)
    active_version_id = Column(UUID(as_uuid=False), nullable=True)
    # Persists canvas state between auto-saves without creating a version each time.
    # Not in DatabaseDesign.md — minimal deviation required by the publish flow.
    draft_definition = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    versions = relationship("WorkflowVersion", back_populates="workflow", cascade="all, delete-orphan")


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"
    __allow_unmapped__ = True
    __table_args__ = (UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions"),)

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workflow_id = Column(UUID(as_uuid=False), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    definition = Column(JSONB, nullable=False)
    created_by = Column(UUID(as_uuid=False), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    workflow = relationship("Workflow", back_populates="versions")
    nodes = relationship("WorkflowNode", back_populates="version", cascade="all, delete-orphan")
    edges = relationship("WorkflowEdge", back_populates="version", cascade="all, delete-orphan")


class WorkflowNode(Base):
    __tablename__ = "workflow_nodes"
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    version_id = Column(UUID(as_uuid=False), ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(String(255), nullable=False)
    node_type = Column(String(100), nullable=False)
    label = Column(String(255), nullable=True)
    position_x = Column(Integer, nullable=True)
    position_y = Column(Integer, nullable=True)
    config = Column(JSONB, nullable=True)

    version = relationship("WorkflowVersion", back_populates="nodes")


class WorkflowEdge(Base):
    __tablename__ = "workflow_edges"
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    version_id = Column(UUID(as_uuid=False), ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    edge_id = Column(String(255), nullable=False)
    source = Column(String(255), nullable=False)
    target = Column(String(255), nullable=False)
    source_handle = Column(String(50), nullable=True)
    target_handle = Column(String(50), nullable=True)

    version = relationship("WorkflowVersion", back_populates="edges")
