import { create } from "zustand";
import {
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  type Node,
  type Edge,
  type NodeChange,
  type EdgeChange,
  type Connection,
} from "@xyflow/react";
import type { WorkflowGraph, GraphNode, GraphEdge, ValidationError } from "@/types/workflow";

interface BuilderState {
  workflowId: string | null;
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;
  isDirty: boolean;
  validationErrors: ValidationError[];

  // React Flow callbacks
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;

  // Builder actions
  addNode: (node: Node) => void;
  selectNode: (id: string | null) => void;
  updateNodeData: (id: string, data: Record<string, unknown>) => void;
  setValidationErrors: (errors: ValidationError[]) => void;
  clearValidationErrors: () => void;

  // Lifecycle
  loadGraph: (workflowId: string, graph: WorkflowGraph | null) => void;
  reset: () => void;
  toGraph: () => WorkflowGraph;
}

function rfNodesToGraph(nodes: Node[], edges: Edge[]): WorkflowGraph {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: (n.data.nodeType as string) ?? n.type ?? "",
      label: (n.data.label as string) ?? "",
      position: { x: n.position.x, y: n.position.y },
      config: (n.data.config as Record<string, unknown>) ?? {},
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle ?? "output",
      targetHandle: e.targetHandle ?? "input",
    })),
  };
}

function graphToRfNodes(graph: WorkflowGraph): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = graph.nodes.map((n: GraphNode) => ({
    id: n.id,
    type: n.type.startsWith("trigger.") ? "triggerNode"
        : n.type === "action.condition" ? "conditionNode"
        : "actionNode",
    position: n.position,
    data: {
      nodeType: n.type,
      label: n.label,
      config: n.config,
    },
  }));

  const edges: Edge[] = graph.edges.map((e: GraphEdge) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle,
    targetHandle: e.targetHandle,
  }));

  return { nodes, edges };
}

export const useBuilderStore = create<BuilderState>((set, get) => ({
  workflowId: null,
  nodes: [],
  edges: [],
  selectedNodeId: null,
  isDirty: false,
  validationErrors: [],

  onNodesChange: (changes) =>
    set((s) => ({ nodes: applyNodeChanges(changes, s.nodes), isDirty: true })),

  onEdgesChange: (changes) =>
    set((s) => ({ edges: applyEdgeChanges(changes, s.edges), isDirty: true })),

  onConnect: (connection) =>
    set((s) => ({
      edges: addEdge({ ...connection, id: `e-${Date.now()}` }, s.edges),
      isDirty: true,
    })),

  addNode: (node) =>
    set((s) => ({ nodes: [...s.nodes, node], isDirty: true })),

  selectNode: (id) => set({ selectedNodeId: id }),

  updateNodeData: (id, data) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, ...data } } : n
      ),
      isDirty: true,
    })),

  setValidationErrors: (errors) => set({ validationErrors: errors }),
  clearValidationErrors: () => set({ validationErrors: [] }),

  loadGraph: (workflowId, graph) => {
    if (!graph) {
      set({ workflowId, nodes: [], edges: [], isDirty: false, validationErrors: [] });
      return;
    }
    const { nodes, edges } = graphToRfNodes(graph);
    set({ workflowId, nodes, edges, isDirty: false, selectedNodeId: null, validationErrors: [] });
  },

  reset: () =>
    set({ workflowId: null, nodes: [], edges: [], selectedNodeId: null, isDirty: false, validationErrors: [] }),

  toGraph: () => rfNodesToGraph(get().nodes, get().edges),
}));
