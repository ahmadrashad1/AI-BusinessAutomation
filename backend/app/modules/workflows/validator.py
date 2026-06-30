"""
DAG validator for workflow graph definitions.
Returns a list of validation error dicts (node_id, message) — empty list means valid.
"""
from __future__ import annotations
from typing import Any

import app.modules.workflows.nodes  # noqa: F401 — triggers node registration side-effects


class ValidationError(Exception):
    """Raised when a graph dict is structurally malformed (missing required keys)."""


def validate_graph(graph: dict[str, Any]) -> list[dict[str, str]]:
    """
    Validate a workflow graph definition.

    Returns a list of error dicts with keys 'node_id' and 'message'.
    An empty list means the graph is structurally valid and publishable.
    Raises ValidationError if the graph dict is missing required top-level keys.
    """
    from app.modules.workflows.nodes.registry import NODE_REGISTRY

    if "nodes" not in graph:
        raise ValidationError("Graph is missing required key 'nodes'")
    if "edges" not in graph:
        raise ValidationError("Graph is missing required key 'edges'")

    nodes: list[dict] = graph["nodes"]
    edges: list[dict] = graph["edges"]
    errors: list[dict[str, str]] = []

    # Index for quick lookup
    node_map = {n["id"]: n for n in nodes}
    # Set of node IDs that have at least one incoming edge
    nodes_with_incoming: set[str] = {e["target"] for e in edges}
    # Outgoing edges grouped by source + sourceHandle
    outgoing_handles: dict[str, set[str]] = {}
    for e in edges:
        src = e["source"]
        handle = e.get("sourceHandle", "output")
        outgoing_handles.setdefault(src, set()).add(handle)

    trigger_types = {k for k in NODE_REGISTRY if k.startswith("trigger.")}
    trigger_node_ids = {n["id"] for n in nodes if n.get("type", "") in trigger_types}

    # ── unknown node types ─────────────────────────────────────────────────────
    for node in nodes:
        ntype = node.get("type", "")
        if ntype not in NODE_REGISTRY:
            errors.append({"node_id": node["id"], "message": f"Unknown node type '{ntype}'"})

    # ── trigger requirement ────────────────────────────────────────────────────
    if not trigger_node_ids:
        errors.append({"node_id": "", "message": "Graph must contain at least one trigger node"})

    # ── empty graph ────────────────────────────────────────────────────────────
    if not nodes:
        errors.append({"node_id": "", "message": "Graph must contain at least one node"})

    # ── cycle detection (DFS) ──────────────────────────────────────────────────
    adjacency: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        adjacency.setdefault(e["source"], []).append(e["target"])

    visited: set[str] = set()
    in_stack: set[str] = set()
    cycle_reported = False

    def dfs(node_id: str) -> bool:
        nonlocal cycle_reported
        visited.add(node_id)
        in_stack.add(node_id)
        for neighbor in adjacency.get(node_id, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in in_stack:
                if not cycle_reported:
                    errors.append({"node_id": node_id, "message": "Graph contains a cycle"})
                    cycle_reported = True
                return True
        in_stack.discard(node_id)
        return False

    for node in nodes:
        if node["id"] not in visited:
            dfs(node["id"])

    # ── orphaned non-trigger nodes ─────────────────────────────────────────────
    for node in nodes:
        nid = node["id"]
        ntype = node.get("type", "")
        if ntype in trigger_types:
            continue  # triggers are allowed to have no incoming edge
        if nid not in nodes_with_incoming:
            errors.append({"node_id": nid, "message": f"Node '{nid}' is orphaned (no incoming edge)"})

    # ── condition node branch completeness ────────────────────────────────────
    for node in nodes:
        if node.get("type") == "action.condition":
            nid = node["id"]
            handles = outgoing_handles.get(nid, set())
            if "true" not in handles:
                errors.append({"node_id": nid, "message": "Condition node missing 'true' outgoing edge"})
            if "false" not in handles:
                errors.append({"node_id": nid, "message": "Condition node missing 'false' outgoing edge"})

    return errors
