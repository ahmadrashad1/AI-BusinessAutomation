export type WorkflowStatus = "draft" | "published" | "archived";

export interface NodePosition {
  x: number;
  y: number;
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  position: NodePosition;
  config: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle: string;
  targetHandle: string;
}

export interface WorkflowGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Workflow {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  status: WorkflowStatus;
  active_version_id: string | null;
  current_version: number | null;
  draft_definition: WorkflowGraph | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowVersion {
  id: string;
  workflow_id: string;
  version_number: number;
  definition: WorkflowGraph;
  created_by: string | null;
  created_at: string;
}

export interface PaginatedWorkflows {
  items: Workflow[];
  total: number;
}

export interface PaginatedVersions {
  items: WorkflowVersion[];
  total: number;
}

export interface PublishResult {
  id: string;
  name: string;
  status: WorkflowStatus;
  active_version_id: string | null;
  active_version: {
    id: string;
    version_number: number;
    created_at: string;
  };
}

export interface ValidationError {
  node_id: string;
  message: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: {
      errors?: ValidationError[];
    };
  };
}

// Node type definitions for the palette
export interface NodeTypeDef {
  type: string;
  label: string;
  category: "trigger" | "action";
  description: string;
}

export const NODE_TYPE_DEFS: NodeTypeDef[] = [
  { type: "trigger.manual", label: "Manual", category: "trigger", description: "Start workflow manually" },
  { type: "trigger.schedule", label: "Schedule", category: "trigger", description: "Run on a cron schedule" },
  { type: "trigger.webhook", label: "Webhook", category: "trigger", description: "Triggered by HTTP webhook" },
  { type: "trigger.email", label: "Email", category: "trigger", description: "Triggered by inbound email" },
  { type: "action.http", label: "HTTP Request", category: "action", description: "Call an external HTTP endpoint" },
  { type: "action.email", label: "Send Email", category: "action", description: "Send an email" },
  { type: "action.condition", label: "Condition", category: "action", description: "Branch on a condition" },
  { type: "action.delay", label: "Delay", category: "action", description: "Wait for a duration" },
  { type: "action.db_write", label: "DB Write", category: "action", description: "Write data to a database" },
];
