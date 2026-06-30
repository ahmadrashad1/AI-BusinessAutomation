"""create workflow tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-01 00:00:00.000000

M3: workflow builder tables.
active_version_id and draft_definition are not in DatabaseDesign.md.
  - draft_definition JSONB: persists canvas state between auto-saves without
    creating a version on every keystroke.
  - active_version_id UUID: denormalized pointer to the live version row so
    API responses can return it without an extra join.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("current_version", sa.Integer, nullable=True),
        sa.Column("active_version_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("draft_definition", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_workflows_organization_id", "workflows", ["organization_id"])

    op.create_table(
        "workflow_versions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("definition", postgresql.JSONB, nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_workflow_versions_workflow_id", "workflow_versions", ["workflow_id"])
    op.create_unique_constraint("uq_workflow_versions", "workflow_versions", ["workflow_id", "version_number"])

    op.create_table(
        "workflow_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("version_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(255), nullable=False),
        sa.Column("node_type", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("position_x", sa.Integer, nullable=True),
        sa.Column("position_y", sa.Integer, nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_workflow_nodes_version_id", "workflow_nodes", ["version_id"])

    op.create_table(
        "workflow_edges",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("version_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("edge_id", sa.String(255), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("source_handle", sa.String(50), nullable=True),
        sa.Column("target_handle", sa.String(50), nullable=True),
    )
    op.create_index("ix_workflow_edges_version_id", "workflow_edges", ["version_id"])


def downgrade() -> None:
    op.drop_table("workflow_edges")
    op.drop_table("workflow_nodes")
    op.drop_table("workflow_versions")
    op.drop_table("workflows")
