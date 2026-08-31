"""Tests for features added during PHP/JS SDK parity work."""

from __future__ import annotations

import httpx
import respx
from pydantic import BaseModel

from querri._base_client import SyncHTTPClient
from querri._config import ClientConfig
from querri._pagination import SyncCursorPage
from querri._user_client import UserQuerri, _session_config


def _make_config() -> ClientConfig:
    return ClientConfig(
        api_key="qk_test",
        org_id="org_test",
        base_url="https://test.querri.com/api/v1",
        timeout=10.0,
        max_retries=0,
    )


class Item(BaseModel):
    id: str
    name: str


# ---------------------------------------------------------------------------
# replace_user_policies
# ---------------------------------------------------------------------------


class TestReplaceUserPolicies:
    """Test policies.replace_user_policies()."""

    @respx.mock
    def test_replace_user_policies(self):
        """Verify PUT /access/users/{id}/policies is called with correct body."""
        respx.put("https://test.querri.com/api/v1/access/users/usr_1/policies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "user_id": "usr_1",
                    "policy_ids": ["pol_a", "pol_b"],
                    "added": ["pol_b"],
                    "removed": ["pol_old"],
                },
            )
        )
        http = SyncHTTPClient(_make_config())
        from querri.resources.policies import Policies

        policies = Policies(http)
        result = policies.replace_user_policies("usr_1", policy_ids=["pol_a", "pol_b"])
        assert result.user_id == "usr_1"
        assert result.policy_ids == ["pol_a", "pol_b"]
        assert result.added == ["pol_b"]
        assert result.removed == ["pol_old"]
        http.close()


# ---------------------------------------------------------------------------
# append_rows / replace_data
# ---------------------------------------------------------------------------


class TestDataWriteOperations:
    """Test sources.append_rows() and sources.replace_data()."""

    @respx.mock
    def test_append_rows(self):
        """Verify POST /sources/{id}/rows sends rows and returns DataWriteResult."""
        respx.post("https://test.querri.com/api/v1/sources/src_1/rows").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "src_1",
                    "name": "test",
                    "columns": ["a"],
                    "row_count": 3,
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            )
        )
        http = SyncHTTPClient(_make_config())
        from querri.resources.sources import Sources

        sources = Sources(http)
        result = sources.append_rows("src_1", rows=[{"a": 1}, {"a": 2}, {"a": 3}])
        assert result.id == "src_1"
        assert result.row_count == 3
        http.close()

    @respx.mock
    def test_replace_data(self):
        """Verify PUT /sources/{id}/data sends rows and returns DataWriteResult."""
        respx.put("https://test.querri.com/api/v1/sources/src_1/data").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "src_1",
                    "name": "test",
                    "columns": ["x"],
                    "row_count": 5,
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            )
        )
        http = SyncHTTPClient(_make_config())
        from querri.resources.sources import Sources

        sources = Sources(http)
        result = sources.replace_data("src_1", rows=[{"x": i} for i in range(5)])
        assert result.id == "src_1"
        assert result.row_count == 5
        http.close()


# ---------------------------------------------------------------------------
# remove_external_id
# ---------------------------------------------------------------------------


class TestRemoveExternalId:
    """Test users.remove_external_id()."""

    @respx.mock
    def test_remove_external_id(self):
        """Verify DELETE /users/external/{id} returns ExternalIdDeleteResponse."""
        respx.delete("https://test.querri.com/api/v1/users/external/ext_abc").mock(
            return_value=httpx.Response(
                200,
                json={
                    "external_id": "ext_abc",
                    "user_id": "usr_1",
                    "deleted": True,
                },
            )
        )
        http = SyncHTTPClient(_make_config())
        from querri.resources.users import Users

        users = Users(http)
        result = users.remove_external_id("ext_abc")
        assert result.external_id == "ext_abc"
        assert result.user_id == "usr_1"
        assert result.deleted is True
        http.close()


# ---------------------------------------------------------------------------
# as_user / UserQuerri
# ---------------------------------------------------------------------------


