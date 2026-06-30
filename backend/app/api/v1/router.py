from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.organizations.router import router as org_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router, prefix="/auth")
api_router.include_router(org_router)
