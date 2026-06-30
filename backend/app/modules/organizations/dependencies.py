"""
Organization dependency functions.

Dependency chain:
    get_current_user()  →  require_org_member()  →  require_org_role(min_role)
                                                 ↕
                          get_api_key_context()  →  (used for bpa_sk_ auth)
"""
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.organizations.models import APIKey, OrgMember, Organization, ROLE_RANK
from app.modules.organizations.service import get_org_by_api_key


async def require_org_member(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgMember:
    """
    Require the caller to be an active member of their JWT org.
    Also checks that the org is active; raises ORG_SUSPENDED if not.
    """
    payload = getattr(user, "_token_payload", {})
    org_id_str: str = payload.get("org_id", "")

    try:
        org_id = UUID(org_id_str)
    except ValueError:
        raise UnauthorizedError("INVALID_TOKEN", "Token is missing org_id.")

    # Verify org is active
    org = await db.get(Organization, org_id)
    if org is None:
        raise UnauthorizedError("ORG_NOT_FOUND", "Organization not found.")
    if not org.is_active:
        raise UnauthorizedError("ORG_SUSPENDED", "This organization has been suspended.")

    result = await db.execute(
        select(OrgMember).where(
            OrgMember.organization_id == org_id,
            OrgMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise ForbiddenError("NOT_A_MEMBER", "You are not a member of this organization.")

    return member


def require_org_role(min_role: str):
    """
    Dependency factory: requires the caller's role rank to be >= min_role rank.
    Must be used after require_org_member.
    """
    min_rank = ROLE_RANK[min_role]

    async def _check(member: OrgMember = Depends(require_org_member)) -> OrgMember:
        caller_rank = ROLE_RANK.get(member.role, 0)
        if caller_rank < min_rank:
            raise ForbiddenError("INSUFFICIENT_ROLE", f"This action requires at least '{min_role}' role.")
        return member

    return _check


# ── API Key authentication ─────────────────────────────────────────────────────

class APIKeyContext:
    """Carries the authenticated api_key and org for API-key-authenticated requests."""
    def __init__(self, api_key: APIKey, org: Organization) -> None:
        self.api_key = api_key
        self.org = org

    def require_scope(self, scope: str) -> None:
        if scope not in self.api_key.scopes:
            raise ForbiddenError("INSUFFICIENT_SCOPE", f"API key lacks required scope: '{scope}'.")


async def get_api_key_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIKeyContext:
    """
    Extract and validate a bpa_sk_ API key from the Authorization header.
    Falls back to bearer JWT if the header is not an API key.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer bpa_sk_"):
        raise UnauthorizedError("UNAUTHORIZED", "API key required (Bearer bpa_sk_...).")

    plaintext_key = auth[7:]  # strip "Bearer "
    api_key, org = await get_org_by_api_key(db, plaintext_key=plaintext_key)
    return APIKeyContext(api_key=api_key, org=org)
