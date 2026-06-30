import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedError

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assigns a unique request_id and logs each request/response pair as structured JSON."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.perf_counter()

        logger.info(
            "request_start",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
            },
        )

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000)

        logger.info(
            "request_end",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Reads the org_id and scope from the JWT in the Authorization header and stores
    them in request.state for use by service functions.

    Does NOT raise an error on missing/invalid tokens — auth dependencies handle that.
    This middleware only populates state when a valid token is present.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request.state.organization_id = None
        request.state.user_id = None
        request.state.token_scope = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and not auth_header[7:].startswith("bpa_sk_"):
            token = auth_header[7:]
            try:
                payload = decode_access_token(token)
                request.state.organization_id = payload.get("org_id")
                request.state.user_id = payload.get("user_id")
                request.state.token_scope = payload.get("scope")
            except UnauthorizedError:
                pass  # Dependencies will raise the proper error on protected routes

        return await call_next(request)
