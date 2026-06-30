from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.core.exceptions import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    validation_exception_handler,
)
from app.core.middleware import RequestLoggingMiddleware, TenantContextMiddleware
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: warm the Redis connection pool
    from app.core.redis import get_pool
    get_pool()
    yield
    # Shutdown: close the Redis pool
    from app.core.redis import _pool
    if _pool is not None:
        await _pool.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AutoFlow AI Business Automation Platform",
        description="Multi-tenant SaaS platform for AI-powered business process automation.",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # Middleware (outermost first)
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Routes
    app.include_router(api_router)

    @app.get("/health", tags=["infra"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
