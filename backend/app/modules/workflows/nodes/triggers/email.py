from typing import Any
from app.modules.workflows.nodes.base import BaseNode
from app.modules.workflows.nodes.registry import register_node


@register_node("trigger.email")
class EmailTriggerNode(BaseNode):
    input_schema: dict[str, Any] = {"mailbox": {"type": "string"}}
    output_schema: dict[str, Any] = {"from": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        email = context.get("email_payload", {})
        return {"from": email.get("from", ""), "subject": email.get("subject", ""), "body": email.get("body", "")}
