"""
Unit tests for the node plugin registry — TDD RED phase.
Registry must: register nodes, look them up, reject duplicates.
"""
import pytest

from app.modules.workflows.nodes.registry import NODE_REGISTRY, register_node, get_node_class
from app.modules.workflows.nodes.base import BaseNode


class TestNodeRegistry:
    def test_all_trigger_types_registered(self):
        # Import triggers to trigger registration side-effects
        import app.modules.workflows.nodes.triggers  # noqa: F401
        for node_type in ("trigger.manual", "trigger.schedule", "trigger.webhook", "trigger.email"):
            assert node_type in NODE_REGISTRY, f"{node_type} not in registry"

    def test_all_action_types_registered(self):
        import app.modules.workflows.nodes.actions  # noqa: F401
        for node_type in ("action.http", "action.email", "action.condition", "action.delay", "action.db_write"):
            assert node_type in NODE_REGISTRY, f"{node_type} not in registry"

    def test_get_node_class_returns_class(self):
        import app.modules.workflows.nodes.triggers  # noqa: F401
        cls = get_node_class("trigger.manual")
        assert cls is not None
        assert issubclass(cls, BaseNode)

    def test_get_node_class_returns_none_for_unknown(self):
        result = get_node_class("trigger.does_not_exist_xyz")
        assert result is None

    def test_duplicate_registration_raises_error(self):
        # Register a type, then try to register it again — must raise
        @register_node("trigger.manual_test_dup_1")
        class _DummyNode1(BaseNode):
            node_type = "trigger.manual_test_dup_1"
            input_schema: dict = {}
            output_schema: dict = {}

            async def execute(self, context: dict) -> dict:
                return {}

        with pytest.raises((ValueError, KeyError)):
            @register_node("trigger.manual_test_dup_1")
            class _DummyNode2(BaseNode):
                node_type = "trigger.manual_test_dup_1"
                input_schema: dict = {}
                output_schema: dict = {}

                async def execute(self, context: dict) -> dict:
                    return {}

    def test_registered_node_is_base_node_subclass(self):
        import app.modules.workflows.nodes.triggers  # noqa: F401
        for node_type, cls in NODE_REGISTRY.items():
            assert issubclass(cls, BaseNode), f"{node_type} does not subclass BaseNode"

    def test_get_all_types_returns_list(self):
        import app.modules.workflows.nodes.triggers  # noqa: F401
        import app.modules.workflows.nodes.actions  # noqa: F401
        types = list(NODE_REGISTRY.keys())
        assert isinstance(types, list)
        assert len(types) >= 9  # 4 triggers + 5 actions
