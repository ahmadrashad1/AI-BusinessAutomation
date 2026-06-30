"""
Tenant isolation integration tests.

For every resource type introduced in M2, verifies that users in Org A
cannot read, update, or delete Org B's resources — all such attempts must
return 404 (not 403), preventing existence leakage.
"""
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.modules.auth.models import User
from app.modules.organizations.models import Organization, OrgMember, Department, APIKey


# ── setup two independent orgs ─────────────────────────────────────────────────

@pytest_asyncio.fixture
async def org_a(db_session: AsyncSession):
    user = User(
        email="owner_a@example.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="Owner A",
        is_verified=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    org = Organization(
        name="Org A", slug="org-a", plan="free", is_active=True,
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
    return user, org, token


@pytest_asyncio.fixture
async def org_b(db_session: AsyncSession):
    user = User(
        email="owner_b@example.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="Owner B",
        is_verified=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    org = Organization(
        name="Org B", slug="org-b", plan="free", is_active=True,
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
    return user, org, token


@pytest_asyncio.fixture
async def org_b_dept(db_session: AsyncSession, org_b):
    _, org, _ = org_b
    dept = Department(organization_id=org.id, name="Finance")
    db_session.add(dept)
    await db_session.flush()
    return dept


# ── org isolation ──────────────────────────────────────────────────────────────

class TestOrgIsolation:
    @pytest.mark.asyncio
    async def test_org_a_cannot_get_org_b_details(
        self, client: AsyncClient, org_a, org_b
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.get(
            f"/api/v1/orgs/{org_b_obj.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_org_a_cannot_patch_org_b(
        self, client: AsyncClient, org_a, org_b
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.patch(
            f"/api/v1/orgs/{org_b_obj.id}",
            json={"name": "Hacked Name"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_org_a_cannot_delete_org_b(
        self, client: AsyncClient, org_a, org_b
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.request(
            "DELETE",
            f"/api/v1/orgs/{org_b_obj.id}",
            json={"confirmation": org_b_obj.slug},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_org_a_cannot_list_org_b_members(
        self, client: AsyncClient, org_a, org_b
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.get(
            f"/api/v1/orgs/{org_b_obj.id}/members",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404


# ── member isolation ──────────────────────────────────────────────────────────

class TestMemberIsolation:
    @pytest.mark.asyncio
    async def test_org_a_cannot_invite_to_org_b(
        self, client: AsyncClient, org_a, org_b
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.post(
            f"/api/v1/orgs/{org_b_obj.id}/invitations",
            json={"email": "spy@example.com", "role": "analyst"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_org_a_cannot_list_org_b_invitations(
        self, client: AsyncClient, org_a, org_b
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.get(
            f"/api/v1/orgs/{org_b_obj.id}/invitations",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404


# ── department isolation ───────────────────────────────────────────────────────

class TestDepartmentIsolation:
    @pytest.mark.asyncio
    async def test_org_a_cannot_list_org_b_departments(
        self, client: AsyncClient, org_a, org_b
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.get(
            f"/api/v1/orgs/{org_b_obj.id}/departments",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_org_a_cannot_create_dept_in_org_b(
        self, client: AsyncClient, org_a, org_b
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.post(
            f"/api/v1/orgs/{org_b_obj.id}/departments",
            json={"name": "Finance"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_org_a_cannot_update_org_b_dept(
        self, client: AsyncClient, org_a, org_b, org_b_dept
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.patch(
            f"/api/v1/orgs/{org_b_obj.id}/departments/{org_b_dept.id}",
            json={"name": "Hacked"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_org_a_cannot_delete_org_b_dept(
        self, client: AsyncClient, org_a, org_b, org_b_dept
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.delete(
            f"/api/v1/orgs/{org_b_obj.id}/departments/{org_b_dept.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404


# ── API key isolation ─────────────────────────────────────────────────────────

class TestAPIKeyIsolation:
    @pytest.mark.asyncio
    async def test_org_a_cannot_list_org_b_api_keys(
        self, client: AsyncClient, org_a, org_b
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.get(
            f"/api/v1/orgs/{org_b_obj.id}/api-keys",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_org_a_cannot_create_api_key_for_org_b(
        self, client: AsyncClient, org_a, org_b
    ):
        _, _, token_a = org_a
        _, org_b_obj, _ = org_b
        res = await client.post(
            f"/api/v1/orgs/{org_b_obj.id}/api-keys",
            json={"label": "Spy Key", "scopes": ["workflow:read"]},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 404
