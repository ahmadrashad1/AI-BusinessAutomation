from typing import Any
import jsonpath_ng
from app.modules.workflows.nodes.base import BaseNode
from app.modules.workflows.nodes.registry import register_node


@register_node("action.condition")
class ConditionNode(BaseNode):
    input_schema: dict[str, Any] = {
        "expression": {"type": "string"},   # JSONPath expression
        "expected": {},                      # expected value
    }
    output_schema: dict[str, Any] = {"result": {"type": "boolean"}, "branch": {"type": "string"}}

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        config = context.get("config", {})
        expression = config.get("expression", "")
        expected = config.get("expected")
        data = context.get("input", {})

        try:
            jsonpath_expr = jsonpath_ng.parse(expression)
            matches = jsonpath_expr.find(data)
            actual = matches[0].value if matches else None
        except Exception:
            actual = None

        result = actual == expected
        return {"result": result, "branch": "true" if result else "false"}
