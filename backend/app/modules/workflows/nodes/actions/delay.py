from typing import Any
import asyncio
from app.modules.workflows.nodes.base import BaseNode
from app.modules.workflows.nodes.registry import register_node


@register_node("action.delay")
class DelayNode(BaseNode):
    input_schema: dict[str, Any] = {"seconds": {"type": "integer"}}
    output_schema: dict[str, Any] = {"delayed_seconds": {"type": "integer"}}

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        config = context.get("config", {})
        seconds = int(config.get("seconds", 0))
        await asyncio.sleep(seconds)
        return {"delayed_seconds": seconds}
