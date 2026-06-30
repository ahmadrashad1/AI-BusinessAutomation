"""
Unit tests for organizations service.

All DB access is mocked via AsyncMock — no real database required.
Tests are written FIRST per TDD discipline; they will fail until service is implemented.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnprocessableError


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_org(org_id=None, slug="acme-corp", is_active=True):
    org = MagicMock()
    org.id = org_id or uuid4()
    org.name = "Acme Corp"
    org.slug = slug
    org.plan = "free"
    org.is_active = is_active
    org.settings = {}
    org.storage_used_bytes = 0
    org.created_at = datetime.now(timezone.utc)
    org.updated_at = datetime.now(timezone.utc)
    return org


def _make_member(org_id=None, user_id=None, role="owner"):
    m = MagicMock()
    m.id = uuid4()
    m.organization_id = org_id or uuid4()
    m.user_id = user_id or uuid4()
    m.role = role
    m.department_id = None
    m.joined_at = datetime.now(timezone.utc)
    return m


def _make_user(user_id=None, email="alice@example.com", is_active=True):
    u = MagicMock()
    u.id = user_id or uuid4()
    u.email = email
    u.full_name = "Alice"
    u.is_active = is_active
    return u


def _make_invitation(org_id=None, email="bob@example.com", role="analyst", accepted=False, expired=False):
    inv = MagicMock()
    inv.id = uuid4()
    inv.organization_id = org_id or uuid4()
    inv.email = email
    inv.role = role
    inv.token_hash = "hashed"
    inv.accepted_at = datetime.now(timezone.utc) if accepted else None
    inv.expires_at = (
        datetime.now(timezone.utc) - timedelta(hours=1) if expired
        else datetime.now(timezone.utc) + timedelta(hours=47)
    )
    inv.created_at = datetime.now(timezone.utc)
    return inv


# ── create_org ────────────────────────────────────────────────────────────────

class TestCreateOrg:
    @pytest.mark.asyncio
    async def test_creates_org_and_owner_membership(self):
        from app.modules.organizations.service import create_org
        from app.modules.organizations.schemas import OrgCreate

        db = AsyncMock()
        user_id = uuid4()
        payload = OrgCreate(name="Acme Corp", slug="acme-corp")

        # Simulate no slug conflict
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        result = await create_org(db, user_id=user_id, payload=payload)

        assert db.add.call_count >= 2  # org + member
        assert db.flush.called

    @pytest.mark.asyncio
    async def test_raises_conflict_if_slug_taken(self):
        from app.modules.organizations.service import create_org
        from app.modules.organizations.schemas import OrgCreate

        db = AsyncMock()
        payload = OrgCreate(name="Acme Corp", slug="acme-corp")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = _make_org(slug="acme-corp")
        db.execute.return_value = mock_result

        with pytest.raises(ConflictError):
            await create_org(db, user_id=uuid4(), payload=payload)

    @pytest.mark.asyncio
    async def test_auto_generates_slug_from_name(self):
        from app.modules.organizations.service import create_org
        from app.modules.organizations.schemas import OrgCreate

        db = AsyncMock()
        payload = OrgCreate(name="Acme Corp")  # no slug

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        await create_org(db, user_id=uuid4(), payload=payload)
        assert db.add.called


# ── get_org ───────────────────────────────────────────────────────────────────

class TestGetOrg:
    @pytest.mark.asyncio
    async def test_returns_org_for_own_org(self):
        from app.modules.organizations.service import get_org

        db = AsyncMock()
        org_id = uuid4()
        org = _make_org(org_id=org_id)
        db.get.return_value = org

        result = await get_org(db, org_id=org_id, requesting_org_id=org_id)

        assert result.id == org_id

    @pytest.mark.asyncio
    async def test_raises_404_for_cross_org_access(self):
        from app.modules.organizations.service import get_org

        db = AsyncMock()
        org_id = uuid4()
        other_org_id = uuid4()
        org = _make_org(org_id=org_id)
        db.get.return_value = org

        with pytest.raises(NotFoundError):
            await get_org(db, org_id=org_id, requesting_org_id=other_org_id)

    @pytest.mark.asyncio
    async def test_raises_404_when_org_does_not_exist(self):
        from app.modules.organizations.service import get_org

        db = AsyncMock()
        org_id = uuid4()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            await get_org(db, org_id=org_id, requesting_org_id=org_id)


# ── transfer_ownership ────────────────────────────────────────────────────────

class TestTransferOwnership:
    @pytest.mark.asyncio
    async def test_demotes_current_owner_to_admin(self):
        from app.modules.organizations.service import transfer_ownership

        db = AsyncMock()
        org_id = uuid4()
        caller_user_id = uuid4()
        new_owner_user_id = uuid4()

        caller_member = _make_member(org_id=org_id, user_id=caller_user_id, role="owner")
        new_owner_member = _make_member(org_id=org_id, user_id=new_owner_user_id, role="admin")

        def side_effect(stmt):
            mock = MagicMock()
            # First call returns caller member, second returns new owner member
            return mock

        mock_caller_result = MagicMock()
        mock_caller_result.scalar_one_or_none.return_value = caller_member
        mock_new_owner_result = MagicMock()
        mock_new_owner_result.scalar_one_or_none.return_value = new_owner_member

        db.execute.side_effect = [mock_caller_result, mock_new_owner_result]

        await transfer_ownership(
            db,
            org_id=org_id,
            new_owner_user_id=new_owner_user_id,
            caller_user_id=caller_user_id,
        )

        assert caller_member.role == "admin"
        assert new_owner_member.role == "owner"

    @pytest.mark.asyncio
    async def test_raises_404_if_new_owner_not_in_org(self):
        from app.modules.organizations.service import transfer_ownership

        db = AsyncMock()
        org_id = uuid4()
        caller_user_id = uuid4()
        new_owner_user_id = uuid4()

        caller_member = _make_member(org_id=org_id, user_id=caller_user_id, role="owner")

        mock_caller_result = MagicMock()
        mock_caller_result.scalar_one_or_none.return_value = caller_member
        mock_new_owner_result = MagicMock()
        mock_new_owner_result.scalar_one_or_none.return_value = None

        db.execute.side_effect = [mock_caller_result, mock_new_owner_result]

        with pytest.raises(NotFoundError):
            await transfer_ownership(
                db,
                org_id=org_id,
                new_owner_user_id=new_owner_user_id,
                caller_user_id=caller_user_id,
            )


# ── invite_member ─────────────────────────────────────────────────────────────

class TestInviteMember:
    @pytest.mark.asyncio
    async def test_creates_invitation(self):
        from app.modules.organizations.service import invite_member
        from app.modules.organizations.schemas import InvitationCreate

        db = AsyncMock()
        org_id = uuid4()
        invited_by = uuid4()
        payload = InvitationCreate(email="bob@example.com", role="analyst")

        # No existing pending invite
        mock_existing = MagicMock()
        mock_existing.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_existing

        result = await invite_member(db, org_id=org_id, invited_by=invited_by, payload=payload)

        assert db.add.called
        assert db.flush.called

    @pytest.mark.asyncio
    async def test_raises_conflict_if_pending_invite_exists(self):
        from app.modules.organizations.service import invite_member
        from app.modules.organizations.schemas import InvitationCreate

        db = AsyncMock()
        org_id = uuid4()
        payload = InvitationCreate(email="bob@example.com", role="analyst")

        existing_invite = _make_invitation(org_id=org_id, email="bob@example.com")
        mock_existing = MagicMock()
        mock_existing.scalar_one_or_none.return_value = existing_invite
        db.execute.return_value = mock_existing

        with pytest.raises(ConflictError):
            await invite_member(db, org_id=org_id, invited_by=uuid4(), payload=payload)

    @pytest.mark.asyncio
    async def test_raises_validation_error_for_owner_role(self):
        from app.modules.organizations.schemas import InvitationCreate

        with pytest.raises(Exception):
            InvitationCreate(email="boss@example.com", role="owner")


# ── accept_invitation ─────────────────────────────────────────────────────────

class TestAcceptInvitation:
    @pytest.mark.asyncio
    async def test_creates_membership_on_valid_token(self):
        from app.modules.organizations.service import accept_invitation

        db = AsyncMock()
        org_id = uuid4()
        user_id = uuid4()
        token = "plaintext-token"

        invitation = _make_invitation(org_id=org_id, email="bob@example.com", role="analyst")

        mock_inv_result = MagicMock()
        mock_inv_result.scalar_one_or_none.return_value = invitation
        mock_member_result = MagicMock()
        mock_member_result.scalar_one_or_none.return_value = None  # not yet a member
        db.execute.side_effect = [mock_inv_result, mock_member_result]

        result = await accept_invitation(
            db, token=token, user_id=user_id, user_email="bob@example.com"
        )

        assert db.add.called  # membership row added
        assert invitation.accepted_at is not None

    @pytest.mark.asyncio
    async def test_raises_403_if_email_mismatch(self):
        from app.modules.organizations.service import accept_invitation

        db = AsyncMock()
        user_id = uuid4()
        invitation = _make_invitation(email="bob@example.com")

        mock_inv_result = MagicMock()
        mock_inv_result.scalar_one_or_none.return_value = invitation
        db.execute.return_value = mock_inv_result

        with pytest.raises(ForbiddenError):
            await accept_invitation(
                db, token="token", user_id=user_id, user_email="wrong@example.com"
            )

    @pytest.mark.asyncio
    async def test_raises_404_for_expired_or_invalid_token(self):
        from app.modules.organizations.service import accept_invitation

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await accept_invitation(
                db, token="bad-token", user_id=uuid4(), user_email="bob@example.com"
            )

    @pytest.mark.asyncio
    async def test_raises_conflict_if_already_a_member(self):
        from app.modules.organizations.service import accept_invitation

        db = AsyncMock()
        user_id = uuid4()
        org_id = uuid4()
        invitation = _make_invitation(org_id=org_id, email="bob@example.com")
        existing_member = _make_member(org_id=org_id, user_id=user_id)

        mock_inv_result = MagicMock()
        mock_inv_result.scalar_one_or_none.return_value = invitation
        mock_member_result = MagicMock()
        mock_member_result.scalar_one_or_none.return_value = existing_member
        db.execute.side_effect = [mock_inv_result, mock_member_result]

        with pytest.raises(ConflictError):
            await accept_invitation(
                db, token="token", user_id=user_id, user_email="bob@example.com"
            )


# ── create_api_key ────────────────────────────────────────────────────────────

class TestCreateApiKey:
    @pytest.mark.asyncio
    async def test_returns_full_key_once(self):
        from app.modules.organizations.service import create_api_key
        from app.modules.organizations.schemas import APIKeyCreate

        db = AsyncMock()
        org_id = uuid4()
        user_id = uuid4()
        payload = APIKeyCreate(label="Test Key", scopes=["workflow:read"])

        result = await create_api_key(db, org_id=org_id, created_by=user_id, payload=payload)

        assert result.key.startswith("bpa_sk_")
        assert result.key_prefix == result.key[:10]
        assert db.add.called

    @pytest.mark.asyncio
    async def test_does_not_store_plaintext_key(self):
        from app.modules.organizations.service import create_api_key
        from app.modules.organizations.schemas import APIKeyCreate

        db = AsyncMock()
        payload = APIKeyCreate(label="Test Key", scopes=["workflow:execute"])

        result = await create_api_key(db, org_id=uuid4(), created_by=uuid4(), payload=payload)

        # Key returned in response is the plaintext; what's stored (via db.add) is the hash
        add_call_args = db.add.call_args[0][0]
        assert add_call_args.key_hash != result.key


# ── update_member_role ────────────────────────────────────────────────────────

class TestUpdateMemberRole:
    @pytest.mark.asyncio
    async def test_raises_403_if_assigning_higher_rank_than_caller(self):
        from app.modules.organizations.service import update_member
        from app.modules.organizations.schemas import MemberUpdate

        db = AsyncMock()
        org_id = uuid4()
        caller_member = _make_member(org_id=org_id, role="manager")
        target_member = _make_member(org_id=org_id, role="analyst")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = target_member
        db.execute.return_value = mock_result

        with pytest.raises(ForbiddenError):
            await update_member(
                db,
                org_id=org_id,
                target_user_id=target_member.user_id,
                payload=MemberUpdate(role="admin"),  # higher than manager
                caller_member=caller_member,
            )

    @pytest.mark.asyncio
    async def test_raises_403_when_trying_to_assign_owner_role(self):
        from app.modules.organizations.service import update_member
        from app.modules.organizations.schemas import MemberUpdate

        with pytest.raises(Exception):
            MemberUpdate(role="owner")  # schema should reject owner role assignment

    @pytest.mark.asyncio
    async def test_raises_404_if_target_not_in_org(self):
        from app.modules.organizations.service import update_member
        from app.modules.organizations.schemas import MemberUpdate

        db = AsyncMock()
        org_id = uuid4()
        caller_member = _make_member(org_id=org_id, role="admin")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await update_member(
                db,
                org_id=org_id,
                target_user_id=uuid4(),
                payload=MemberUpdate(role="employee"),
                caller_member=caller_member,
            )
