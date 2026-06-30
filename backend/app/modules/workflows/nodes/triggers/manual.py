from typing import Any
from app.modules.workflows.nodes.base import BaseNode
from app.modules.workflows.nodes.registry import register_node


@register_node("trigger.manual")
class ManualTriggerNode(BaseNode):
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {"data": {"type": "object"}}

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"data": context.get("input_data", {})}
