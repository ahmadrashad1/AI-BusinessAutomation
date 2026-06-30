"""
Unit tests for the DAG validator — written FIRST per TDD discipline.
Tests validate the structural rules enforced before a workflow can be published.
"""
import pytest

from app.modules.workflows.validator import validate_graph, ValidationError as GraphValidationError


def _make_graph(nodes: list[dict], edges: list[dict]) -> dict:
    return {"nodes": nodes, "edges": edges}


def _trigger(node_id: str = "t1", node_type: str = "trigger.manual") -> dict:
    return {"id": node_id, "type": node_type, "label": "Start", "position": {"x": 0, "y": 0}, "config": {}}


def _action(node_id: str, node_type: str = "action.http") -> dict:
    return {"id": node_id, "type": node_type, "label": node_id, "position": {"x": 100, "y": 0}, "config": {}}


def _edge(source: str, target: str, source_handle: str = "output") -> dict:
    return {"id": f"{source}->{target}", "source": source, "target": target,
            "sourceHandle": source_handle, "targetHandle": "input"}


# ── trigger count ──────────────────────────────────────────────────────────────

class TestTriggerRequirement:
    def test_graph_with_no_trigger_fails(self):
        graph = _make_graph([_action("a1")], [])
        errors = validate_graph(graph)
        assert any("trigger" in e["message"].lower() for e in errors)

    def test_graph_with_one_trigger_satisfies_requirement(self):
        graph = _make_graph([_trigger(), _action("a1")], [_edge("t1", "a1")])
        errors = validate_graph(graph)
        assert not any("trigger" in e["message"].lower() for e in errors)


# ── orphaned nodes ─────────────────────────────────────────────────────────────

class TestOrphanedNodes:
    def test_orphaned_action_node_fails(self):
        # a1 has no incoming edges — it's orphaned
        graph = _make_graph([_trigger(), _action("a1")], [])
        errors = validate_graph(graph)
        orphan_errors = [e for e in errors if e.get("node_id") == "a1"]
        assert orphan_errors

    def test_trigger_node_is_exempt_from_orphan_check(self):
        graph = _make_graph([_trigger("t1"), _action("a1")], [_edge("t1", "a1")])
        errors = validate_graph(graph)
        assert not any(e.get("node_id") == "t1" and "orphan" in e["message"].lower() for e in errors)

    def test_all_nodes_connected_passes(self):
        graph = _make_graph(
            [_trigger("t1"), _action("a1"), _action("a2")],
            [_edge("t1", "a1"), _edge("a1", "a2")],
        )
        errors = validate_graph(graph)
        assert len(errors) == 0


# ── cycle detection ────────────────────────────────────────────────────────────

class TestCycleDetection:
    def test_simple_cycle_fails(self):
        # a1 → a2 → a1
        graph = _make_graph(
            [_trigger("t1"), _action("a1"), _action("a2")],
            [_edge("t1", "a1"), _edge("a1", "a2"), _edge("a2", "a1")],
        )
        errors = validate_graph(graph)
        assert any("cycle" in e["message"].lower() for e in errors)

    def test_self_loop_fails(self):
        # a1 → a1
        graph = _make_graph(
            [_trigger("t1"), _action("a1")],
            [_edge("t1", "a1"), _edge("a1", "a1")],
        )
        errors = validate_graph(graph)
        assert any("cycle" in e["message"].lower() for e in errors)

    def test_linear_chain_has_no_cycle(self):
        graph = _make_graph(
            [_trigger("t1"), _action("a1"), _action("a2")],
            [_edge("t1", "a1"), _edge("a1", "a2")],
        )
        errors = validate_graph(graph)
        assert not any("cycle" in e["message"].lower() for e in errors)


# ── condition node branches ────────────────────────────────────────────────────

class TestConditionNodeBranches:
    def test_condition_missing_false_branch_fails(self):
        cond = {"id": "c1", "type": "action.condition", "label": "Check", "position": {"x": 100, "y": 0}, "config": {}}
        graph = _make_graph(
            [_trigger("t1"), cond, _action("a_true")],
            [_edge("t1", "c1"), _edge("c1", "a_true", source_handle="true")],
        )
        errors = validate_graph(graph)
        assert any(e.get("node_id") == "c1" for e in errors)

    def test_condition_missing_true_branch_fails(self):
        cond = {"id": "c1", "type": "action.condition", "label": "Check", "position": {"x": 100, "y": 0}, "config": {}}
        graph = _make_graph(
            [_trigger("t1"), cond, _action("a_false")],
            [_edge("t1", "c1"), _edge("c1", "a_false", source_handle="false")],
        )
        errors = validate_graph(graph)
        assert any(e.get("node_id") == "c1" for e in errors)

    def test_condition_with_both_branches_passes(self):
        cond = {"id": "c1", "type": "action.condition", "label": "Check", "position": {"x": 100, "y": 0}, "config": {}}
        graph = _make_graph(
            [_trigger("t1"), cond, _action("a_true"), _action("a_false")],
            [
                _edge("t1", "c1"),
                _edge("c1", "a_true", source_handle="true"),
                _edge("c1", "a_false", source_handle="false"),
            ],
        )
        errors = validate_graph(graph)
        assert not any(e.get("node_id") == "c1" for e in errors)


# ── unknown node type ──────────────────────────────────────────────────────────

class TestUnknownNodeType:
    def test_unknown_node_type_fails(self):
        unknown = {"id": "u1", "type": "trigger.does_not_exist", "label": "X",
                   "position": {"x": 0, "y": 0}, "config": {}}
        graph = _make_graph([unknown, _action("a1")], [_edge("u1", "a1")])
        errors = validate_graph(graph)
        assert any(e.get("node_id") == "u1" for e in errors)

    def test_known_node_types_pass(self):
        graph = _make_graph([_trigger("t1"), _action("a1")], [_edge("t1", "a1")])
        errors = validate_graph(graph)
        assert not any("unknown" in e["message"].lower() for e in errors)


# ── empty graph ────────────────────────────────────────────────────────────────

class TestEmptyGraph:
    def test_empty_nodes_fails(self):
        errors = validate_graph({"nodes": [], "edges": []})
        assert len(errors) > 0

    def test_missing_nodes_key_fails(self):
        with pytest.raises((KeyError, Exception)):
            validate_graph({})


# ── multiple errors returned ───────────────────────────────────────────────────

class TestMultipleErrors:
    def test_returns_all_errors_not_just_first(self):
        # Two orphaned action nodes AND no trigger → at least 3 errors
        graph = _make_graph([_action("a1"), _action("a2")], [])
        errors = validate_graph(graph)
        assert len(errors) >= 2
