"""
RBAC integration tests.

Verifies role-based access control enforcement across all org roles.
Cross-references: ARCHITECTURE.md §10.5, API.md §2.3
"""
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.modules.auth.models import User
from app.modules.organizations.models import Organization, OrgMember


# ── shared org fixture ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def rbac_org(db_session: AsyncSession):
    """Returns org with owner. Other roles added per test."""
    owner_user = User(
        email="rbac_owner@example.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="RBAC Owner",
        is_verified=True, is_active=True,
    )
    db_session.add(owner_user)
    await db_session.flush()

    org = Organization(
        name="RBAC Org", slug="rbac-org", plan="free", is_active=True,
        settings={}, storage_used_bytes=0,
    )
    db_session.add(org)
    await db_session.flush()

    owner_member = OrgMember(organization_id=org.id, user_id=owner_user.id, role="owner")
    db_session.add(owner_member)
    await db_session.flush()

    return owner_user, org


async def _create_member_token(db_session, org_id, role: str, email: str) -> tuple:
    user = User(
        email=email,
        hashed_password=hash_password("SecurePass123!"),
        full_name=f"{role} User",
        is_verified=True, is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    member = OrgMember(organization_id=org_id, user_id=user.id, role=role)
    db_session.add(member)
    await db_session.flush()

    token = create_access_token(
        user_id=user.id, org_id=org_id, session_id=uuid4(),
        role=role, scope="org",
    )
    return user, member, token


# ── viewer restrictions ────────────────────────────────────────────────────────

class TestViewerRestrictions:
    @pytest.mark.asyncio
    async def test_viewer_can_get_org(self, client: AsyncClient, rbac_org, db_session: AsyncSession):
        _, org = rbac_org
        _, _, token = await _create_member_token(db_session, org.id, "viewer", "viewer_rbac@example.com")

        res = await client.get(
            f"/api/v1/orgs/{org.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_cannot_update_org(self, client: AsyncClient, rbac_org, db_session: AsyncSession):
        _, org = rbac_org
        _, _, token = await _create_member_token(db_session, org.id, "viewer", "viewer2_rbac@example.com")

        res = await client.patch(
            f"/api/v1/orgs/{org.id}",
            json={"name": "Hacked"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "INSUFFICIENT_ROLE"

    @pytest.mark.asyncio
    async def test_viewer_cannot_delete_org(self, client: AsyncClient, rbac_org, db_session: AsyncSession):
        _, org = rbac_org
        _, _, token = await _create_member_token(db_session, org.id, "viewer", "viewer3_rbac@example.com")

        res = await client.request(
            "DELETE",
            f"/api/v1/orgs/{org.id}",
            json={"confirmation": org.slug},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_invite_members(self, client: AsyncClient, rbac_org, db_session: AsyncSession):
        _, org = rbac_org
        _, _, token = await _create_member_token(db_session, org.id, "viewer", "viewer4_rbac@example.com")

        res = await client.post(
            f"/api/v1/orgs/{org.id}/invitations",
            json={"email": "new@example.com", "role": "employee"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_create_department(self, client: AsyncClient, rbac_org, db_session: AsyncSession):
        _, org = rbac_org
        _, _, token = await _create_member_token(db_session, org.id, "viewer", "viewer5_rbac@example.com")

        res = await client.post(
            f"/api/v1/orgs/{org.id}/departments",
            json={"name": "Finance"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_list_api_keys(self, client: AsyncClient, rbac_org, db_session: AsyncSession):
        _, org = rbac_org
        _, _, token = await _create_member_token(db_session, org.id, "viewer", "viewer6_rbac@example.com")

        res = await client.get(
            f"/api/v1/orgs/{org.id}/api-keys",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403


# ── admin permissions ──────────────────────────────────────────────────────────

class TestAdminPermissions:
    @pytest.mark.asyncio
    async def test_admin_can_update_org(self, client: AsyncClient, rbac_org, db_session: AsyncSession):
        _, org = rbac_org
        _, _, token = await _create_member_token(db_session, org.id, "admin", "admin_rbac@example.com")

        res = await client.patch(
            f"/api/v1/orgs/{org.id}",
            json={"name": "Updated by Admin"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_cannot_delete_org(self, client: AsyncClient, rbac_org, db_session: AsyncSession):
        _, org = rbac_org
        _, _, token = await _create_member_token(db_session, org.id, "admin", "admin2_rbac@example.com")

        res = await client.request(
            "DELETE",
            f"/api/v1/orgs/{org.id}",
            json={"confirmation": org.slug},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_cannot_transfer_ownership(self, client: AsyncClient, rbac_org, db_session: AsyncSession):
        owner_user, org = rbac_org
        _, _, admin_token = await _create_member_token(db_session, org.id, "admin", "admin3_rbac@example.com")

        res = await client.post(
            f"/api/v1/orgs/{org.id}/transfer-ownership",
            json={"new_owner_user_id": str(owner_user.id)},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_cannot_assign_admin_role(self, client: AsyncClient, rbac_org, db_session: AsyncSession):
        """Admin (rank 5) cannot promote someone to admin rank 5 — only owner can."""
        _, org = rbac_org
        _, admin_member, admin_token = await _create_member_token(db_session, org.id, "admin", "admin4_rbac@example.com")
        employee_user, _, _ = await _create_member_token(db_session, org.id, "employee", "employee_rbac@example.com")

        # Admin trying to assign admin role (same rank as themselves) — should be blocked
        res = await client.patch(
            f"/api/v1/orgs/{org.id}/members/{employee_user.id}",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Admin cannot assign a role equal to or higher than their own
        assert res.status_code == 403


# ── ownership transfer ─────────────────────────────────────────────────────────

class TestOwnershipTransfer:
    @pytest.mark.asyncio
    async def test_owner_can_transfer_and_is_demoted(
        self, client: AsyncClient, rbac_org, db_session: AsyncSession
    ):
        owner_user, org = rbac_org
        new_owner_user, _, _ = await _create_member_token(
            db_session, org.id, "admin", "new_owner_rbac@example.com"
        )

        owner_token = create_access_token(
            user_id=owner_user.id, org_id=org.id, session_id=uuid4(),
            role="owner", scope="org",
        )

        res = await client.post(
            f"/api/v1/orgs/{org.id}/transfer-ownership",
            json={"new_owner_user_id": str(new_owner_user.id)},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert res.status_code == 200

        # Verify new owner membership
        result = await db_session.execute(
            __import__("sqlalchemy").select(OrgMember).where(
                OrgMember.organization_id == org.id,
                OrgMember.user_id == new_owner_user.id,
            )
        )
        new_member = result.scalar_one_or_none()
        assert new_member is not None
        assert new_member.role == "owner"

        # Verify old owner was demoted to admin
        result2 = await db_session.execute(
            __import__("sqlalchemy").select(OrgMember).where(
                OrgMember.organization_id == org.id,
                OrgMember.user_id == owner_user.id,
            )
        )
        old_member = result2.scalar_one_or_none()
        assert old_member is not None
        assert old_member.role == "admin"


# ── org suspended ─────────────────────────────────────────────────────────────

class TestSuspendedOrg:
    @pytest.mark.asyncio
    async def test_suspended_org_blocks_all_requests(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = User(
            email="suspended@example.com",
            hashed_password=hash_password("SecurePass123!"),
            full_name="Suspended User",
            is_verified=True, is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        org = Organization(
            name="Suspended Org", slug="suspended-org", plan="free",
            is_active=False,  # suspended
            settings={}, storage_used_bytes=0,
        )
        db_session.add(org)
        await db_session.flush()

        member = OrgMember(organization_id=org.id, user_id=user.id, role="owner")
        db_session.add(member)
        await db_session.flush()

        token = create_access_token(
            user_id=user.id, org_id=org.id, session_id=uuid4(),
            role="owner", scope="org",
        )

        res = await client.get(
            f"/api/v1/orgs/{org.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "ORG_SUSPENDED"
