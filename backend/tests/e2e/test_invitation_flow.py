"""
E2E test: Full invitation → accept → role change → remove cycle.

This tests the complete flow without any mocks. Requires a running DB and Redis.
"""
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, generate_token, hash_token
from app.modules.auth.models import User
from app.modules.organizations.models import Organization, OrgMember, Invitation


@pytest_asyncio.fixture
async def alice_with_org(db_session: AsyncSession):
    """Alice is an org owner."""
    alice = User(
        email="alice_e2e@example.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="Alice E2E",
        is_verified=True, is_active=True,
    )
    db_session.add(alice)
    await db_session.flush()

    org = Organization(
        name="Alice's Company", slug="alice-company", plan="free", is_active=True,
        settings={}, storage_used_bytes=0,
    )
    db_session.add(org)
    await db_session.flush()

    member = OrgMember(organization_id=org.id, user_id=alice.id, role="owner")
    db_session.add(member)
    await db_session.flush()

    token = create_access_token(
        user_id=alice.id, org_id=org.id, session_id=uuid4(),
        role="owner", scope="org",
    )
    return alice, org, token


@pytest_asyncio.fixture
async def bob(db_session: AsyncSession):
    """Bob will be invited."""
    bob = User(
        email="bob_e2e@example.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="Bob E2E",
        is_verified=True, is_active=True,
    )
    db_session.add(bob)
    await db_session.flush()
    return bob


class TestInvitationFlow:
    @pytest.mark.asyncio
    async def test_full_invite_accept_promote_remove_cycle(
        self,
        client: AsyncClient,
        alice_with_org,
        bob,
        db_session: AsyncSession,
    ):
        alice, org, alice_token = alice_with_org

        # ── Step 1: Alice invites Bob ──────────────────────────────────────────
        invite_res = await client.post(
            f"/api/v1/orgs/{org.id}/invitations",
            json={"email": bob.email, "role": "analyst"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert invite_res.status_code == 201
        invitation_data = invite_res.json()
        assert invitation_data["email"] == bob.email

        # ── Step 2: Verify invitation in DB ───────────────────────────────────
        result = await db_session.execute(
            select(Invitation).where(
                Invitation.organization_id == org.id,
                Invitation.accepted_at.is_(None),
            )
        )
        invitation = result.scalar_one_or_none()
        assert invitation is not None
        assert invitation.role == "analyst"

        # ── Step 3: Bob gets a token for a separate org context ───────────────
        # For the accept flow, Bob calls the public endpoint with his own token
        # We need the plaintext invitation token (which was sent via email in prod)
        # For the test, we'll rebuild the token by inserting it directly
        plaintext_token = generate_token()
        invitation.token_hash = hash_token(plaintext_token)
        await db_session.flush()

        bob_token = create_access_token(
            user_id=bob.id,
            org_id=uuid4(),  # placeholder org before acceptance
            session_id=uuid4(),
            role="viewer",
            scope="org",
        )

        accept_res = await client.post(
            "/api/v1/invitations/accept",
            json={"token": plaintext_token},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert accept_res.status_code == 200
        assert "organization" in accept_res.json()

        # ── Step 4: Verify Bob is now a member ────────────────────────────────
        result = await db_session.execute(
            select(OrgMember).where(
                OrgMember.organization_id == org.id,
                OrgMember.user_id == bob.id,
            )
        )
        bob_member = result.scalar_one_or_none()
        assert bob_member is not None
        assert bob_member.role == "analyst"

        # ── Step 5: Alice promotes Bob to manager ─────────────────────────────
        promote_res = await client.patch(
            f"/api/v1/orgs/{org.id}/members/{bob.id}",
            json={"role": "manager"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert promote_res.status_code == 200
        assert promote_res.json()["role"] == "manager"

        # ── Step 6: Alice removes Bob ─────────────────────────────────────────
        remove_res = await client.delete(
            f"/api/v1/orgs/{org.id}/members/{bob.id}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert remove_res.status_code == 204

        # ── Step 7: Verify Bob is no longer a member ──────────────────────────
        result = await db_session.execute(
            select(OrgMember).where(
                OrgMember.organization_id == org.id,
                OrgMember.user_id == bob.id,
            )
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_expired_invitation_is_rejected(
        self,
        client: AsyncClient,
        alice_with_org,
        bob,
        db_session: AsyncSession,
    ):
        from datetime import datetime, timezone, timedelta

        alice, org, alice_token = alice_with_org

        plaintext_token = generate_token()
        expired_inv = Invitation(
            organization_id=org.id,
            invited_by=alice.id,
            email=bob.email,
            role="analyst",
            token_hash=hash_token(plaintext_token),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # already expired
        )
        db_session.add(expired_inv)
        await db_session.flush()

        bob_token = create_access_token(
            user_id=bob.id, org_id=uuid4(), session_id=uuid4(),
            role="viewer", scope="org",
        )

        accept_res = await client.post(
            "/api/v1/invitations/accept",
            json={"token": plaintext_token},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert accept_res.status_code == 404
