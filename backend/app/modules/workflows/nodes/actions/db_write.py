from typing import Any
from app.modules.workflows.nodes.base import BaseNode
from app.modules.workflows.nodes.registry import register_node


@register_node("action.db_write")
class DbWriteNode(BaseNode):
    input_schema: dict[str, Any] = {
        "integration_id": {"type": "string"},
        "table": {"type": "string"},
        "data": {"type": "object"},
    }
    output_schema: dict[str, Any] = {"rows_written": {"type": "integer"}}

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        # DB write via integration credentials — full implementation in M5.
        return {"rows_written": 0}
