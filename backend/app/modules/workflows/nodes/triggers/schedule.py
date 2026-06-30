from typing import Any
from app.modules.workflows.nodes.base import BaseNode
from app.modules.workflows.nodes.registry import register_node


@register_node("trigger.schedule")
class ScheduleTriggerNode(BaseNode):
    input_schema: dict[str, Any] = {"cron": {"type": "string"}}
    output_schema: dict[str, Any] = {"scheduled_at": {"type": "string"}}

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from datetime import datetime, timezone
        return {"scheduled_at": datetime.now(timezone.utc).isoformat()}
