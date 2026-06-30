from typing import Any
from app.modules.workflows.nodes.base import BaseNode
from app.modules.workflows.nodes.registry import register_node


@register_node("trigger.webhook")
class WebhookTriggerNode(BaseNode):
    input_schema: dict[str, Any] = {"path": {"type": "string"}, "method": {"type": "string"}}
    output_schema: dict[str, Any] = {"body": {"type": "object"}, "headers": {"type": "object"}}

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        payload = context.get("webhook_payload", {})
        return {"body": payload.get("body", {}), "headers": payload.get("headers", {})}
