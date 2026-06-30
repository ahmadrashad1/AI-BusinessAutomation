"""
BaseNode ABC — every workflow node type inherits from this class.
"""
from abc import ABC, abstractmethod
from typing import Any, ClassVar


class BaseNode(ABC):
    """Abstract base for all workflow node types."""

    node_type: ClassVar[str]
    input_schema: ClassVar[dict[str, Any]]
    output_schema: ClassVar[dict[str, Any]]

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the node with the given execution context and return output."""
        ...
