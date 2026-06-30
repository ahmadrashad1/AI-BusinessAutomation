"""
Node plugin registry — global registry mapping node_type strings to BaseNode subclasses.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.workflows.nodes.base import BaseNode

NODE_REGISTRY: dict[str, type["BaseNode"]] = {}


def register_node(node_type: str):
    """Decorator that registers a BaseNode subclass under the given node_type string."""
    def decorator(cls: type["BaseNode"]) -> type["BaseNode"]:
        if node_type in NODE_REGISTRY:
            raise ValueError(
                f"Node type '{node_type}' is already registered by {NODE_REGISTRY[node_type].__name__}. "
                f"Each node_type must be unique."
            )
        NODE_REGISTRY[node_type] = cls
        cls.node_type = node_type
        return cls
    return decorator


def get_node_class(node_type: str) -> type["BaseNode"] | None:
    """Return the registered class for the given node_type, or None if not found."""
    return NODE_REGISTRY.get(node_type)
