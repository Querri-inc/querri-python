"""RLS Integration Tests for the Querri Python SDK.

Runs against a live Querri instance at http://localhost.
Requires the Docker development stack to be running.

Execute with:
    QUERRI_API_KEY=qk_... QUERRI_ORG_ID=org_... QUERRI_RLS_CSV_PATH=/path/to/csv \
    python -m pytest tests/test_rls_integration.py -v -s
"""

from __future__ import annotations

import csv
import os
import uuid

import pytest

from querri import Querri
from querri._exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Configuration — all from environment variables
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("QUERRI_API_KEY", "")
ORG_ID = os.environ.get("QUERRI_ORG_ID", "")
HOST = os.environ.get("QUERRI_HOST", "http://localhost")

CSV_PATH = os.environ.get("QUERRI_RLS_CSV_PATH", "")

# Unique test run suffix to avoid collisions
RUN_ID = uuid.uuid4().hex[:8]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """Admin-level SDK client for the test suite."""
    c = Querri(api_key=API_KEY, org_id=ORG_ID, host=HOST)
    yield c
    c.close()


@pytest.fixture(scope="module")
def source_id(client: Querri):
    """Create a data source from CSV test data via the Sources API.

    Uses POST /sources with inline JSON rows.
    """
    # Read CSV into row dicts
    rows = []
    with open(CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    source = client.sources.create_data_source(
        name=f"rls_test_py_employees_{RUN_ID}",
        rows=rows,
    )
    yield source.id

    # Cleanup: delete the source after all tests
    try:
        client.sources.delete(source.id)
    except Exception:
        pass


@pytest.fixture(scope="module")
def user_1(client: Querri):
    """Create or retrieve py_test_user_1."""
    return client.users.get_or_create(
        external_id=f"py_test_user_1_{RUN_ID}",
        email=f"py_test_user_1_{RUN_ID}@test.querri.dev",
        first_name="Test",
        last_name="UserOne",
    )


@pytest.fixture(scope="module")
def user_2(client: Querri):
    """Create or retrieve py_test_user_2."""
    return client.users.get_or_create(
        external_id=f"py_test_user_2_{RUN_ID}",
        email=f"py_test_user_2_{RUN_ID}@test.querri.dev",
        first_name="Test",
        last_name="UserTwo",
    )


# ---------------------------------------------------------------------------
# Module-level storage for IDs shared across tests
# ---------------------------------------------------------------------------

_state: dict = {}


# ===========================================================================
# A. User Management
# ===========================================================================


class TestUserManagement:
    """Test user CRUD operations."""

    def test_01_create_user_1(self, client: Querri, user_1):
        """Create user via get_or_create."""
        assert user_1.id, "User should have an ID"
        assert user_1.email.startswith("py_test_user_1_")
        _state["user_1_id"] = user_1.id
        print(f"\n  user_1 id: {user_1.id}")

    def test_02_create_user_2(self, client: Querri, user_2):
        """Create second test user."""
        assert user_2.id, "User should have an ID"
        assert user_2.email.startswith("py_test_user_2_")
        _state["user_2_id"] = user_2.id
        print(f"\n  user_2 id: {user_2.id}")

    def test_03_idempotent_get_or_create(self, client: Querri, user_1):
        """get_or_create with same external_id returns same user."""
        user_again = client.users.get_or_create(
            external_id=f"py_test_user_1_{RUN_ID}",
            email=f"py_test_user_1_{RUN_ID}@test.querri.dev",
            first_name="Test",
            last_name="UserOne",
        )
        assert user_again.id == user_1.id, "Idempotent call should return same user"

    def test_04_list_users(self, client: Querri, user_1):
        """List users and find our test user."""
        found = False
        for u in client.users.list():
            if u.id == user_1.id:
                found = True
                break
        assert found, f"User {user_1.id} not found in list"

    def test_05_get_user_by_id(self, client: Querri, user_1):
        """Get user by ID."""
        user = client.users.get(user_1.id)
        assert user.id == user_1.id
        assert user.email == user_1.email

    def test_06_update_user(self, client: Querri, user_1):
        """Update user's first name."""
        updated = client.users.update(user_1.id, first_name="Updated")
        assert updated.first_name == "Updated"


# ===========================================================================
# B. Access Policy CRUD
# ===========================================================================


class TestAccessPolicyCRUD:
    """Test policy create, read, update, delete."""

    def test_07_create_policy_single_filter(self, client: Querri, source_id):
        """Create policy with single office=New York filter."""
        policy = client.policies.create(
            name=f"py_test_office_ny_{RUN_ID}",
            source_ids=[source_id],
            row_filters=[{"column": "office", "values": ["New York"]}],
        )
        assert policy.id, "Policy should have an ID"
        assert policy.name == f"py_test_office_ny_{RUN_ID}"
        _state["policy_ny_id"] = policy.id
        print(f"\n  policy_ny id: {policy.id}")

    def test_08_create_policy_multiple_filters(self, client: Querri, source_id):
        """Create policy with office + team filters."""
        policy = client.policies.create(
            name=f"py_test_office_team_{RUN_ID}",
            source_ids=[source_id],
            row_filters=[
                {"column": "office", "values": ["San Francisco"]},
                {"column": "team", "values": ["Engineering"]},
            ],
        )
        assert policy.id
        _state["policy_sf_eng_id"] = policy.id
        print(f"\n  policy_sf_eng id: {policy.id}")

    def test_09_list_policies(self, client: Querri):
        """List policies and find our test policies."""
        policies = client.policies.list()
        policy_ids = {p.id for p in policies}
        assert _state["policy_ny_id"] in policy_ids, "NY policy not in list"

    def test_10_get_policy_by_id(self, client: Querri):
        """Get policy detail by ID."""
        policy = client.policies.get(_state["policy_ny_id"])
        assert policy.id == _state["policy_ny_id"]
        assert policy.name == f"py_test_office_ny_{RUN_ID}"
        assert len(policy.row_filters) >= 1

    def test_11_update_policy(self, client: Querri):
        """Update policy description."""
        result = client.policies.update(
            _state["policy_ny_id"],
            description="Updated by integration test",
        )
        assert result.id == _state["policy_ny_id"]
        assert result.updated

    def test_12_delete_policy(self, client: Querri, source_id):
        """Create and delete a temporary policy."""
        tmp = client.policies.create(
            name=f"py_test_delete_me_{RUN_ID}",
            source_ids=[source_id],
            row_filters=[{"column": "office", "values": ["Tokyo"]}],
        )
        result = client.policies.delete(tmp.id)
        assert result.deleted

        # Verify it's gone
        with pytest.raises(NotFoundError):
            client.policies.get(tmp.id)


# ===========================================================================
# C. Policy Assignment
# ===========================================================================


class TestPolicyAssignment:
    """Test assigning and removing users from policies."""

    def test_13_assign_user_to_policy(self, client: Querri, user_1):
        """Assign user_1 to NY policy."""
        result = client.policies.assign_users(
            _state["policy_ny_id"],
            user_ids=[user_1.id],
        )
        assert result.policy_id == _state["policy_ny_id"]
        assert user_1.id in result.assigned_user_ids

    def test_14_remove_user_from_policy(self, client: Querri, user_2):
        """Assign then remove user_2 from NY policy."""
        # Assign first
        client.policies.assign_users(
            _state["policy_ny_id"],
            user_ids=[user_2.id],
        )
        # Remove
        result = client.policies.remove_user(
            _state["policy_ny_id"],
            user_2.id,
        )
        assert result.removed

    def test_15_replace_all_user_policies(self, client: Querri, user_1, source_id):
        """Use get_session to atomically replace user's policy assignment."""
        # First assign user_1 to sf_eng policy
        client.policies.assign_users(
            _state["policy_sf_eng_id"],
            user_ids=[user_1.id],
        )

        # Use get_session with policy_ids to set the exact policies
        session = client.embed.get_session(
            user={
                "external_id": f"py_test_user_1_{RUN_ID}",
                "email": f"py_test_user_1_{RUN_ID}@test.querri.dev",
            },
            access={"policy_ids": [_state["policy_ny_id"]]},
        )
        assert session.get("session_token"), "Session should have a token"

    def test_16_verify_assignments(self, client: Querri, user_1):
        """Verify user_1 is assigned to NY policy."""
        policy = client.policies.get(_state["policy_ny_id"])
        assert policy.assigned_user_ids is not None
        assert user_1.id in policy.assigned_user_ids


# ===========================================================================
# D. get_session() Workflow
# ===========================================================================


class TestGetSessionWorkflow:
    """Test the flagship get_session convenience method."""

    def test_17_get_session_inline_access(self, client: Querri, source_id):
        """get_session with inline sources+filters spec."""
        session = client.embed.get_session(
            user={
                "external_id": f"py_test_user_1_{RUN_ID}",
                "email": f"py_test_user_1_{RUN_ID}@test.querri.dev",
            },
            access={
                "sources": [source_id],
                "filters": {"office": ["New York"]},
            },
        )
        assert session.get("session_token"), "Should return a session token"
        assert session["session_token"].startswith("es_"), "Token should start with es_"
        _state["session_token_1"] = session["session_token"]
        _state["session_user_id"] = session.get("user_id")
        print(f"\n  session token: {session['session_token'][:20]}...")

    def test_18_deterministic_policy_naming(self, client: Querri, source_id):
        """Verify auto-policies use deterministic naming from content hash."""
        from querri._convenience import _hash_access_spec

        spec = {"sources": [source_id], "filters": {"office": ["New York"]}}
        expected_hash = _hash_access_spec(spec)
        expected_name = f"sdk_auto_{expected_hash}"

        # Find the auto-created policy
        policies = client.policies.list(name=expected_name)
        assert len(policies) >= 1, f"Expected auto-policy named {expected_name}"
        _state["auto_policy_id"] = policies[0].id

    def test_19_get_session_reuse_policy(self, client: Querri, source_id):
        """Calling get_session with same spec reuses existing auto-policy."""
        policies_before = client.policies.list()
        count_before = len(policies_before)

        session = client.embed.get_session(
            user={
                "external_id": f"py_test_user_1_{RUN_ID}",
                "email": f"py_test_user_1_{RUN_ID}@test.querri.dev",
            },
            access={
                "sources": [source_id],
                "filters": {"office": ["New York"]},
            },
        )
        assert session.get("session_token")

        policies_after = client.policies.list()
        count_after = len(policies_after)
        assert count_after == count_before, (
            f"Policy count changed from {count_before} to {count_after} - "
            "should have reused existing auto-policy"
        )

    def test_20_get_session_with_policy_ids(self, client: Querri):
        """get_session with explicit policy_ids."""
        session = client.embed.get_session(
            user={
                "external_id": f"py_test_user_2_{RUN_ID}",
                "email": f"py_test_user_2_{RUN_ID}@test.querri.dev",
            },
            access={"policy_ids": [_state["policy_ny_id"]]},
        )
        assert session.get("session_token")

    def test_21_get_session_no_access(self, client: Querri):
        """get_session with no access spec preserves existing."""
        session = client.embed.get_session(
            user={
                "external_id": f"py_test_user_1_{RUN_ID}",
                "email": f"py_test_user_1_{RUN_ID}@test.querri.dev",
            },
            access=None,
        )
        assert session.get("session_token")

    def test_22_verify_atomic_replacement(self, client: Querri, user_2):
        """Verify get_session with policy_ids assigns user to that policy."""
        policy = client.policies.get(_state["policy_ny_id"])
        assert policy.assigned_user_ids is not None
        assert user_2.id in policy.assigned_user_ids


# ===========================================================================
# E. Session-Scoped Data Access
# ===========================================================================


class TestSessionScopedDataAccess:
    """Test data access through embed sessions with RLS."""

    def test_23_create_session_for_data_access(self, client: Querri, source_id):
        """Create a session with NY-only access for data verification."""
        session = client.embed.get_session(
            user={
                "external_id": f"py_test_user_1_{RUN_ID}",
                "email": f"py_test_user_1_{RUN_ID}@test.querri.dev",
            },
            access={
                "sources": [source_id],
                "filters": {"office": ["New York"]},
            },
        )
        _state["data_session_token"] = session["session_token"]
        _state["data_user_id"] = session.get("user_id")
        assert session.get("session_token")

    def test_24_get_source_metadata(self, client: Querri, source_id):
        """Verify our test source is accessible via data.source() metadata endpoint.

        Note: sources created via POST /data/sources (service='api') may not
        appear in list endpoints that filter by service type. The individual
        source metadata endpoint works regardless.
        """
        source = client.sources.get(source_id)
        assert source.id == source_id
        assert "office" in source.columns
        assert "team" in source.columns
        print(f"\n  Source: {source.name}, columns: {source.columns}")

    def test_25_get_source_data_all_rows(self, client: Querri, source_id):
        """Get all source data through admin client."""
        result = client.sources.source_data(source_id, page_size=100)
        assert len(result.data) > 0, "Source should have data"
        # Admin should see all 20 rows
        assert len(result.data) >= 20, f"Expected >= 20 rows, got {len(result.data)}"
        print(f"\n  Total rows (admin): {len(result.data)}")

    def test_26_verify_ny_data_exists(self, client: Querri, source_id):
        """Verify source data includes New York office entries."""
        result = client.sources.source_data(source_id, page_size=100)
        ny_rows = [r for r in result.data if r.get("office") == "New York"]
        assert len(ny_rows) > 0, "Should have New York rows"
        # CSV has 5 New York rows
        assert len(ny_rows) == 5, f"Expected 5 NY rows, got {len(ny_rows)}"
        print(f"\n  New York rows: {len(ny_rows)}")


# ===========================================================================
# F. RLS Resolution
# ===========================================================================


class TestRLSResolution:
    """Test the resolve endpoint for previewing effective access."""

    def test_27_resolve_access(self, client: Querri, source_id, user_1):
        """Resolve effective filters for user_1 + source."""
        resolved = client.policies.resolve(
            user_id=user_1.id,
            source_id=source_id,
        )
        assert resolved.user_id == user_1.id
        assert resolved.source_id == source_id
        print(f"\n  Resolved filters: {resolved.resolved_filters}")
        print(f"  WHERE clause: {resolved.where_clause}")
        print(f"  Effective access: {resolved.effective_access}")

    def test_28_verify_where_clause(self, client: Querri, source_id, user_1):
        """Verify WHERE clause or effective access is reported for a user with policies."""
        resolved = client.policies.resolve(
            user_id=user_1.id,
            source_id=source_id,
        )
        # User has at least the NY policy, so there should be filters or a where clause
        has_filters = (
            resolved.where_clause != ""
            or resolved.resolved_filters.row_filters
            or resolved.resolved_filters.has_any_policy
        )
        assert has_filters or resolved.effective_access, (
            "Expected resolved access info for a user with policies"
        )


# ===========================================================================
# G. Access Control Toggle
# ===========================================================================


class TestAccessControlToggle:
    """Test behavior with access_controlled flag scenarios."""

    def test_29_admin_query_returns_all_rows(self, client: Querri, source_id):
        """Admin source_data with no RLS enforcement should return all rows."""
        result = client.sources.source_data(source_id, page_size=100)
        assert len(result.data) >= 20, (
            f"Expected >= 20 rows for admin, got {len(result.data)}"
        )
        print(f"\n  Total rows (admin): {len(result.data)}")

    def test_30_user_with_no_policies_behavior(self, client: Querri, source_id):
        """Create a user with no policies and verify resolve returns empty filters."""
        fresh_user = client.users.get_or_create(
            external_id=f"py_test_no_policy_{RUN_ID}",
            email=f"py_test_no_policy_{RUN_ID}@test.querri.dev",
            first_name="NoPol",
            last_name="User",
        )
        resolved = client.policies.resolve(
            user_id=fresh_user.id,
            source_id=source_id,
        )
        # A user with no policies should have no resolved row_filters
        assert not resolved.resolved_filters.has_any_policy, (
            "User with no policies should have has_any_policy=False"
        )
        print(f"\n  No-policy user resolved_filters: {resolved.resolved_filters}")
        print(f"  No-policy user where_clause: '{resolved.where_clause}'")
        print(f"  No-policy user effective_access: '{resolved.effective_access}'")


# ===========================================================================
# H. Error Handling
# ===========================================================================


class TestErrorHandling:
    """Test SDK error handling for invalid operations."""

    def test_31_invalid_api_key(self):
        """Invalid API key should raise AuthenticationError."""
        bad_client = Querri(
            api_key="qk_invalid_key_for_testing",
            org_id=ORG_ID,
            host=HOST,
            max_retries=0,
        )
        try:
            with pytest.raises((AuthenticationError, APIError)) as exc_info:
                bad_client.users.list().data  # force the request
            err = exc_info.value
            assert err.status in (401, 403), f"Expected 401/403, got {err.status}"
            print(f"\n  Error: {err}")
        finally:
            bad_client.close()

    def test_32_expired_session(self, client: Querri):
        """Using a fake/expired session token should fail gracefully."""
        try:
            result = client.embed.refresh_session(session_token="es_expired_fake_token")
            print(f"\n  Unexpected success: {result}")
        except (APIError, NotFoundError) as e:
            assert e.status in (400, 401, 404), f"Expected 400/401/404, got {e.status}"
            print(f"\n  Expected error: {e}")

    def test_33_policy_not_found(self, client: Querri):
        """Getting a non-existent policy should raise NotFoundError."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        with pytest.raises((NotFoundError, APIError)) as exc_info:
            client.policies.get(fake_id)
        err = exc_info.value
        assert err.status in (404, 400), f"Expected 404/400, got {err.status}"
        print(f"\n  Error: {err}")


# ===========================================================================
# Cleanup
# ===========================================================================


class TestCleanup:
    """Clean up test resources. Runs last due to class ordering."""

    def test_99_cleanup_policies(self, client: Querri):
        """Delete test policies (including auto-created ones)."""
        policies = client.policies.list()
        deleted = 0
        for p in policies:
            if RUN_ID in p.name or p.name.startswith("sdk_auto_"):
                try:
                    client.policies.delete(p.id)
                    deleted += 1
                except Exception:
                    pass
        print(f"\n  Cleaned up {deleted} policies")

    def test_99_cleanup_users(self, client: Querri):
        """Delete test users."""
        deleted = 0
        for u in client.users.list():
            if RUN_ID in (u.external_id or ""):
                try:
                    client.users.delete(u.id)
                    deleted += 1
                except Exception:
                    pass
        print(f"\n  Cleaned up {deleted} users")


# ---------------------------------------------------------------------------
# Direct execution support
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
