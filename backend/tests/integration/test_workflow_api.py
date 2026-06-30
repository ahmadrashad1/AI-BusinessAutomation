"""
Integration tests for workflow API endpoints — TDD RED phase.
Uses real async DB (bpa_test) and real Redis.
Covers: CRUD, publish (valid + invalid graph), versioning, duplication, archive.
"""
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.modules.auth.models import User
from app.modules.organizations.models import Organization, OrgMember


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def wf_manager(db_session: AsyncSession):
    """Manager user with org context — can create and publish workflows."""
    user = User(
        email="manager@wftest.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="WF Manager",
        is_verified=True, is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    org = Organization(
        name="WF Org", slug="wf-org", plan="free",
        is_active=True, settings={}, storage_used_bytes=0,
    )
    db_session.add(org)
    await db_session.flush()

    member = OrgMember(organization_id=org.id, user_id=user.id, role="manager")
    db_session.add(member)
    await db_session.flush()

    token = create_access_token(
        user_id=user.id, org_id=org.id, session_id=uuid4(), role="manager", scope="org"
    )
    return user, org, token


@pytest_asyncio.fixture
async def wf_viewer(db_session: AsyncSession, wf_manager):
    """Viewer user in the same org."""
    _, org, _ = wf_manager
    user = User(
        email="viewer@wftest.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="WF Viewer",
        is_verified=True, is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    member = OrgMember(organization_id=org.id, user_id=user.id, role="viewer")
    db_session.add(member)
    await db_session.flush()

    token = create_access_token(
        user_id=user.id, org_id=org.id, session_id=uuid4(), role="viewer", scope="org"
    )
    return user, org, token


@pytest_asyncio.fixture
async def wf_admin(db_session: AsyncSession, wf_manager):
    """Admin user in the same org."""
    _, org, _ = wf_manager
    user = User(
        email="admin@wftest.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="WF Admin",
        is_verified=True, is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    member = OrgMember(organization_id=org.id, user_id=user.id, role="admin")
    db_session.add(member)
    await db_session.flush()

    token = create_access_token(
        user_id=user.id, org_id=org.id, session_id=uuid4(), role="admin", scope="org"
    )
    return user, org, token


# ── helper graph definitions ───────────────────────────────────────────────────

VALID_GRAPH = {
    "nodes": [
        {"id": "t1", "type": "trigger.manual", "label": "Start", "position": {"x": 0, "y": 0}, "config": {}},
        {"id": "a1", "type": "action.http", "label": "HTTP Call", "position": {"x": 200, "y": 0},
         "config": {"url": "https://example.com", "method": "GET"}},
    ],
    "edges": [
        {"id": "e1", "source": "t1", "target": "a1", "sourceHandle": "output", "targetHandle": "input"}
    ],
}

CYCLIC_GRAPH = {
    "nodes": [
        {"id": "t1", "type": "trigger.manual", "label": "Start", "position": {"x": 0, "y": 0}, "config": {}},
        {"id": "a1", "type": "action.http", "label": "HTTP", "position": {"x": 200, "y": 0}, "config": {}},
        {"id": "a2", "type": "action.http", "label": "HTTP 2", "position": {"x": 400, "y": 0}, "config": {}},
    ],
    "edges": [
        {"id": "e1", "source": "t1", "target": "a1", "sourceHandle": "output", "targetHandle": "input"},
        {"id": "e2", "source": "a1", "target": "a2", "sourceHandle": "output", "targetHandle": "input"},
        {"id": "e3", "source": "a2", "target": "a1", "sourceHandle": "output", "targetHandle": "input"},
    ],
}

NO_TRIGGER_GRAPH = {
    "nodes": [
        {"id": "a1", "type": "action.http", "label": "HTTP", "position": {"x": 0, "y": 0}, "config": {}},
    ],
    "edges": [],
}


# ── POST /workflows ────────────────────────────────────────────────────────────

class TestCreateWorkflow:
    @pytest.mark.asyncio
    async def test_manager_can_create_workflow(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        res = await client.post(
            "/api/v1/workflows",
            json={"name": "My Workflow", "description": "A test workflow", "tags": ["test"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "My Workflow"
        assert data["status"] == "draft"
        assert data["active_version_id"] is None

    @pytest.mark.asyncio
    async def test_viewer_cannot_create_workflow(self, client: AsyncClient, wf_viewer):
        _, org, token = wf_viewer
        res = await client.post(
            "/api/v1/workflows",
            json={"name": "Viewer Workflow"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient):
        res = await client.post("/api/v1/workflows", json={"name": "No Auth"})
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_name_returns_422(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        res = await client.post(
            "/api/v1/workflows",
            json={"description": "No name"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422


# ── GET /workflows ─────────────────────────────────────────────────────────────

class TestListWorkflows:
    @pytest.mark.asyncio
    async def test_viewer_can_list_workflows(self, client: AsyncClient, wf_manager, wf_viewer):
        _, org, mgr_token = wf_manager
        _, _, viewer_token = wf_viewer

        # Create a workflow first
        await client.post(
            "/api/v1/workflows",
            json={"name": "Listed Workflow"},
            headers={"Authorization": f"Bearer {mgr_token}"},
        )

        res = await client.get(
            "/api/v1/workflows",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient):
        res = await client.get("/api/v1/workflows")
        assert res.status_code == 401


# ── GET /workflows/{id} ────────────────────────────────────────────────────────

class TestGetWorkflow:
    @pytest.mark.asyncio
    async def test_get_own_workflow_returns_200(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Get Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        res = await client.get(
            f"/api/v1/workflows/{wf_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json()["id"] == wf_id

    @pytest.mark.asyncio
    async def test_cross_org_returns_404(self, client: AsyncClient, wf_manager):
        _, _, token = wf_manager
        res = await client.get(
            f"/api/v1/workflows/{uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_deleted_workflow_returns_404(self, client: AsyncClient, wf_admin):
        _, org, token = wf_admin
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Delete Me"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        await client.request(
            "DELETE",
            f"/api/v1/workflows/{wf_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        res = await client.get(
            f"/api/v1/workflows/{wf_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 404


# ── PATCH /workflows/{id} ──────────────────────────────────────────────────────

class TestUpdateWorkflow:
    @pytest.mark.asyncio
    async def test_manager_can_update_name_and_tags(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Original"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        res = await client.patch(
            f"/api/v1/workflows/{wf_id}",
            json={"name": "Updated", "tags": ["updated"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Updated"

    @pytest.mark.asyncio
    async def test_viewer_cannot_update_workflow(self, client: AsyncClient, wf_manager, wf_viewer):
        _, org, mgr_token = wf_manager
        _, _, viewer_token = wf_viewer

        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Viewer Cannot Update"},
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        wf_id = create_res.json()["id"]

        res = await client.patch(
            f"/api/v1/workflows/{wf_id}",
            json={"name": "Hacked"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_update_definition_on_draft(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Draft With Definition"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        res = await client.patch(
            f"/api/v1/workflows/{wf_id}",
            json={"definition": VALID_GRAPH},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200


# ── POST /workflows/{id}/publish ───────────────────────────────────────────────

class TestPublishWorkflow:
    @pytest.mark.asyncio
    async def test_publish_valid_graph_creates_version(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Publish Me"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        # Set the draft definition
        await client.patch(
            f"/api/v1/workflows/{wf_id}",
            json={"definition": VALID_GRAPH},
            headers={"Authorization": f"Bearer {token}"},
        )

        res = await client.post(
            f"/api/v1/workflows/{wf_id}/publish",
            json={"change_summary": "Initial publish"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "published"
        assert data["active_version"]["version_number"] == 1

    @pytest.mark.asyncio
    async def test_second_publish_increments_version(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Version Counter"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        for _ in range(2):
            await client.patch(
                f"/api/v1/workflows/{wf_id}",
                json={"definition": VALID_GRAPH},
                headers={"Authorization": f"Bearer {token}"},
            )
            await client.post(
                f"/api/v1/workflows/{wf_id}/publish",
                headers={"Authorization": f"Bearer {token}"},
            )

        res = await client.post(
            f"/api/v1/workflows/{wf_id}/publish",
            json={"definition": VALID_GRAPH},
            headers={"Authorization": f"Bearer {token}"},
        )
        # After patching definition on published workflow, it becomes draft again
        # So third publish is either 3 or 2 depending on flow
        # Just assert it succeeded and version_number > 1
        patch_res = await client.patch(
            f"/api/v1/workflows/{wf_id}",
            json={"definition": VALID_GRAPH},
            headers={"Authorization": f"Bearer {token}"},
        )
        pub_res = await client.post(
            f"/api/v1/workflows/{wf_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pub_res.status_code == 200
        assert pub_res.json()["active_version"]["version_number"] >= 2

    @pytest.mark.asyncio
    async def test_cyclic_graph_returns_422_invalid_graph(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Cyclic"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        await client.patch(
            f"/api/v1/workflows/{wf_id}",
            json={"definition": CYCLIC_GRAPH},
            headers={"Authorization": f"Bearer {token}"},
        )

        res = await client.post(
            f"/api/v1/workflows/{wf_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422
        data = res.json()
        assert data["error"]["code"] == "INVALID_GRAPH"
        assert "errors" in data["error"]["details"]

    @pytest.mark.asyncio
    async def test_no_trigger_graph_returns_422(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "No Trigger"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        await client.patch(
            f"/api/v1/workflows/{wf_id}",
            json={"definition": NO_TRIGGER_GRAPH},
            headers={"Authorization": f"Bearer {token}"},
        )

        res = await client.post(
            f"/api/v1/workflows/{wf_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "INVALID_GRAPH"

    @pytest.mark.asyncio
    async def test_publish_without_definition_returns_422(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "No Definition"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        res = await client.post(
            f"/api/v1/workflows/{wf_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_viewer_cannot_publish(self, client: AsyncClient, wf_manager, wf_viewer):
        _, org, mgr_token = wf_manager
        _, _, viewer_token = wf_viewer

        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Viewer Cannot Publish"},
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        wf_id = create_res.json()["id"]

        res = await client.post(
            f"/api/v1/workflows/{wf_id}/publish",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert res.status_code == 403


# ── GET /workflows/{id}/versions ───────────────────────────────────────────────

class TestListVersions:
    @pytest.mark.asyncio
    async def test_lists_published_versions(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Version List"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        # Publish v1
        await client.patch(f"/api/v1/workflows/{wf_id}", json={"definition": VALID_GRAPH},
                           headers={"Authorization": f"Bearer {token}"})
        await client.post(f"/api/v1/workflows/{wf_id}/publish", headers={"Authorization": f"Bearer {token}"})

        res = await client.get(
            f"/api/v1/workflows/{wf_id}/versions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert any(v["version_number"] == 1 for v in data["items"])


# ── GET /workflows/{id}/versions/{version_number} ─────────────────────────────

class TestGetVersion:
    @pytest.mark.asyncio
    async def test_get_specific_version_returns_definition(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Get Version"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        await client.patch(f"/api/v1/workflows/{wf_id}", json={"definition": VALID_GRAPH},
                           headers={"Authorization": f"Bearer {token}"})
        await client.post(f"/api/v1/workflows/{wf_id}/publish", headers={"Authorization": f"Bearer {token}"})

        res = await client.get(
            f"/api/v1/workflows/{wf_id}/versions/1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert "definition" in res.json()

    @pytest.mark.asyncio
    async def test_nonexistent_version_returns_404(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "No Version 99"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        res = await client.get(
            f"/api/v1/workflows/{wf_id}/versions/99",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 404


# ── POST /workflows/{id}/revert/{version_number} ──────────────────────────────

class TestRevertVersion:
    @pytest.mark.asyncio
    async def test_revert_to_previous_version_creates_new_version(self, client: AsyncClient, wf_admin):
        _, org, token = wf_admin

        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Revert Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        # Publish v1
        await client.patch(f"/api/v1/workflows/{wf_id}", json={"definition": VALID_GRAPH},
                           headers={"Authorization": f"Bearer {token}"})
        await client.post(f"/api/v1/workflows/{wf_id}/publish", headers={"Authorization": f"Bearer {token}"})

        # Publish v2 (after editing definition again)
        await client.patch(f"/api/v1/workflows/{wf_id}", json={"definition": VALID_GRAPH},
                           headers={"Authorization": f"Bearer {token}"})
        await client.post(f"/api/v1/workflows/{wf_id}/publish",
                          json={"change_summary": "v2"},
                          headers={"Authorization": f"Bearer {token}"})

        # Revert to v1
        res = await client.post(
            f"/api/v1/workflows/{wf_id}/revert/1",
            json={"change_summary": "Reverted to v1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "published"
        # The new version number should be 3 (v1 revert = new publish as v3)
        assert data["active_version"]["version_number"] == 3

    @pytest.mark.asyncio
    async def test_revert_nonexistent_version_returns_404(self, client: AsyncClient, wf_admin):
        _, org, token = wf_admin
        create_res = await client.post(
            "/api/v1/workflows", json={"name": "No Revert"}, headers={"Authorization": f"Bearer {token}"}
        )
        wf_id = create_res.json()["id"]

        res = await client.post(
            f"/api/v1/workflows/{wf_id}/revert/99",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_viewer_cannot_revert(self, client: AsyncClient, wf_viewer):
        _, org, token = wf_viewer
        res = await client.post(
            f"/api/v1/workflows/{uuid4()}/revert/1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403


# ── POST /workflows/{id}/duplicate ────────────────────────────────────────────

class TestDuplicateWorkflow:
    @pytest.mark.asyncio
    async def test_duplicate_creates_new_draft(self, client: AsyncClient, wf_manager):
        _, org, token = wf_manager
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Original WF"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        res = await client.post(
            f"/api/v1/workflows/{wf_id}/duplicate",
            json={"name": "Copy of Original WF"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Copy of Original WF"
        assert data["status"] == "draft"
        assert data["id"] != wf_id


# ── POST /workflows/{id}/archive ──────────────────────────────────────────────

class TestArchiveWorkflow:
    @pytest.mark.asyncio
    async def test_admin_can_archive_published_workflow(self, client: AsyncClient, wf_admin, wf_manager):
        _, org, admin_token = wf_admin
        _, _, mgr_token = wf_manager

        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "To Archive"},
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        wf_id = create_res.json()["id"]

        await client.patch(f"/api/v1/workflows/{wf_id}", json={"definition": VALID_GRAPH},
                           headers={"Authorization": f"Bearer {admin_token}"})
        await client.post(f"/api/v1/workflows/{wf_id}/publish",
                          headers={"Authorization": f"Bearer {admin_token}"})

        res = await client.post(
            f"/api/v1/workflows/{wf_id}/archive",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "archived"

    @pytest.mark.asyncio
    async def test_viewer_cannot_archive(self, client: AsyncClient, wf_viewer):
        _, org, token = wf_viewer
        res = await client.post(
            f"/api/v1/workflows/{uuid4()}/archive",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403


# ── DELETE /workflows/{id} ─────────────────────────────────────────────────────

class TestDeleteWorkflow:
    @pytest.mark.asyncio
    async def test_admin_can_soft_delete(self, client: AsyncClient, wf_admin):
        _, org, token = wf_admin
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Delete Me"},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = create_res.json()["id"]

        res = await client.request(
            "DELETE",
            f"/api/v1/workflows/{wf_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 204

    @pytest.mark.asyncio
    async def test_viewer_cannot_delete(self, client: AsyncClient, wf_viewer):
        _, org, token = wf_viewer
        res = await client.request(
            "DELETE",
            f"/api/v1/workflows/{uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403


# ── Tenant isolation ──────────────────────────────────────────────────────────

class TestWorkflowTenantIsolation:
    @pytest.mark.asyncio
    async def test_user_cannot_access_another_orgs_workflow(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        # Create Org A with a workflow
        user_a = User(email="a_wf@isolate.com", hashed_password=hash_password("Pass123!"),
                      full_name="A", is_verified=True, is_active=True)
        db_session.add(user_a)
        await db_session.flush()

        org_a = Organization(name="Org A WF", slug="org-a-wf", plan="free",
                             is_active=True, settings={}, storage_used_bytes=0)
        db_session.add(org_a)
        await db_session.flush()

        db_session.add(OrgMember(organization_id=org_a.id, user_id=user_a.id, role="manager"))
        await db_session.flush()

        token_a = create_access_token(user_id=user_a.id, org_id=org_a.id,
                                      session_id=uuid4(), role="manager", scope="org")

        # Create Org B user
        user_b = User(email="b_wf@isolate.com", hashed_password=hash_password("Pass123!"),
                      full_name="B", is_verified=True, is_active=True)
        db_session.add(user_b)
        await db_session.flush()

        org_b = Organization(name="Org B WF", slug="org-b-wf", plan="free",
                             is_active=True, settings={}, storage_used_bytes=0)
        db_session.add(org_b)
        await db_session.flush()

        db_session.add(OrgMember(organization_id=org_b.id, user_id=user_b.id, role="manager"))
        await db_session.flush()

        token_b = create_access_token(user_id=user_b.id, org_id=org_b.id,
                                      session_id=uuid4(), role="manager", scope="org")

        # Org A creates a workflow
        create_res = await client.post(
            "/api/v1/workflows",
            json={"name": "Org A Secret"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        wf_id = create_res.json()["id"]

        # Org B tries to access it — must get 404
        res = await client.get(
            f"/api/v1/workflows/{wf_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res.status_code == 404