class TestAsUser:
    """Test client.as_user() and UserQuerri."""

    def test_session_config_keeps_v1_base_url(self):
        """v2.0.0: user clients call the public API (/api/v1), not /api.

        X-Embed-Session is the public API's priority-0 credential, so the
        base URL is the same as the parent admin client's.
        """
        parent = _make_config()
        session = {
            "session_token": "es_test_token",
            "expires_in": 3600,
            "user_id": "usr_1",
        }
        config = _session_config(session, parent)
        assert config.base_url == "https://test.querri.com/api/v1"
        assert config.session_token == "es_test_token"
        assert config.timeout == parent.timeout
        assert config.max_retries == parent.max_retries

    def test_user_querri_has_expected_resources(self):
        """Verify UserQuerri exposes only user-visible resources."""
        session = {"session_token": "es_test", "expires_in": 3600, "user_id": "usr_1"}
        user_client = UserQuerri(session, _make_config())
        assert hasattr(user_client, "projects")
        assert hasattr(user_client, "dashboards")
        assert hasattr(user_client, "sources")
        assert hasattr(user_client, "chats")
        # Should NOT have admin resources
        assert not hasattr(user_client, "users")
        assert not hasattr(user_client, "policies")
        assert not hasattr(user_client, "keys")
        assert not hasattr(user_client, "audit")
        # v2.0.0: no .embed — the server excludes embed:session:create from
        # embed-session scopes, so a session cannot mint or manage sessions.
        assert not hasattr(user_client, "embed")
        user_client.close()

    def test_user_querri_dashboards_are_read_only(self):
        """v2.0.0: embed sessions lack admin:dashboards:write — the write
        methods do not exist on the user-scoped dashboards surface."""
        session = {"session_token": "es_test", "expires_in": 3600, "user_id": "usr_1"}
        with UserQuerri(session, _make_config()) as uc:
            assert callable(uc.dashboards.list)
            assert callable(uc.dashboards.get)
            assert callable(uc.dashboards.refresh_status)
            for write_method in ("create", "update", "delete", "refresh"):
                assert not hasattr(uc.dashboards, write_method)

    @respx.mock
    def test_user_querri_requests_hit_v1_paths(self):
        """User-client requests go to /api/v1 with X-Embed-Session auth."""
        route = respx.get("https://test.querri.com/api/v1/projects").mock(
            return_value=httpx.Response(
                200, json={"data": [], "has_more": False, "next_cursor": None}
            )
        )
        session = {"session_token": "es_test", "expires_in": 3600, "user_id": "usr_1"}
        with UserQuerri(session, _make_config()) as uc:
            list(uc.projects.list())
        request = route.calls[0].request
        assert request.headers["X-Embed-Session"] == "es_test"
        assert "Authorization" not in request.headers

    def test_user_querri_context_manager(self):
        """Verify UserQuerri supports context manager usage."""
        session = {"session_token": "es_test", "expires_in": 3600, "user_id": "usr_1"}
        with UserQuerri(session, _make_config()) as uc:
            assert uc.projects is not None


# ---------------------------------------------------------------------------
# to_list
# ---------------------------------------------------------------------------


class TestToList:
    """Test SyncCursorPage.to_list()."""

    @respx.mock
    def test_to_list_single_page(self):
        """Verify to_list() returns all items as a flat list."""
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "1", "name": "A"},
                        {"id": "2", "name": "B"},
                    ],
                    "has_more": False,
                },
            )
        )
        http = SyncHTTPClient(_make_config())
        page = SyncCursorPage(http, "/items", Item)
        result = page.to_list()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].name == "A"
        assert result[1].name == "B"
        http.close()

    @respx.mock
    def test_to_list_multi_page(self):
        """Verify to_list() consumes all pages into a flat list."""
        respx.get("https://test.querri.com/api/v1/items").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "data": [{"id": "1", "name": "A"}],
                        "has_more": True,
                        "next_cursor": "cur_1",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "data": [{"id": "2", "name": "B"}],
                        "has_more": False,
                    },
                ),
            ]
        )
        http = SyncHTTPClient(_make_config())
        page = SyncCursorPage(http, "/items", Item)
        result = page.to_list()
        assert len(result) == 2
        assert result[0].name == "A"
        assert result[1].name == "B"
        http.close()
