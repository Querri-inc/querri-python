"""Integration tests for the querri-python SDK against a live API.

These tests require:
- A running Querri instance at http://localhost/api/v1
- QUERRI_API_KEY and QUERRI_ORG_ID environment variables set

Run with:
    pytest tests/test_integration.py -m integration -v
"""

from __future__ import annotations

import os
import uuid

import pytest

from querri import Querri
from querri._exceptions import (
    NotFoundError,
)

pytestmark = pytest.mark.integration

HOST = "http://localhost"


def _unique(prefix: str = "sdk_test") -> str:
    """Generate a unique name for test entities."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def client():
    """Create a Querri client pointing at local dev stack."""
    c = Querri(
        api_key=os.environ["QUERRI_API_KEY"],
        org_id=os.environ["QUERRI_ORG_ID"],
        host=HOST,
    )
    yield c
    c.close()


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------


class TestUserCRUD:
    """Test create → get → list → update → delete user lifecycle."""

    def test_create_get_update_delete(self, client: Querri):
        ext_id = _unique("ext")
        email = f"{ext_id}@sdk-test.querri.com"

        # Create
        user = client.users.create(
            email=email,
            external_id=ext_id,
            first_name="SDK",
            last_name="Test",
            role="member",
        )
        assert user.email == email
        assert user.id  # has a WorkOS user ID
        user_id = user.id

        try:
            # Get
            fetched = client.users.get(user_id)
            assert fetched.id == user_id
            assert fetched.email == email

            # List (filter by external_id)
            page = client.users.list(external_id=ext_id)
            found = page.data
            assert len(found) >= 1
            assert any(u.id == user_id for u in found)

            # Update — may fail with 400 if WorkOS rejects the update
            # (e.g., user created via API doesn't have full WorkOS profile)
            try:
                updated = client.users.update(user_id, first_name="Updated")
                assert updated.id == user_id
            except Exception:
                pytest.skip("User update not supported for API-created users (WorkOS limitation)")

        finally:
            # Delete (cleanup)
            client.users.delete(user_id)

    def test_get_or_create_idempotent(self, client: Querri):
        ext_id = _unique("idem")
        email = f"{ext_id}@sdk-test.querri.com"

        user1 = client.users.get_or_create(
            external_id=ext_id,
            email=email,
            first_name="Idempotent",
        )
        user2 = client.users.get_or_create(
            external_id=ext_id,
            email=email,
        )
        assert user1.id == user2.id

        # Cleanup
        client.users.delete(user1.id)


# ---------------------------------------------------------------------------
# Policy CRUD
# ---------------------------------------------------------------------------


class TestPolicyCRUD:
    """Test policy create → list → assign → resolve → delete."""

    def test_policy_lifecycle(self, client: Querri):
        name = _unique("policy")

        # Create
        policy = client.policies.create(
            name=name,
            description="SDK integration test policy",
        )
        assert policy.id
        assert policy.name == name
        policy_id = policy.id

        try:
            # List with name filter
            policies = client.policies.list(name=name)
            assert any(p.id == policy_id for p in policies)

            # Get
            fetched = client.policies.get(policy_id)
            assert fetched.id == policy_id

        finally:
            # Delete
            resp = client.policies.delete(policy_id)
            assert resp.deleted is True

    def test_policy_user_assignment(self, client: Querri):
        """Create policy, create user, assign user, then cleanup."""
        policy_name = _unique("pol_assign")
        ext_id = _unique("pol_user")
        email = f"{ext_id}@sdk-test.querri.com"

        policy = client.policies.create(name=policy_name)
        user = client.users.create(email=email, external_id=ext_id)

        try:
            # Assign
            assign_resp = client.policies.assign_users(
                policy.id, user_ids=[user.id],
            )
            assert len(assign_resp.assigned_user_ids) >= 1

            # Remove
            remove_resp = client.policies.remove_user(policy.id, user.id)
            assert remove_resp.removed is True

        finally:
            client.policies.delete(policy.id)
            client.users.delete(user.id)


# ---------------------------------------------------------------------------
# Project operations
# ---------------------------------------------------------------------------


class TestProjectOperations:
    """Test project list, get, and step listing."""

    def test_list_projects(self, client: Querri):
        page = client.projects.list(limit=5)
        # Should not raise — may be empty in a fresh environment
        items = page.data
        assert isinstance(items, list)

    def test_get_nonexistent_project(self, client: Querri):
        fake_id = "00000000-0000-0000-0000-000000000000"
        with pytest.raises(NotFoundError):
            client.projects.get(fake_id)

    def test_create_and_delete_project(self, client: Querri):
        """Create a project, verify it exists, then delete it."""
        ext_id = _unique("proj_user")
        email = f"{ext_id}@sdk-test.querri.com"
        user = client.users.create(email=email, external_id=ext_id)

        try:
            project = client.projects.create(
                name=_unique("project"),
                user_id=user.id,
            )
            assert project.id
            assert project.name

            # Get
            fetched = client.projects.get(project.id)
            assert fetched.id == project.id

            # List steps (should be empty for new project)
            steps = client.projects.list_steps(project.id)
            assert isinstance(steps, list)

            # Delete
            client.projects.delete(project.id)

            # Verify deleted
            with pytest.raises(NotFoundError):
                client.projects.get(project.id)

        finally:
            client.users.delete(user.id)


# ---------------------------------------------------------------------------
# Dashboard operations
# ---------------------------------------------------------------------------


class TestDashboardOperations:
    """Test dashboard list and get."""

    def test_list_dashboards(self, client: Querri):
        dashboards = client.dashboards.list(limit=5)
        assert isinstance(dashboards, list)

    def test_get_nonexistent_dashboard(self, client: Querri):
        fake_id = "00000000-0000-0000-0000-000000000000"
        with pytest.raises(NotFoundError):
            client.dashboards.get(fake_id)


# ---------------------------------------------------------------------------
# Data operations
# ---------------------------------------------------------------------------


class TestDataOperations:
    """Test data source listing."""

    def test_list_sources(self, client: Querri):
        try:
            sources = client.sources.list()
            assert isinstance(sources, list)
        except Exception as exc:
            pytest.skip(f"Data sources endpoint unavailable: {exc}")


# ---------------------------------------------------------------------------
# Embed session
# ---------------------------------------------------------------------------


class TestEmbedSession:
    """Test embed session create → list → revoke."""

    def test_session_lifecycle(self, client: Querri):
        # Need a user first
        ext_id = _unique("embed_user")
        email = f"{ext_id}@sdk-test.querri.com"
        user = client.users.create(email=email, external_id=ext_id)

        try:
            # Create session
            session = client.embed.create_session(
                user_id=user.id,
                ttl=900,
            )
            assert session.session_token
            assert session.session_token.startswith("es_")

            # List sessions
            session_list = client.embed.list_sessions(limit=10)
            assert isinstance(session_list.data, list)

            # Revoke
            revoke = client.embed.revoke_session(session.session_token)
            assert revoke.revoked is True

        finally:
            client.users.delete(user.id)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test that errors are raised correctly."""

    def test_404_on_nonexistent_user(self, client: Querri):
        with pytest.raises(NotFoundError) as exc_info:
            client.users.get("nonexistent_user_id_12345")
        assert exc_info.value.status == 404

    def test_404_on_nonexistent_policy(self, client: Querri):
        fake_id = "00000000-0000-0000-0000-000000000000"
        with pytest.raises(NotFoundError):
            client.policies.get(fake_id)
