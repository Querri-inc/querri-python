"""Comprehensive unit tests for the Querri SDK resource layer.

Each test class covers a single resource and verifies that:
1. The correct HTTP method + URL is called.
2. The correct request body/params are sent.
3. The response is parsed into the right type.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from querri._base_client import SyncHTTPClient
from querri._config import ClientConfig

BASE = "https://test.querri.com/api/v1"


def _make_config() -> ClientConfig:
    return ClientConfig(
        api_key="qk_test",
        org_id="org_test",
        base_url=BASE,
        timeout=10.0,
        max_retries=0,
    )


def _http() -> SyncHTTPClient:
    return SyncHTTPClient(_make_config())


# =========================================================================
# Users
# =========================================================================


class TestUsers:
    """Tests for querri.resources.users.Users."""

    @respx.mock
    def test_create(self):
        route = respx.post(f"{BASE}/users").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "usr_1",
                    "email": "a@b.com",
                    "role": "member",
                },
            )
        )
        from querri.resources.users import Users
        from querri.types.user import User

        users = Users(_http())
        result = users.create(email="a@b.com")
        assert isinstance(result, User)
        assert result.id == "usr_1"
        assert result.email == "a@b.com"
        assert result.role == "member"
        req = route.calls[0].request
        assert (
            b'"email": "a@b.com"' in req.content or b'"email":"a@b.com"' in req.content
        )

    @respx.mock
    def test_create_with_all_fields(self):
        respx.post(f"{BASE}/users").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "usr_2",
                    "email": "b@c.com",
                    "role": "admin",
                    "external_id": "ext_1",
                    "first_name": "Alice",
                    "last_name": "Smith",
                },
            )
        )
        from querri.resources.users import Users

        users = Users(_http())
        result = users.create(
            email="b@c.com",
            role="admin",
            external_id="ext_1",
            first_name="Alice",
            last_name="Smith",
        )
        assert result.id == "usr_2"
        assert result.external_id == "ext_1"
        assert result.first_name == "Alice"

    @respx.mock
    def test_get(self):
        respx.get(f"{BASE}/users/usr_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "usr_1",
                    "email": "a@b.com",
                    "role": "member",
                },
            )
        )
        from querri.resources.users import Users

        users = Users(_http())
        result = users.get("usr_1")
        assert result.id == "usr_1"

    @respx.mock
    def test_list(self):
        respx.get(f"{BASE}/users").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "usr_1", "email": "a@b.com", "role": "member"},
                        {"id": "usr_2", "email": "c@d.com", "role": "admin"},
                    ],
                    "has_more": False,
                },
            )
        )
        from querri.resources.users import Users

        users = Users(_http())
        page = users.list(limit=10)
        items = list(page)
        assert len(items) == 2
        assert items[0].id == "usr_1"
        assert items[1].email == "c@d.com"

    @respx.mock
    def test_list_with_external_id_filter(self):
        route = respx.get(f"{BASE}/users").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"id": "usr_1", "email": "a@b.com", "role": "member"}],
                    "has_more": False,
                },
            )
        )
        from querri.resources.users import Users

        users = Users(_http())
        page = users.list(external_id="ext_1")
        items = list(page)
        assert len(items) == 1
        req = route.calls[0].request
        assert "external_id=ext_1" in str(req.url)

    @respx.mock
    def test_update(self):
        respx.patch(f"{BASE}/users/usr_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "usr_1",
                    "email": "a@b.com",
                    "role": "admin",
                    "first_name": "Updated",
                },
            )
        )
        from querri.resources.users import Users

        users = Users(_http())
        result = users.update("usr_1", role="admin", first_name="Updated")
        assert result.role == "admin"
        assert result.first_name == "Updated"

    @respx.mock
    def test_delete(self):
        respx.delete(f"{BASE}/users/usr_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "usr_1",
                    "deleted": True,
                },
            )
        )
        from querri.resources.users import Users
        from querri.types.user import UserDeleteResponse

        users = Users(_http())
        result = users.delete("usr_1")
        assert isinstance(result, UserDeleteResponse)
        assert result.id == "usr_1"
        assert result.deleted is True

    @respx.mock
    def test_get_or_create(self):
        respx.put(f"{BASE}/users/external/ext_99").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "usr_new",
                    "email": "new@test.com",
                    "role": "member",
                    "external_id": "ext_99",
                    "created": True,
                },
            )
        )
        from querri.resources.users import Users

        users = Users(_http())
        result = users.get_or_create(
            external_id="ext_99",
            email="new@test.com",
        )
        assert result.id == "usr_new"
        assert result.created is True
        assert result.external_id == "ext_99"

    @respx.mock
    def test_remove_external_id(self):
        respx.delete(f"{BASE}/users/external/ext_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "external_id": "ext_1",
                    "user_id": "usr_1",
                    "deleted": True,
                },
            )
        )
        from querri.resources.users import Users
        from querri.types.user import ExternalIdDeleteResponse

        users = Users(_http())
        result = users.remove_external_id("ext_1")
        assert isinstance(result, ExternalIdDeleteResponse)
        assert result.external_id == "ext_1"
        assert result.user_id == "usr_1"


# =========================================================================
# Dashboards
# =========================================================================


class TestDashboards:
    """Tests for querri.resources.dashboards.Dashboards."""

    @respx.mock
    def test_create(self):
        respx.post(f"{BASE}/dashboards").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "dash_1",
                    "name": "Sales",
                    "widget_count": 0,
                },
            )
        )
        from querri.resources.dashboards import Dashboards
        from querri.types.dashboard import Dashboard

        dash = Dashboards(_http())
        result = dash.create(name="Sales")
        assert isinstance(result, Dashboard)
        assert result.id == "dash_1"
        assert result.name == "Sales"

    @respx.mock
    def test_create_with_description(self):
        route = respx.post(f"{BASE}/dashboards").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "dash_2",
                    "name": "Ops",
                    "description": "Ops dash",
                    "widget_count": 0,
                },
            )
        )
        from querri.resources.dashboards import Dashboards

        dash = Dashboards(_http())
        result = dash.create(name="Ops", description="Ops dash")
        assert result.description == "Ops dash"
        assert b"description" in route.calls[0].request.content

    @respx.mock
    def test_get(self):
        respx.get(f"{BASE}/dashboards/dash_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "dash_1",
                    "name": "Sales",
                    "widget_count": 3,
                    "widgets": [{"id": "w1"}],
                    "filters": [],
                },
            )
        )
        from querri.resources.dashboards import Dashboards

        dash = Dashboards(_http())
        result = dash.get("dash_1")
        assert result.widget_count == 3
        assert result.widgets == [{"id": "w1"}]

    @respx.mock
    def test_list(self):
        respx.get(f"{BASE}/dashboards").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "dash_1", "name": "A", "widget_count": 0},
                        {"id": "dash_2", "name": "B", "widget_count": 2},
                    ],
                    "has_more": False,
                },
            )
        )
        from querri.resources.dashboards import Dashboards

        dash = Dashboards(_http())
        items = list(dash.list())
        assert len(items) == 2
        assert items[0].name == "A"

    @respx.mock
    def test_update(self):
        respx.patch(f"{BASE}/dashboards/dash_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "dash_1",
                    "updated": True,
                },
            )
        )
        from querri.resources.dashboards import Dashboards
        from querri.types.dashboard import DashboardUpdateResponse

        dash = Dashboards(_http())
        result = dash.update("dash_1", name="New Name")
        assert isinstance(result, DashboardUpdateResponse)
        assert result.updated is True

    @respx.mock
    def test_delete(self):
        route = respx.delete(f"{BASE}/dashboards/dash_1").mock(
            return_value=httpx.Response(204)
        )
        from querri.resources.dashboards import Dashboards

        dash = Dashboards(_http())
        dash.delete("dash_1")
        assert route.called

    @respx.mock
    def test_refresh(self):
        respx.post(f"{BASE}/dashboards/dash_1/refresh").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "dash_1",
                    "status": "refreshing",
                    "project_count": 5,
                },
            )
        )
        from querri.resources.dashboards import Dashboards
        from querri.types.dashboard import DashboardRefreshResponse

        dash = Dashboards(_http())
        result = dash.refresh("dash_1")
        assert isinstance(result, DashboardRefreshResponse)
        assert result.status == "refreshing"
        assert result.project_count == 5

    @respx.mock
    def test_refresh_status(self):
        respx.get(f"{BASE}/dashboards/dash_1/refresh/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "dash_1",
                    "status": "idle",
                    "project_count": 5,
                },
            )
        )
        from querri.resources.dashboards import Dashboards
        from querri.types.dashboard import DashboardRefreshStatus

        dash = Dashboards(_http())
        result = dash.refresh_status("dash_1")
        assert isinstance(result, DashboardRefreshStatus)
        assert result.status == "idle"


# =========================================================================
# Keys
# =========================================================================


class TestKeys:
    """Tests for querri.resources.keys.Keys."""

    @respx.mock
    def test_create(self):
        route = respx.post(f"{BASE}/keys").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "key_1",
                    "name": "CI",
                    "key_prefix": "qk_abc",
                    "scopes": ["data:read"],
                    "status": "active",
                    "secret": "qk_abc_full_secret",
                },
            )
        )
        from querri.resources.keys import Keys
        from querri.types.key import ApiKeyCreated

        keys = Keys(_http())
        result = keys.create(name="CI", scopes=["data:read"])
        assert isinstance(result, ApiKeyCreated)
        assert result.id == "key_1"
        assert result.secret == "qk_abc_full_secret"
        assert result.scopes == ["data:read"]
        req_body = route.calls[0].request.content
        assert b'"name"' in req_body
        assert b'"scopes"' in req_body

    @respx.mock
    def test_create_with_all_options(self):
        respx.post(f"{BASE}/keys").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "key_2",
                    "name": "Full",
                    "key_prefix": "qk_xyz",
                    "scopes": ["data:read", "data:write"],
                    "status": "active",
                    "secret": "qk_xyz_secret",
                    "expires_at": "2025-12-31T00:00:00Z",
                    "rate_limit_per_minute": 120,
                    "bound_user_id": "usr_1",
                    "ip_allowlist": ["1.2.3.4"],
                },
            )
        )
        from querri.resources.keys import Keys

        keys = Keys(_http())
        result = keys.create(
            name="Full",
            scopes=["data:read", "data:write"],
            expires_in_days=30,
            bound_user_id="usr_1",
            rate_limit_per_minute=120,
            ip_allowlist=["1.2.3.4"],
        )
        assert result.rate_limit_per_minute == 120
        assert result.bound_user_id == "usr_1"
        assert result.ip_allowlist == ["1.2.3.4"]

    @respx.mock
    def test_get(self):
        respx.get(f"{BASE}/keys/key_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "key_1",
                    "name": "CI",
                    "key_prefix": "qk_abc",
                    "scopes": ["data:read"],
                    "status": "active",
                },
            )
        )
        from querri.resources.keys import Keys
        from querri.types.key import ApiKey

        keys = Keys(_http())
        result = keys.get("key_1")
        assert isinstance(result, ApiKey)
        assert result.id == "key_1"
        assert not hasattr(result, "secret") or not isinstance(
            result, type(result).__mro__[0]
        )

    @respx.mock
    def test_list(self):
        respx.get(f"{BASE}/keys").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "key_1",
                            "name": "A",
                            "key_prefix": "qk_a",
                            "scopes": [],
                            "status": "active",
                        },
                        {
                            "id": "key_2",
                            "name": "B",
                            "key_prefix": "qk_b",
                            "scopes": ["data:read"],
                            "status": "active",
                        },
                    ],
                },
            )
        )
        from querri.resources.keys import Keys
        from querri.types.key import ApiKey

        keys = Keys(_http())
        result = keys.list()
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(k, ApiKey) for k in result)

    @respx.mock
    def test_delete(self):
        respx.delete(f"{BASE}/keys/key_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "key_1",
                    "status": "revoked",
                },
            )
        )
        from querri.resources.keys import Keys

        keys = Keys(_http())
        result = keys.delete("key_1")
        assert result["id"] == "key_1"
        assert result["status"] == "revoked"


# =========================================================================
# Sources
# =========================================================================


class TestSources:
    """Tests for querri.resources.sources.Sources."""

    @respx.mock
    def test_create(self):
        route = respx.post(f"{BASE}/sources").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "src_1",
                    "name": "My Source",
                    "connector_id": "conn_1",
                    "status": "pending",
                },
            )
        )
        from querri.resources.sources import Sources

        sources = Sources(_http())
        result = sources.create(name="My Source", connector_id="conn_1")
        assert isinstance(result, dict)
        assert result["id"] == "src_1"
        req_body = route.calls[0].request.content
        assert b"connector_id" in req_body

    @respx.mock
    def test_create_data_source(self):
        respx.post(f"{BASE}/sources").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "src_2",
                    "name": "Inline",
                    "columns": ["a", "b"],
                    "row_count": 2,
                },
            )
        )
        from querri.resources.sources import Sources
        from querri.types.data import Source

        sources = Sources(_http())
        result = sources.create_data_source(
            name="Inline",
            rows=[{"a": 1, "b": 2}, {"a": 3, "b": 4}],
        )
        assert isinstance(result, Source)
        assert result.id == "src_2"
        assert result.columns == ["a", "b"]
        assert result.row_count == 2

    @respx.mock
    def test_get(self):
        respx.get(f"{BASE}/sources/src_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "src_1",
                    "name": "My Source",
                    "status": "active",
                },
            )
        )
        from querri.resources.sources import Sources

        sources = Sources(_http())
        result = sources.get("src_1")
        assert result["id"] == "src_1"

    @respx.mock
    def test_list(self):
        respx.get(f"{BASE}/sources").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "src_1", "name": "Alpha"},
                        {"id": "src_2", "name": "Beta"},
                    ],
                },
            )
        )
        from querri.resources.sources import Sources

        sources = Sources(_http())
        result = sources.list()
        assert len(result) == 2
        assert result[0]["name"] == "Alpha"

    @respx.mock
    def test_list_with_search(self):
        respx.get(f"{BASE}/sources").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "src_1", "name": "Alpha"},
                        {"id": "src_2", "name": "Beta"},
                    ],
                },
            )
        )
        from querri.resources.sources import Sources

        sources = Sources(_http())
        result = sources.list(search="beta")
        assert len(result) == 1
        assert result[0]["name"] == "Beta"

    @respx.mock
    def test_update(self):
        route = respx.patch(f"{BASE}/sources/src_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "src_1",
                    "updated": True,
                },
            )
        )
        from querri.resources.sources import Sources

        sources = Sources(_http())
        result = sources.update("src_1", name="Renamed")
        assert result["id"] == "src_1"
        assert b"Renamed" in route.calls[0].request.content

    @respx.mock
    def test_delete(self):
        route = respx.delete(f"{BASE}/sources/src_1").mock(
            return_value=httpx.Response(204)
        )
        from querri.resources.sources import Sources

        sources = Sources(_http())
        sources.delete("src_1")
        assert route.called

    @respx.mock
    def test_sync(self):
        respx.post(f"{BASE}/sources/src_1/sync").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "src_1",
                    "status": "sync_queued",
                },
            )
        )
        from querri.resources.sources import Sources

        sources = Sources(_http())
        result = sources.sync("src_1")
        assert result["status"] == "sync_queued"

    @respx.mock
    def test_query(self):
        route = respx.post(f"{BASE}/sources/src_1/query").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"col": "val"}],
                    "total_rows": 1,
                    "page": 1,
                    "page_size": 100,
                },
            )
        )
        from querri.resources.sources import Sources
        from querri.types.data import QueryResult

        sources = Sources(_http())
        result = sources.query(sql="SELECT * FROM t", source_id="src_1")
        assert isinstance(result, QueryResult)
        assert result.data == [{"col": "val"}]
        assert result.total_rows == 1
        req_body = route.calls[0].request.content
        assert b"SELECT * FROM t" in req_body

    @respx.mock
    def test_source_data(self):
        route = respx.get(f"{BASE}/sources/src_1/data").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"a": 1}],
                    "total_count": 50,
                    "page": 2,
                    "page_size": 10,
                    "columns": ["a"],
                },
            )
        )
        from querri.resources.sources import Sources
        from querri.types.data import DataPage

        sources = Sources(_http())
        result = sources.source_data("src_1", page=2, page_size=10)
        assert isinstance(result, DataPage)
        assert result.data == [{"a": 1}]
        assert result.total_rows == 50  # aliased from total_count
        req = route.calls[0].request
        assert "page=2" in str(req.url)
        assert "page_size=10" in str(req.url)

    @respx.mock
    def test_append_rows(self):
        respx.post(f"{BASE}/sources/src_1/rows").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "src_1",
                    "name": "Test",
                    "columns": ["x"],
                    "row_count": 5,
                },
            )
        )
        from querri.resources.sources import Sources
        from querri.types.data import DataWriteResult

        sources = Sources(_http())
        result = sources.append_rows("src_1", rows=[{"x": 10}])
        assert isinstance(result, DataWriteResult)
        assert result.row_count == 5

    @respx.mock
    def test_replace_data(self):
        respx.put(f"{BASE}/sources/src_1/data").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "src_1",
                    "name": "Test",
                    "columns": ["x"],
                    "row_count": 2,
                },
            )
        )
        from querri.resources.sources import Sources
        from querri.types.data import DataWriteResult

        sources = Sources(_http())
        result = sources.replace_data("src_1", rows=[{"x": 1}, {"x": 2}])
        assert isinstance(result, DataWriteResult)
        assert result.row_count == 2

    @respx.mock
    def test_ask(self):
        route = respx.post(f"{BASE}/sources/src_1/ask").mock(
            return_value=httpx.Response(
                200,
                json={
                    "answer": "42",
                    "data": [{"result": 42}],
                },
            )
        )
        from querri.resources.sources import Sources

        sources = Sources(_http())
        result = sources.ask("src_1", question="What is the meaning?")
        assert result["answer"] == "42"
        assert b"What is the meaning?" in route.calls[0].request.content

    @respx.mock
    def test_list_connectors(self):
        respx.get(f"{BASE}/connectors").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "conn_1",
                            "name": "PostgreSQL",
                            "service": "postgres",
                            "status": "active",
                        },
                    ],
                },
            )
        )
        from querri.resources.sources import Sources

        sources = Sources(_http())
        result = sources.list_connectors()
        assert len(result) == 1
        assert result[0]["name"] == "PostgreSQL"


# =========================================================================
# Files
# =========================================================================


class TestFiles:
    """Tests for querri.resources.files.Files (skip upload)."""

    @respx.mock
    def test_get(self):
        respx.get(f"{BASE}/files/file_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "file_1",
                    "name": "data.csv",
                    "size": 1024,
                    "content_type": "text/csv",
                },
            )
        )
        from querri.resources.files import Files
        from querri.types.file import File

        files = Files(_http())
        result = files.get("file_1")
        assert isinstance(result, File)
        assert result.id == "file_1"
        assert result.name == "data.csv"
        assert result.size == 1024

    @respx.mock
    def test_list(self):
        respx.get(f"{BASE}/files").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "file_1", "name": "a.csv"},
                        {"id": "file_2", "name": "b.csv"},
                    ],
                },
            )
        )
        from querri.resources.files import Files
        from querri.types.file import File

        files = Files(_http())
        result = files.list()
        assert len(result) == 2
        assert all(isinstance(f, File) for f in result)
        assert result[0].name == "a.csv"

    @respx.mock
    def test_delete(self):
        route = respx.delete(f"{BASE}/files/file_1").mock(
            return_value=httpx.Response(204)
        )
        from querri.resources.files import Files

        files = Files(_http())
        files.delete("file_1")
        assert route.called


# =========================================================================
# Views
# =========================================================================


class TestViews:
    """Tests for querri.resources.views.Views."""

    @respx.mock
    def test_create(self):
        respx.post(f"{BASE}/views").mock(
            return_value=httpx.Response(
                200,
                json={
                    "uuid": "view_1",
                    "name": "Revenue",
                    "sql_definition": "SELECT sum(revenue) FROM sales",
                },
            )
        )
        from querri.resources.views import Views

        views = Views(_http())
        result = views.create(
            name="Revenue",
            sql_definition="SELECT sum(revenue) FROM sales",
        )
        assert result["uuid"] == "view_1"
        assert result["name"] == "Revenue"

    @respx.mock
    def test_create_draft(self):
        """Creating a view with no fields produces a draft."""
        route = respx.post(f"{BASE}/views").mock(
            return_value=httpx.Response(
                200,
                json={
                    "uuid": "view_draft",
                    "name": None,
                    "sql_definition": None,
                },
            )
        )
        from querri.resources.views import Views

        views = Views(_http())
        result = views.create()
        assert result["uuid"] == "view_draft"
        # Body should be an empty JSON object
        assert route.calls[0].request.content in (b"{}", b"{ }")

    @respx.mock
    def test_list(self):
        respx.get(f"{BASE}/views").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"uuid": "view_1", "name": "A"},
                        {"uuid": "view_2", "name": "B"},
                    ],
                },
            )
        )
        from querri.resources.views import Views

        views = Views(_http())
        result = views.list()
        assert len(result) == 2
        assert result[0]["uuid"] == "view_1"

    @respx.mock
    def test_list_returns_raw_list(self):
        """If API returns a plain list instead of {data: [...]}, handle it."""
        respx.get(f"{BASE}/views").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"uuid": "view_1", "name": "A"},
                ],
            )
        )
        from querri.resources.views import Views

        views = Views(_http())
        result = views.list()
        assert len(result) == 1

    @respx.mock
    def test_get(self):
        respx.get(f"{BASE}/views/view_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "uuid": "view_1",
                    "name": "Revenue",
                    "sql_definition": "SELECT 1",
                },
            )
        )
        from querri.resources.views import Views

        views = Views(_http())
        result = views.get("view_1")
        assert result["uuid"] == "view_1"

    @respx.mock
    def test_update(self):
        route = respx.patch(f"{BASE}/views/view_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "uuid": "view_1",
                    "sql_definition": "SELECT 2",
                },
            )
        )
        from querri.resources.views import Views

        views = Views(_http())
        result = views.update("view_1", sql_definition="SELECT 2")
        assert result["sql_definition"] == "SELECT 2"
        assert b"SELECT 2" in route.calls[0].request.content

    @respx.mock
    def test_delete(self):
        route = respx.delete(f"{BASE}/views/view_1").mock(
            return_value=httpx.Response(204)
        )
        from querri.resources.views import Views

        views = Views(_http())
        views.delete("view_1")
        assert route.called

    @respx.mock
    def test_run(self):
        respx.post(f"{BASE}/views/run").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "started",
                    "view_count": 3,
                },
            )
        )
        from querri.resources.views import Views

        views = Views(_http())
        result = views.run()
        assert result["status"] == "started"

    @respx.mock
    def test_run_specific_views(self):
        route = respx.post(f"{BASE}/views/run").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "started",
                    "view_count": 2,
                },
            )
        )
        from querri.resources.views import Views

        views = Views(_http())
        result = views.run(view_uuids=["view_1", "view_2"])
        assert result["view_count"] == 2
        assert b"view_uuids" in route.calls[0].request.content

    @respx.mock
    def test_preview(self):
        route = respx.post(f"{BASE}/views/view_1/preview").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"col": "val"}],
                    "columns": ["col"],
                },
            )
        )
        from querri.resources.views import Views

        views = Views(_http())
        result = views.preview("view_1", limit=50)
        assert result["data"] == [{"col": "val"}]
        assert (
            b'"limit": 50' in route.calls[0].request.content
            or b'"limit":50' in route.calls[0].request.content
        )

    @respx.mock
    def test_generate_metadata(self):
        respx.post(f"{BASE}/views/view_1/generate-metadata").mock(
            return_value=httpx.Response(
                200,
                json={
                    "name": "Generated Name",
                    "description": "Generated description",
                },
            )
        )
        from querri.resources.views import Views

        views = Views(_http())
        result = views.generate_metadata("view_1")
        assert result["name"] == "Generated Name"


# =========================================================================
# Policies
# =========================================================================


class TestPolicies:
    """Tests for querri.resources.policies.Policies."""

    @respx.mock
    def test_create(self):
        respx.post(f"{BASE}/access/policies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "pol_1",
                    "name": "Sales",
                    "source_ids": ["src_1"],
                    "row_filters": [],
                    "user_count": 0,
                },
            )
        )
        from querri.resources.policies import Policies
        from querri.types.policy import Policy

        policies = Policies(_http())
        result = policies.create(name="Sales", source_ids=["src_1"])
        assert isinstance(result, Policy)
        assert result.id == "pol_1"
        assert result.source_ids == ["src_1"]

    @respx.mock
    def test_create_with_row_filters(self):
        respx.post(f"{BASE}/access/policies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "pol_2",
                    "name": "Region Filter",
                    "source_ids": ["src_1"],
                    "row_filters": [{"column": "region", "values": ["US"]}],
                    "user_count": 0,
                },
            )
        )
        from querri.resources.policies import Policies

        policies = Policies(_http())
        result = policies.create(
            name="Region Filter",
            source_ids=["src_1"],
            row_filters=[{"column": "region", "values": ["US"]}],
        )
        assert len(result.row_filters) == 1
        assert result.row_filters[0].column == "region"
        assert result.row_filters[0].values == ["US"]

    @respx.mock
    def test_get(self):
        respx.get(f"{BASE}/access/policies/pol_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "pol_1",
                    "name": "Sales",
                    "source_ids": [],
                    "row_filters": [],
                    "user_count": 2,
                    "user_ids": ["usr_1", "usr_2"],
                },
            )
        )
        from querri.resources.policies import Policies

        policies = Policies(_http())
        result = policies.get("pol_1")
        assert result.user_count == 2
        assert result.assigned_user_ids == ["usr_1", "usr_2"]

    @respx.mock
    def test_list(self):
        respx.get(f"{BASE}/access/policies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "pol_1",
                            "name": "A",
                            "source_ids": [],
                            "row_filters": [],
                            "user_count": 0,
                        },
                    ],
                    "has_more": False,
                },
            )
        )
        from querri.resources.policies import Policies
        from querri.types.policy import Policy

        policies = Policies(_http())
        items = list(policies.list())
        assert len(items) == 1
        assert isinstance(items[0], Policy)

    @respx.mock
    def test_list_with_name_filter(self):
        route = respx.get(f"{BASE}/access/policies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "pol_1",
                            "name": "Exact",
                            "source_ids": [],
                            "row_filters": [],
                            "user_count": 0,
                        },
                    ],
                    "has_more": False,
                },
            )
        )
        from querri.resources.policies import Policies

        policies = Policies(_http())
        items = list(policies.list(name="Exact"))
        assert len(items) == 1
        assert "name=Exact" in str(route.calls[0].request.url)

    @respx.mock
    def test_update(self):
        respx.patch(f"{BASE}/access/policies/pol_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "pol_1",
                    "updated": True,
                },
            )
        )
        from querri.resources.policies import Policies
        from querri.types.policy import PolicyUpdateResponse

        policies = Policies(_http())
        result = policies.update("pol_1", name="New Name")
        assert isinstance(result, PolicyUpdateResponse)
        assert result.updated is True

    @respx.mock
    def test_delete(self):
        respx.delete(f"{BASE}/access/policies/pol_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "pol_1",
                    "deleted": True,
                },
            )
        )
        from querri.resources.policies import Policies
        from querri.types.policy import PolicyDeleteResponse

        policies = Policies(_http())
        result = policies.delete("pol_1")
        assert isinstance(result, PolicyDeleteResponse)
        assert result.deleted is True

    @respx.mock
    def test_assign_users(self):
        respx.post(f"{BASE}/access/policies/pol_1/users").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policy_id": "pol_1",
                    "assigned_user_ids": ["usr_1", "usr_2"],
                },
            )
        )
        from querri.resources.policies import Policies
        from querri.types.policy import PolicyAssignResponse

        policies = Policies(_http())
        result = policies.assign_users("pol_1", user_ids=["usr_1", "usr_2"])
        assert isinstance(result, PolicyAssignResponse)
        assert result.policy_id == "pol_1"
        assert result.assigned_user_ids == ["usr_1", "usr_2"]

    @respx.mock
    def test_remove_user(self):
        respx.delete(f"{BASE}/access/policies/pol_1/users/usr_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policy_id": "pol_1",
                    "user_id": "usr_1",
                    "removed": True,
                },
            )
        )
        from querri.resources.policies import Policies
        from querri.types.policy import PolicyRemoveUserResponse

        policies = Policies(_http())
        result = policies.remove_user("pol_1", "usr_1")
        assert isinstance(result, PolicyRemoveUserResponse)
        assert result.removed is True

    @respx.mock
    def test_resolve(self):
        respx.post(f"{BASE}/access/resolve").mock(
            return_value=httpx.Response(
                200,
                json={
                    "user_id": "usr_1",
                    "source_id": "src_1",
                    "source_is_access_controlled": True,
                    "effective_access": "filtered",
                    "resolved_filters": {
                        "row_filters": {"region": ["US"]},
                        "has_any_policy": True,
                    },
                    "where_clause": "region IN ('US')",
                },
            )
        )
        from querri.resources.policies import Policies
        from querri.types.policy import ResolvedAccess

        policies = Policies(_http())
        result = policies.resolve(user_id="usr_1", source_id="src_1")
        assert isinstance(result, ResolvedAccess)
        assert result.effective_access == "filtered"
        assert result.where_clause == "region IN ('US')"
        assert result.source_is_access_controlled is True

    @respx.mock
    def test_columns(self):
        respx.get(f"{BASE}/access/columns").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "source_id": "src_1",
                            "source_name": "Sales",
                            "columns": [
                                {"name": "region", "type": "string"},
                                {"name": "revenue", "type": "number"},
                            ],
                        },
                    ],
                },
            )
        )
        from querri.resources.policies import Policies
        from querri.types.policy import SourceColumns

        policies = Policies(_http())
        result = policies.columns()
        assert len(result) == 1
        assert isinstance(result[0], SourceColumns)
        assert result[0].source_id == "src_1"
        assert len(result[0].columns) == 2
        assert result[0].columns[0].name == "region"

    @respx.mock
    def test_columns_with_source_filter(self):
        route = respx.get(f"{BASE}/access/columns").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"source_id": "src_1", "source_name": "Sales", "columns": []},
                    ],
                },
            )
        )
        from querri.resources.policies import Policies

        policies = Policies(_http())
        policies.columns(source_id="src_1")
        assert "source_id=src_1" in str(route.calls[0].request.url)

    @respx.mock
    def test_replace_user_policies(self):
        respx.put(f"{BASE}/access/users/usr_1/policies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "user_id": "usr_1",
                    "policy_ids": ["pol_a"],
                    "added": ["pol_a"],
                    "removed": ["pol_old"],
                },
            )
        )
        from querri.resources.policies import Policies
        from querri.types.policy import PolicyReplaceResponse

        policies = Policies(_http())
        result = policies.replace_user_policies("usr_1", policy_ids=["pol_a"])
        assert isinstance(result, PolicyReplaceResponse)
        assert result.policy_ids == ["pol_a"]
        assert result.added == ["pol_a"]
        assert result.removed == ["pol_old"]


# =========================================================================
# Embed
# =========================================================================


class TestEmbed:
    """Tests for querri.resources.embed.Embed."""

    @respx.mock
    def test_create_session(self):
        respx.post(f"{BASE}/embed/sessions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_token": "es_abc123",
                    "expires_in": 3600,
                    "user_id": "usr_1",
                },
            )
        )
        from querri.resources.embed import Embed
        from querri.types.embed import EmbedSession

        embed = Embed(_http())
        result = embed.create_session(user_id="usr_1")
        assert isinstance(result, EmbedSession)
        assert result.session_token == "es_abc123"
        assert result.expires_in == 3600
        assert result.user_id == "usr_1"

    @respx.mock
    def test_create_session_with_origin_and_ttl(self):
        route = respx.post(f"{BASE}/embed/sessions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_token": "es_xyz",
                    "expires_in": 7200,
                    "user_id": "usr_1",
                },
            )
        )
        from querri.resources.embed import Embed

        embed = Embed(_http())
        result = embed.create_session(
            user_id="usr_1",
            origin="https://example.com",
            ttl=7200,
        )
        assert result.expires_in == 7200
        req_body = route.calls[0].request.content
        assert b"origin" in req_body
        assert b"example.com" in req_body

    @respx.mock
    def test_create_session_with_source_scope(self):
        route = respx.post(f"{BASE}/embed/sessions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_token": "es_scoped",
                    "expires_in": 3600,
                },
            )
        )
        from querri.resources.embed import Embed

        embed = Embed(_http())
        embed.create_session(user_id="usr_1", source_scope=["src_1", "src_2"])
        req_body = route.calls[0].request.content
        assert b"source_scope" in req_body

    @respx.mock
    def test_refresh_session(self):
        respx.post(f"{BASE}/embed/sessions/refresh").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_token": "es_new",
                    "expires_in": 3600,
                },
            )
        )
        from querri.resources.embed import Embed

        embed = Embed(_http())
        result = embed.refresh_session(session_token="es_old")
        assert result.session_token == "es_new"

    @respx.mock
    def test_list_sessions(self):
        respx.get(f"{BASE}/embed/sessions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"session_token": "es_1", "user_id": "usr_1"},
                        {"session_token": "es_2", "user_id": "usr_2"},
                    ],
                    "has_more": False,
                },
            )
        )
        from querri.resources.embed import Embed
        from querri.types.embed import EmbedSessionList

        embed = Embed(_http())
        result = embed.list_sessions()
        assert isinstance(result, EmbedSessionList)
        assert len(result.data) == 2
        assert result.data[0].session_token == "es_1"

    @respx.mock
    def test_revoke_session_by_id(self):
        respx.delete(f"{BASE}/embed/sessions/es_abc").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "es_abc",
                    "revoked": True,
                },
            )
        )
        from querri.resources.embed import Embed
        from querri.types.embed import EmbedSessionRevokeResponse

        embed = Embed(_http())
        result = embed.revoke_session("es_abc")
        assert isinstance(result, EmbedSessionRevokeResponse)
        assert result.revoked is True

    @respx.mock
    def test_revoke_session_by_token_kwarg(self):
        respx.delete(f"{BASE}/embed/sessions/es_tok").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "es_tok",
                    "revoked": True,
                },
            )
        )
        from querri.resources.embed import Embed

        embed = Embed(_http())
        result = embed.revoke_session(session_token="es_tok")
        assert result.revoked is True

    def test_revoke_session_raises_without_args(self):
        from querri.resources.embed import Embed

        embed = Embed(_http())
        with pytest.raises(ValueError, match="Either session_id or session_token"):
            embed.revoke_session()

    @respx.mock
    def test_revoke_user_sessions(self):
        """Test the compound revoke_user_sessions method."""
        respx.get(f"{BASE}/embed/sessions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"session_token": "es_1", "user_id": "usr_target"},
                        {"session_token": "es_2", "user_id": "usr_other"},
                        {"session_token": "es_3", "user_id": "usr_target"},
                    ],
                    "has_more": False,
                },
            )
        )
        respx.delete(f"{BASE}/embed/sessions/es_1").mock(
            return_value=httpx.Response(200, json={"id": "es_1", "revoked": True})
        )
        respx.delete(f"{BASE}/embed/sessions/es_3").mock(
            return_value=httpx.Response(200, json={"id": "es_3", "revoked": True})
        )
        from querri.resources.embed import Embed

        embed = Embed(_http())
        count = embed.revoke_user_sessions("usr_target")
        assert count == 2


# =========================================================================
# Usage
# =========================================================================


class TestUsage:
    """Tests for querri.resources.usage.Usage."""

    @respx.mock
    def test_org_usage(self):
        route = respx.get(f"{BASE}/usage").mock(
            return_value=httpx.Response(
                200,
                json={
                    "org_id": "org_test",
                    "period": "current_month",
                    "period_start": "2025-01-01T00:00:00Z",
                    "period_end": "2025-01-31T23:59:59Z",
                    "total_ai_messages": 500,
                    "active_user_count": 10,
                    "project_count": 25,
                },
            )
        )
        from querri.resources.usage import Usage
        from querri.types.usage import OrgUsageReport

        usage = Usage(_http())
        result = usage.org_usage()
        assert isinstance(result, OrgUsageReport)
        assert result.total_ai_messages == 500
        assert result.active_user_count == 10
        assert "period=current_month" in str(route.calls[0].request.url)

    @respx.mock
    def test_org_usage_custom_period(self):
        route = respx.get(f"{BASE}/usage").mock(
            return_value=httpx.Response(
                200,
                json={
                    "period": "last_30_days",
                    "total_ai_messages": 200,
                },
            )
        )
        from querri.resources.usage import Usage

        usage = Usage(_http())
        result = usage.org_usage(period="last_30_days")
        assert result.period == "last_30_days"
        assert "period=last_30_days" in str(route.calls[0].request.url)

    @respx.mock
    def test_user_usage(self):
        respx.get(f"{BASE}/usage/users/usr_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "user_id": "usr_1",
                    "period": "current_month",
                    "period_start": "2025-01-01T00:00:00Z",
                    "period_end": "2025-01-31T23:59:59Z",
                    "ai_messages": 42,
                    "daily_breakdown": [
                        {"date": "2025-01-15", "count": 10},
                        {"date": "2025-01-16", "count": 32},
                    ],
                },
            )
        )
        from querri.resources.usage import Usage
        from querri.types.usage import UserUsageReport

        usage = Usage(_http())
        result = usage.user_usage("usr_1")
        assert isinstance(result, UserUsageReport)
        assert result.ai_messages == 42
        assert len(result.daily_breakdown) == 2
        assert result.daily_breakdown[0].date == "2025-01-15"


# =========================================================================
# Audit
# =========================================================================


class TestAudit:
    """Tests for querri.resources.audit.Audit."""

    @respx.mock
    def test_list(self):
        respx.get(f"{BASE}/audit/events").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "evt_1",
                            "actor_id": "usr_1",
                            "actor_type": "user",
                            "action": "data.query",
                            "target_type": "source",
                            "target_id": "src_1",
                            "timestamp": "2025-01-15T10:00:00Z",
                        },
                        {
                            "id": "evt_2",
                            "actor_id": "usr_2",
                            "actor_type": "user",
                            "action": "file.upload",
                            "target_type": "file",
                            "target_id": "file_1",
                            "timestamp": "2025-01-15T11:00:00Z",
                        },
                    ],
                },
            )
        )
        from querri.resources.audit import Audit
        from querri.types.audit import AuditEvent

        audit = Audit(_http())
        result = audit.list()
        assert len(result) == 2
        assert all(isinstance(e, AuditEvent) for e in result)
        assert result[0].action == "data.query"
        assert result[1].target_type == "file"

    @respx.mock
    def test_list_with_filters(self):
        route = respx.get(f"{BASE}/audit/events").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        from querri.resources.audit import Audit

        audit = Audit(_http())
        audit.list(
            actor_id="usr_1",
            action="data.query",
            start_date="2025-01-01",
            end_date="2025-01-31",
            limit=10,
        )
        url = str(route.calls[0].request.url)
        assert "actor_id=usr_1" in url
        assert "action=data.query" in url
        assert "start_date=2025-01-01" in url
        assert "end_date=2025-01-31" in url
        assert "limit=10" in url

    @respx.mock
    def test_list_with_pagination_cursor(self):
        route = respx.get(f"{BASE}/audit/events").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        from querri.resources.audit import Audit

        audit = Audit(_http())
        audit.list(after="cursor_abc")
        assert "after=cursor_abc" in str(route.calls[0].request.url)


# =========================================================================
# Sharing
# =========================================================================


class TestSharing:
    """Tests for querri.resources.sharing.Sharing."""

    # -- Project sharing --

    @respx.mock
    def test_share_project(self):
        respx.post(f"{BASE}/projects/proj_1/shares").mock(
            return_value=httpx.Response(
                200,
                json={
                    "user_id": "usr_1",
                    "permission": "edit",
                    "resource_type": "project",
                    "resource_id": "proj_1",
                    "granted_by": "usr_admin",
                },
            )
        )
        from querri.resources.sharing import Sharing
        from querri.types.sharing import ShareEntry

        sharing = Sharing(_http())
        result = sharing.share_project("proj_1", user_id="usr_1", permission="edit")
        assert isinstance(result, ShareEntry)
        assert result.user_id == "usr_1"
        assert result.permission == "edit"
        assert result.resource_type == "project"
        assert result.granted_by == "usr_admin"

    @respx.mock
    def test_revoke_project_share(self):
        respx.delete(f"{BASE}/projects/proj_1/shares/usr_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "user_id": "usr_1",
                    "resource_type": "project",
                    "resource_id": "proj_1",
                    "revoked": True,
                },
            )
        )
        from querri.resources.sharing import Sharing

        sharing = Sharing(_http())
        result = sharing.revoke_project_share("proj_1", "usr_1")
        assert result["revoked"] is True

    @respx.mock
    def test_list_project_shares(self):
        respx.get(f"{BASE}/projects/proj_1/shares").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"user_id": "usr_1", "permission": "view"},
                        {"user_id": "usr_2", "permission": "edit"},
                    ],
                },
            )
        )
        from querri.resources.sharing import Sharing
        from querri.types.sharing import ShareEntry

        sharing = Sharing(_http())
        result = sharing.list_project_shares("proj_1")
        assert len(result) == 2
        assert all(isinstance(s, ShareEntry) for s in result)
        assert result[1].permission == "edit"

    # -- Dashboard sharing --

    @respx.mock
    def test_share_dashboard(self):
        respx.post(f"{BASE}/dashboards/dash_1/shares").mock(
            return_value=httpx.Response(
                200,
                json={
                    "user_id": "usr_1",
                    "permission": "view",
                    "resource_type": "dashboard",
                    "resource_id": "dash_1",
                    "granted_by": "usr_admin",
                },
            )
        )
        from querri.resources.sharing import Sharing
        from querri.types.sharing import ShareEntry

        sharing = Sharing(_http())
        result = sharing.share_dashboard("dash_1", user_id="usr_1")
        assert isinstance(result, ShareEntry)
        assert result.resource_type == "dashboard"

    @respx.mock
    def test_revoke_dashboard_share(self):
        respx.delete(f"{BASE}/dashboards/dash_1/shares/usr_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "user_id": "usr_1",
                    "resource_type": "dashboard",
                    "resource_id": "dash_1",
                    "revoked": True,
                },
            )
        )
        from querri.resources.sharing import Sharing

        sharing = Sharing(_http())
        result = sharing.revoke_dashboard_share("dash_1", "usr_1")
        assert result["revoked"] is True

    @respx.mock
    def test_list_dashboard_shares(self):
        respx.get(f"{BASE}/dashboards/dash_1/shares").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"user_id": "usr_1", "permission": "view"},
                    ],
                },
            )
        )
        from querri.resources.sharing import Sharing
        from querri.types.sharing import ShareEntry

        sharing = Sharing(_http())
        result = sharing.list_dashboard_shares("dash_1")
        assert len(result) == 1
        assert isinstance(result[0], ShareEntry)

    # -- Source sharing --

    @respx.mock
    def test_share_source(self):
        respx.post(f"{BASE}/sources/src_1/shares").mock(
            return_value=httpx.Response(
                200,
                json={
                    "user_id": "usr_1",
                    "permission": "view",
                    "resource_type": "source",
                    "resource_id": "src_1",
                },
            )
        )
        from querri.resources.sharing import Sharing
        from querri.types.sharing import ShareEntry

        sharing = Sharing(_http())
        result = sharing.share_source("src_1", user_id="usr_1")
        assert isinstance(result, ShareEntry)
        assert result.resource_type == "source"

    @respx.mock
    def test_share_source_with_edit(self):
        route = respx.post(f"{BASE}/sources/src_1/shares").mock(
            return_value=httpx.Response(
                200,
                json={
                    "user_id": "usr_1",
                    "permission": "edit",
                    "resource_type": "source",
                    "resource_id": "src_1",
                },
            )
        )
        from querri.resources.sharing import Sharing

        sharing = Sharing(_http())
        result = sharing.share_source("src_1", user_id="usr_1", permission="edit")
        assert result.permission == "edit"
        assert b'"permission"' in route.calls[0].request.content

    @respx.mock
    def test_org_share_source(self):
        route = respx.post(f"{BASE}/sources/src_1/org-share").mock(
            return_value=httpx.Response(
                200,
                json={
                    "source_id": "src_1",
                    "enabled": True,
                    "permission": "view",
                },
            )
        )
        from querri.resources.sharing import Sharing

        sharing = Sharing(_http())
        result = sharing.org_share_source("src_1", enabled=True)
        assert result["enabled"] is True
        assert (
            b'"enabled": true' in route.calls[0].request.content
            or b'"enabled":true' in route.calls[0].request.content
        )


# =========================================================================
# Error handling: HTTP errors surface correctly
# =========================================================================


class TestHTTPErrors:
    """Verify that HTTP errors from the API propagate as exceptions."""

    @respx.mock
    def test_404_raises(self):
        from querri._exceptions import NotFoundError

        respx.get(f"{BASE}/users/nonexistent").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        from querri.resources.users import Users

        users = Users(_http())
        with pytest.raises(NotFoundError):
            users.get("nonexistent")

    @respx.mock
    def test_401_raises(self):
        from querri._exceptions import AuthenticationError

        respx.get(f"{BASE}/users/usr_1").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        from querri.resources.users import Users

        users = Users(_http())
        with pytest.raises(AuthenticationError):
            users.get("usr_1")

    @respx.mock
    def test_429_raises(self):
        from querri._exceptions import RateLimitError

        respx.get(f"{BASE}/keys").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        from querri.resources.keys import Keys

        keys = Keys(_http())
        with pytest.raises(RateLimitError):
            keys.list()

    @respx.mock
    def test_500_raises(self):
        from querri._exceptions import ServerError

        respx.post(f"{BASE}/dashboards").mock(
            return_value=httpx.Response(500, json={"error": "Internal error"})
        )
        from querri.resources.dashboards import Dashboards

        dash = Dashboards(_http())
        with pytest.raises(ServerError):
            dash.create(name="Fail")


# =========================================================================
# Request body correctness: optional fields are omitted when not set
# =========================================================================


class TestOptionalFieldOmission:
    """Verify that optional parameters are not sent when not provided."""

    @respx.mock
    def test_user_create_minimal_body(self):
        route = respx.post(f"{BASE}/users").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "usr_1",
                    "email": "a@b.com",
                    "role": "member",
                },
            )
        )
        from querri.resources.users import Users

        users = Users(_http())
        users.create(email="a@b.com")
        body = route.calls[0].request.content
        assert b"external_id" not in body
        assert b"first_name" not in body
        assert b"last_name" not in body

    @respx.mock
    def test_user_update_empty_body_when_no_fields(self):
        route = respx.patch(f"{BASE}/users/usr_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "usr_1",
                    "email": "a@b.com",
                    "role": "member",
                },
            )
        )
        from querri.resources.users import Users

        users = Users(_http())
        users.update("usr_1")
        body = route.calls[0].request.content
        assert body == b"{}"

    @respx.mock
    def test_dashboard_update_only_sends_provided_fields(self):
        route = respx.patch(f"{BASE}/dashboards/dash_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "dash_1",
                    "updated": True,
                },
            )
        )
        from querri.resources.dashboards import Dashboards

        dash = Dashboards(_http())
        dash.update("dash_1", description="new desc")
        body = route.calls[0].request.content
        assert b"description" in body
        assert b"name" not in body

    @respx.mock
    def test_source_update_only_sends_provided_fields(self):
        route = respx.patch(f"{BASE}/sources/src_1").mock(
            return_value=httpx.Response(200, json={"id": "src_1", "updated": True})
        )
        from querri.resources.sources import Sources

        sources = Sources(_http())
        sources.update("src_1", description="notes")
        body = route.calls[0].request.content
        assert b"description" in body
        assert b"name" not in body
        assert b"config" not in body

    @respx.mock
    def test_policy_create_minimal(self):
        route = respx.post(f"{BASE}/access/policies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "pol_1",
                    "name": "Test",
                    "source_ids": [],
                    "row_filters": [],
                    "user_count": 0,
                },
            )
        )
        from querri.resources.policies import Policies

        policies = Policies(_http())
        policies.create(name="Test")
        body = route.calls[0].request.content
        assert b"source_ids" not in body
        assert b"row_filters" not in body
        assert b"description" not in body
