from typing import Any
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class AppException(HTTPException):
    """Base exception for all application errors. Always produces the standard error envelope."""

    def __init__(self, status_code: int, error_code: str, message: str, details: dict | None = None) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.error_code = error_code
        self.message = message
        self.details = details or {}


class UnauthorizedError(AppException):
    def __init__(self, error_code: str = "UNAUTHORIZED", message: str = "Authentication required.") -> None:
        super().__init__(401, error_code, message)


class ForbiddenError(AppException):
    def __init__(self, error_code: str = "FORBIDDEN", message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(403, error_code, message)


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(404, "NOT_FOUND", message)


class ConflictError(AppException):
    def __init__(self, message: str = "A conflict occurred.") -> None:
        super().__init__(409, "CONFLICT", message)


class UnprocessableError(AppException):
    def __init__(self, message: str = "Unprocessable request.", details: dict | None = None) -> None:
        super().__init__(422, "VALIDATION_ERROR", message, details)


class RateLimitError(AppException):
    def __init__(self, retry_after: int = 60) -> None:
        super().__init__(429, "RATE_LIMITED", f"Too many requests. Retry after {retry_after} seconds.")
        self.retry_after = retry_after


class ExternalServiceError(AppException):
    def __init__(self, message: str = "An upstream service failed.") -> None:
        super().__init__(502, "EXTERNAL_SERVICE_ERROR", message)


def _build_error_body(request: Request, error_code: str, message: str, details: dict[str, Any]) -> dict:
    request_id: str = getattr(request.state, "request_id", "unknown")
    return {"error": {"code": error_code, "message": message, "request_id": request_id, "details": details}}


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitError):
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_body(request, exc.error_code, exc.message, exc.details),
        headers=headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [{"field": ".".join(str(l) for l in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    body = _build_error_body(request, "VALIDATION_ERROR", "Request validation failed.", {"fields": fields})
    return JSONResponse(status_code=422, content=body)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    body = _build_error_body(request, "INTERNAL_ERROR", "An unexpected error occurred.", {})
    return JSONResponse(status_code=500, content=body)
