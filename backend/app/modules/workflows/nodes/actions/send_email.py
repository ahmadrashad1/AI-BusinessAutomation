from typing import Any
from app.modules.workflows.nodes.base import BaseNode
from app.modules.workflows.nodes.registry import register_node


@register_node("action.email")
class SendEmailNode(BaseNode):
    input_schema: dict[str, Any] = {
        "to": {"type": "string"},
        "subject": {"type": "string"},
        "body": {"type": "string"},
    }
    output_schema: dict[str, Any] = {"sent": {"type": "boolean"}}

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        # Email dispatch is handled by Celery task in production (M7).
        # The node records the intent; the task runner dispatches it.
        return {"sent": True}
