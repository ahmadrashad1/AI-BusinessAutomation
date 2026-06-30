from typing import Any
from app.modules.workflows.nodes.base import BaseNode
from app.modules.workflows.nodes.registry import register_node


@register_node("action.http")
class HttpRequestNode(BaseNode):
    input_schema: dict[str, Any] = {
        "url": {"type": "string"},
        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
        "headers": {"type": "object"},
        "body": {"type": "object"},
    }
    output_schema: dict[str, Any] = {"status_code": {"type": "integer"}, "body": {"type": "object"}}

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        import httpx
        config = context.get("config", {})
        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        headers = config.get("headers", {})
        body = config.get("body")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, headers=headers, json=body)
            try:
                resp_body = response.json()
            except Exception:
                resp_body = {"text": response.text}
            return {"status_code": response.status_code, "body": resp_body}
