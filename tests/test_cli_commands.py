"""Comprehensive CLI command tests for every resource module.

Uses Typer's CliRunner with mocked SDK clients to verify correct behavior
including happy paths, JSON output, quiet mode, and missing-arg errors.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from querri.cli._app import main_app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_GLOBAL = ["--api-key", "qk_test123456", "--org-id", "org_1"]
_JSON = ["--json"]
_QUIET = ["-q"]


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class TestUsersCommands:
    """Tests for querri user list/get/new/update/delete."""

    def _make_user(self, **overrides):
        from querri.types.user import User

        defaults = dict(
            id="usr_1",
            email="alice@example.com",
            role="member",
            first_name="Alice",
            last_name="Smith",
            external_id=None,
            created_at="2025-01-01T00:00:00Z",
        )
        defaults.update(overrides)
        return User(**defaults)

    # -- list ---------------------------------------------------------------

    def test_user_list(self) -> None:
        mock_client = MagicMock()
        mock_client.users.list.return_value = [self._make_user()]
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "user", "list"])
        assert result.exit_code == 0
        assert "alice@example.com" in result.output

    def test_user_list_json(self) -> None:
        mock_client = MagicMock()
        mock_client.users.list.return_value = [self._make_user()]
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "user", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["email"] == "alice@example.com"

    def test_user_list_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.users.list.return_value = [self._make_user()]
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_QUIET, "user", "list"])
        assert result.exit_code == 0
        assert "usr_1" in result.output

    # -- get ----------------------------------------------------------------

    def test_user_get(self) -> None:
        mock_client = MagicMock()
        mock_client.users.get.return_value = self._make_user()
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "user", "get", "usr_1"])
        assert result.exit_code == 0
        assert "alice@example.com" in result.output
        mock_client.users.get.assert_called_once_with("usr_1")

    def test_user_get_json(self) -> None:
        mock_client = MagicMock()
        mock_client.users.get.return_value = self._make_user()
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "user", "get", "usr_1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "usr_1"

    def test_user_get_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.users.get.return_value = self._make_user()
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_QUIET, "user", "get", "usr_1"]
            )
        assert result.exit_code == 0
        assert result.output.strip() == "usr_1"

    def test_user_get_missing_id_non_interactive(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "user", "get"])
        assert result.exit_code != 0
        assert "Missing" in result.output or "USER_ID" in result.output

    # -- new ----------------------------------------------------------------

    def test_user_new(self) -> None:
        mock_client = MagicMock()
        mock_client.users.create.return_value = self._make_user()
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    *_GLOBAL,
                    "user",
                    "new",
                    "--email",
                    "alice@example.com",
                    "--role",
                    "admin",
                ],
            )
        assert result.exit_code == 0
        assert "Created" in result.output
        mock_client.users.create.assert_called_once_with(
            email="alice@example.com",
            role="admin",
            external_id=None,
            first_name=None,
            last_name=None,
        )

    def test_user_new_json(self) -> None:
        mock_client = MagicMock()
        mock_client.users.create.return_value = self._make_user()
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "user", "new", "--email", "alice@example.com"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "usr_1"

    def test_user_new_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.users.create.return_value = self._make_user()
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_QUIET, "user", "new", "--email", "alice@example.com"],
            )
        assert result.exit_code == 0
        assert result.output.strip() == "usr_1"

    def test_user_new_missing_email_non_interactive(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "user", "new"])
        assert result.exit_code != 0
        assert "email" in result.output.lower() or "Missing" in result.output

    # -- update -------------------------------------------------------------

    def test_user_update_role_only(self) -> None:
        """update sends only non-None kwargs to the SDK."""
        mock_client = MagicMock()
        mock_client.users.update.return_value = self._make_user(role="admin")
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "user", "update", "usr_1", "--role", "admin"],
            )
        assert result.exit_code == 0
        mock_client.users.update.assert_called_once_with("usr_1", role="admin")

    def test_user_update_first_name_only(self) -> None:
        mock_client = MagicMock()
        mock_client.users.update.return_value = self._make_user(first_name="Bob")
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "user", "update", "usr_1", "--first-name", "Bob"],
            )
        assert result.exit_code == 0
        mock_client.users.update.assert_called_once_with("usr_1", first_name="Bob")

    def test_user_update_last_name_only(self) -> None:
        mock_client = MagicMock()
        mock_client.users.update.return_value = self._make_user(last_name="Jones")
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "user", "update", "usr_1", "--last-name", "Jones"],
            )
        assert result.exit_code == 0
        mock_client.users.update.assert_called_once_with("usr_1", last_name="Jones")

    def test_user_update_multiple_fields(self) -> None:
        mock_client = MagicMock()
        mock_client.users.update.return_value = self._make_user()
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    *_GLOBAL,
                    "user",
                    "update",
                    "usr_1",
                    "--role",
                    "admin",
                    "--first-name",
                    "Al",
                ],
            )
        assert result.exit_code == 0
        mock_client.users.update.assert_called_once_with(
            "usr_1", role="admin", first_name="Al"
        )

    def test_user_update_json(self) -> None:
        mock_client = MagicMock()
        mock_client.users.update.return_value = self._make_user()
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "user", "update", "usr_1", "--role", "admin"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "usr_1"

    def test_user_update_missing_id_non_interactive(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "user", "update"])
        assert result.exit_code != 0

    # -- delete -------------------------------------------------------------

    def test_user_delete(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "user", "delete", "usr_1"])
        assert result.exit_code == 0
        assert "Deleted" in result.output
        mock_client.users.delete.assert_called_once_with("usr_1")

    def test_user_delete_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.users.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "user", "delete", "usr_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] is True

    def test_user_delete_missing_id_non_interactive(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "user", "delete"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------


class TestDashboardsCommands:
    """Tests for querri dashboard list/get/new/update/delete/refresh."""

    def _make_dashboard(self, **overrides):
        from querri.types.dashboard import Dashboard

        defaults = dict(
            id="dash_1",
            name="Sales Dashboard",
            description="Overview",
            widget_count=5,
            created_by="usr_1",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
        )
        defaults.update(overrides)
        return Dashboard(**defaults)

    # -- list ---------------------------------------------------------------

    def test_dashboard_list(self) -> None:
        mock_client = MagicMock()
        mock_client.dashboards.list.return_value = [self._make_dashboard()]
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "dashboard", "list"])
        assert result.exit_code == 0
        assert "Sales Dashboard" in result.output

    def test_dashboard_list_json(self) -> None:
        mock_client = MagicMock()
        mock_client.dashboards.list.return_value = [self._make_dashboard()]
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "dashboard", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "Sales Dashboard"

    def test_dashboard_list_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.dashboards.list.return_value = [self._make_dashboard()]
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_QUIET, "dashboard", "list"])
        assert result.exit_code == 0
        assert "dash_1" in result.output

    # -- get ----------------------------------------------------------------

    def test_dashboard_get(self) -> None:
        mock_client = MagicMock()
        mock_client.dashboards.get.return_value = self._make_dashboard()
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "dashboard", "get", "dash_1"])
        assert result.exit_code == 0
        assert "Sales Dashboard" in result.output

    def test_dashboard_get_json(self) -> None:
        mock_client = MagicMock()
        mock_client.dashboards.get.return_value = self._make_dashboard()
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "dashboard", "get", "dash_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "dash_1"

    def test_dashboard_get_missing_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "dashboard", "get"])
        assert result.exit_code != 0

    # -- new ----------------------------------------------------------------

    def test_dashboard_new(self) -> None:
        mock_client = MagicMock()
        mock_client.dashboards.create.return_value = self._make_dashboard()
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "dashboard", "new", "--name", "Sales Dashboard"],
            )
        assert result.exit_code == 0
        assert "Created" in result.output

    def test_dashboard_new_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.dashboards.create.return_value = self._make_dashboard()
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_QUIET, "dashboard", "new", "--name", "Sales Dashboard"],
            )
        assert result.exit_code == 0
        assert result.output.strip() == "dash_1"

    def test_dashboard_new_missing_name(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "dashboard", "new"])
        assert result.exit_code != 0

    # -- update -------------------------------------------------------------

    def test_dashboard_update(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "dashboard", "update", "dash_1", "--name", "New Name"],
            )
        assert result.exit_code == 0
        assert "Updated" in result.output

    def test_dashboard_update_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "dashboard", "update", "dash_1", "--name", "New"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["updated"] is True

    # -- delete -------------------------------------------------------------

    def test_dashboard_delete(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, "dashboard", "delete", "dash_1"]
            )
        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_dashboard_delete_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "dashboard", "delete", "dash_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] is True

    # -- refresh ------------------------------------------------------------

    def test_dashboard_refresh(self) -> None:
        from querri.types.dashboard import DashboardRefreshResponse

        mock_client = MagicMock()
        mock_client.dashboards.refresh.return_value = DashboardRefreshResponse(
            id="dash_1",
            status="refreshing",
            project_count=3,
        )
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, "dashboard", "refresh", "dash_1"]
            )
        assert result.exit_code == 0
        assert (
            "refresh started" in result.output.lower()
            or "refreshing" in result.output.lower()
        )

    def test_dashboard_refresh_json(self) -> None:
        from querri.types.dashboard import DashboardRefreshResponse

        mock_client = MagicMock()
        mock_client.dashboards.refresh.return_value = DashboardRefreshResponse(
            id="dash_1",
            status="refreshing",
            project_count=3,
        )
        with patch("querri.cli.dashboards.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "dashboard", "refresh", "dash_1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "refreshing"

    def test_dashboard_refresh_missing_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "dashboard", "refresh"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------


class TestKeysCommands:
    """Tests for querri key list/get/new/delete."""

    def _make_key(self, **overrides):
        from querri.types.key import ApiKey

        defaults = dict(
            id="key_1",
            name="My Key",
            key_prefix="qk_abc",
            scopes=["data:read"],
            status="active",
            created_at="2025-01-01T00:00:00Z",
        )
        defaults.update(overrides)
        return ApiKey(**defaults)

    def _make_created_key(self, **overrides):
        from querri.types.key import ApiKeyCreated

        defaults = dict(
            id="key_1",
            name="My Key",
            key_prefix="qk_abc",
            scopes=["data:read"],
            status="active",
            secret="qk_test_secret_full_value",
            created_at="2025-01-01T00:00:00Z",
        )
        defaults.update(overrides)
        return ApiKeyCreated(**defaults)

    # -- list ---------------------------------------------------------------

    def test_key_list(self) -> None:
        mock_client = MagicMock()
        mock_client.keys.list.return_value = [self._make_key()]
        with patch("querri.cli.keys.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "key", "list"])
        assert result.exit_code == 0
        assert "My Key" in result.output

    def test_key_list_json(self) -> None:
        mock_client = MagicMock()
        mock_client.keys.list.return_value = [self._make_key()]
        with patch("querri.cli.keys.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "key", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "My Key"

    def test_key_list_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.keys.list.return_value = [self._make_key()]
        with patch("querri.cli.keys.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_QUIET, "key", "list"])
        assert result.exit_code == 0
        assert "key_1" in result.output

    # -- get ----------------------------------------------------------------

    def test_key_get(self) -> None:
        mock_client = MagicMock()
        mock_client.keys.get.return_value = self._make_key()
        with patch("querri.cli.keys.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "key", "get", "key_1"])
        assert result.exit_code == 0
        assert "My Key" in result.output

    def test_key_get_json(self) -> None:
        mock_client = MagicMock()
        mock_client.keys.get.return_value = self._make_key()
        with patch("querri.cli.keys.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "key", "get", "key_1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "key_1"

    def test_key_get_missing_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "key", "get"])
        assert result.exit_code != 0

    # -- new ----------------------------------------------------------------

    def test_key_new(self) -> None:
        mock_client = MagicMock()
        mock_client.keys.create.return_value = self._make_created_key()
        with patch("querri.cli.keys.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "key", "new", "--name", "My Key", "--scopes", "data:read"],
            )
        assert result.exit_code == 0
        assert "Created" in result.output

    def test_key_new_json(self) -> None:
        mock_client = MagicMock()
        mock_client.keys.create.return_value = self._make_created_key()
        with patch("querri.cli.keys.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    *_GLOBAL,
                    *_JSON,
                    "key",
                    "new",
                    "--name",
                    "My Key",
                    "--scopes",
                    "data:read",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "secret" in data

    def test_key_new_quiet_outputs_secret(self) -> None:
        mock_client = MagicMock()
        mock_client.keys.create.return_value = self._make_created_key()
        with patch("querri.cli.keys.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    *_GLOBAL,
                    *_QUIET,
                    "key",
                    "new",
                    "--name",
                    "My Key",
                    "--scopes",
                    "data:read",
                ],
            )
        assert result.exit_code == 0
        assert "qk_test_secret_full_value" in result.output

    def test_key_new_missing_name(self) -> None:
        result = runner.invoke(
            main_app, [*_GLOBAL, "key", "new", "--scopes", "data:read"]
        )
        assert result.exit_code != 0

    def test_key_new_missing_scopes(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "key", "new", "--name", "K"])
        assert result.exit_code != 0

    # -- delete -------------------------------------------------------------

    def test_key_delete(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.keys.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "key", "delete", "key_1"])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_key_delete_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.keys.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "key", "delete", "key_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] is True


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


class TestSourcesCommands:
    """Tests for querri source list/get/new/update/delete/describe/data/query."""

    # sources.list returns dicts (not Pydantic models) based on the CLI code
    _SOURCE_DICT = {
        "id": "src_1",
        "name": "Orders",
        "service": "csv",
        "connector_id": None,
    }

    def _make_source_model(self):
        from querri.types.data import Source

        return Source(id="src_1", name="Orders")

    # -- list ---------------------------------------------------------------

    def test_source_list(self) -> None:
        mock_client = MagicMock()
        mock_client.sources.list.return_value = [self._SOURCE_DICT]
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "source", "list"])
        assert result.exit_code == 0
        assert "Orders" in result.output

    def test_source_list_json(self) -> None:
        mock_client = MagicMock()
        mock_client.sources.list.return_value = [self._SOURCE_DICT]
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "source", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "Orders"

    def test_source_list_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.sources.list.return_value = [self._SOURCE_DICT]
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_QUIET, "source", "list"])
        assert result.exit_code == 0
        assert "src_1" in result.output

    # -- get ----------------------------------------------------------------

    def test_source_get(self) -> None:
        mock_client = MagicMock()
        mock_client.sources.get.return_value = self._SOURCE_DICT
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "source", "get", "src_1"])
        assert result.exit_code == 0
        assert "Orders" in result.output

    def test_source_get_json(self) -> None:
        mock_client = MagicMock()
        mock_client.sources.get.return_value = self._SOURCE_DICT
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "source", "get", "src_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "src_1"

    def test_source_get_missing_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "source", "get"])
        assert result.exit_code != 0

    # -- describe -----------------------------------------------------------

    def test_source_describe(self) -> None:
        src = {
            "id": "src_1",
            "name": "Orders",
            "row_count": 100,
            "description": "Order data",
            "summary": "Summary",
            "updated_at": "2025-01-01",
            "columns": ["id", "total"],
            "column_details": {},
            "column_types": {"id": "integer", "total": "float"},
        }
        mock_client = MagicMock()
        mock_client.sources.get.return_value = src
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "source", "describe", "src_1"])
        assert result.exit_code == 0
        assert "Orders" in result.output

    # -- data ---------------------------------------------------------------

    def test_source_data(self) -> None:
        from querri.types.data import DataPage

        page = DataPage(
            data=[{"id": 1, "total": 99.0}],
            total_rows=1,
            page=1,
            page_size=25,
            columns=["id", "total"],
        )
        mock_client = MagicMock()
        mock_client.sources.source_data.return_value = page
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "source", "data", "src_1"])
        assert result.exit_code == 0

    def test_source_data_json(self) -> None:
        from querri.types.data import DataPage

        page = DataPage(
            data=[{"id": 1, "total": 99.0}],
            total_rows=1,
            page=1,
            page_size=25,
            columns=["id", "total"],
        )
        mock_client = MagicMock()
        mock_client.sources.source_data.return_value = page
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "source", "data", "src_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "data" in data

    # -- query --------------------------------------------------------------

    def test_source_query(self) -> None:
        from querri.types.data import QueryResult

        qr = QueryResult(
            data=[{"id": 1, "total": 99}],
            total_rows=1,
            page=1,
            page_size=25,
        )
        mock_client = MagicMock()
        mock_client.sources.query.return_value = qr
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    *_GLOBAL,
                    "source",
                    "query",
                    "--source-id",
                    "src_1",
                    "--sql",
                    "SELECT 1",
                ],
            )
        assert result.exit_code == 0

    def test_source_query_missing_sql(self) -> None:
        result = runner.invoke(
            main_app,
            [*_GLOBAL, "source", "query", "--source-id", "src_1"],
        )
        assert result.exit_code != 0

    # -- new (piped JSON) ---------------------------------------------------

    def test_source_new_with_json_input(self) -> None:
        mock_client = MagicMock()
        mock_client.sources.create_data_source.return_value = self._make_source_model()
        rows = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "source", "new", "--name", "Test"],
                input=json.dumps(rows),
            )
        assert result.exit_code == 0
        mock_client.sources.create_data_source.assert_called_once_with(
            name="Test",
            rows=rows,
        )

    def test_source_new_invalid_json(self) -> None:
        result = runner.invoke(
            main_app,
            [*_GLOBAL, "source", "new", "--name", "Test"],
            input="not json",
        )
        assert result.exit_code != 0

    # -- update -------------------------------------------------------------

    def test_source_update(self) -> None:
        mock_client = MagicMock()
        mock_client.sources.update.return_value = {}
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "source", "update", "src_1", "--name", "Renamed"],
            )
        assert result.exit_code == 0
        assert "Updated" in result.output

    # -- delete -------------------------------------------------------------

    def test_source_delete(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "source", "delete", "src_1"])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_source_delete_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.sources.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "source", "delete", "src_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] is True


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


class TestViewsCommands:
    """Tests for querri view list/get/new/update/delete/run/preview."""

    _VIEW_DICT = {
        "id": "v_1",
        "uuid": "v_1",
        "name": "Revenue",
        "status": "ready",
        "description": "Monthly revenue",
    }

    # -- list ---------------------------------------------------------------

    def test_view_list(self) -> None:
        mock_client = MagicMock()
        mock_client.views.list.return_value = [self._VIEW_DICT]
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "view", "list"])
        assert result.exit_code == 0
        assert "Revenue" in result.output

    def test_view_list_json(self) -> None:
        mock_client = MagicMock()
        mock_client.views.list.return_value = [self._VIEW_DICT]
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "view", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "Revenue"

    def test_view_list_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.views.list.return_value = [self._VIEW_DICT]
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_QUIET, "view", "list"])
        assert result.exit_code == 0
        assert "v_1" in result.output

    # -- get ----------------------------------------------------------------

    def test_view_get(self) -> None:
        mock_client = MagicMock()
        mock_client.views.get.return_value = self._VIEW_DICT
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "view", "get", "v_1"])
        assert result.exit_code == 0

    def test_view_get_json(self) -> None:
        mock_client = MagicMock()
        mock_client.views.get.return_value = self._VIEW_DICT
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "view", "get", "v_1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "v_1"

    def test_view_get_missing_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "view", "get"])
        assert result.exit_code != 0

    # -- new (SQL path) -----------------------------------------------------

    def test_view_new_sql_path(self) -> None:
        mock_client = MagicMock()
        mock_client.views.create.return_value = {"id": "v_new", "uuid": "v_new"}
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    *_GLOBAL,
                    "view",
                    "new",
                    "--name",
                    "Revenue",
                    "--sql",
                    "SELECT sum(total) FROM orders",
                ],
            )
        assert result.exit_code == 0
        assert "Created" in result.output
        mock_client.views.create.assert_called_once_with(
            name="Revenue",
            sql_definition="SELECT sum(total) FROM orders",
            description=None,
        )

    def test_view_new_sql_json(self) -> None:
        mock_client = MagicMock()
        mock_client.views.create.return_value = {"id": "v_new", "uuid": "v_new"}
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "view", "new", "--sql", "SELECT 1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "id" in data

    def test_view_new_sql_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.views.create.return_value = {"id": "v_new", "uuid": "v_new"}
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_QUIET, "view", "new", "--sql", "SELECT 1"],
            )
        assert result.exit_code == 0
        assert "v_new" in result.output

    def test_view_new_no_sql_no_prompt_non_interactive(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "view", "new", "--name", "X"])
        assert result.exit_code != 0

    # -- update -------------------------------------------------------------

    def test_view_update(self) -> None:
        mock_client = MagicMock()
        mock_client.views.update.return_value = {"id": "v_1"}
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "view", "update", "v_1", "--sql", "SELECT 2"],
            )
        assert result.exit_code == 0
        assert "Updated" in result.output

    def test_view_update_json(self) -> None:
        mock_client = MagicMock()
        mock_client.views.update.return_value = {"id": "v_1"}
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "view", "update", "v_1", "--sql", "SELECT 2"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "v_1"

    # -- delete -------------------------------------------------------------

    def test_view_delete(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "view", "delete", "v_1"])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_view_delete_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "view", "delete", "v_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] is True

    # -- run ----------------------------------------------------------------

    def test_view_run_all(self) -> None:
        """run with no --view-ids materializes the full DAG."""
        mock_client = MagicMock()
        mock_client.views.run.return_value = {"status": "started"}
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "view", "run"])
        assert result.exit_code == 0
        mock_client.views.run.assert_called_once_with(view_uuids=None)

    def test_view_run_specific_ids(self) -> None:
        """run passes view_uuids= (not view_ids=) to the SDK."""
        mock_client = MagicMock()
        mock_client.views.run.return_value = {"status": "started"}
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "view", "run", "--view-ids", "v_1,v_2"],
            )
        assert result.exit_code == 0
        mock_client.views.run.assert_called_once_with(view_uuids=["v_1", "v_2"])

    def test_view_run_json(self) -> None:
        mock_client = MagicMock()
        mock_client.views.run.return_value = {"status": "started"}
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "view", "run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "started"

    # -- preview ------------------------------------------------------------

    def test_view_preview(self) -> None:
        mock_client = MagicMock()
        mock_client.views.preview.return_value = {
            "rows": [{"a": 1, "b": 2}],
            "total_rows": 1,
        }
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "view", "preview", "v_1"])
        assert result.exit_code == 0

    def test_view_preview_json(self) -> None:
        mock_client = MagicMock()
        mock_client.views.preview.return_value = {
            "rows": [{"a": 1}],
            "total_rows": 1,
        }
        with patch("querri.cli.views.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "view", "preview", "v_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "rows" in data

    def test_view_preview_missing_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "view", "preview"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


class TestFilesCommands:
    """Tests for querri file list/get/delete (upload skipped)."""

    def _make_file(self, **overrides):
        from querri.types.file import File

        defaults = dict(
            id="file_1",
            name="data.csv",
            size=1024,
            content_type="text/csv",
            created_at="2025-01-01T00:00:00Z",
        )
        defaults.update(overrides)
        return File(**defaults)

    # -- list ---------------------------------------------------------------

    def test_file_list(self) -> None:
        mock_client = MagicMock()
        mock_client.files.list.return_value = [self._make_file()]
        with patch("querri.cli.files.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "file", "list"])
        assert result.exit_code == 0
        assert "data.csv" in result.output

    def test_file_list_json(self) -> None:
        mock_client = MagicMock()
        mock_client.files.list.return_value = [self._make_file()]
        with patch("querri.cli.files.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "file", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "data.csv"

    def test_file_list_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.files.list.return_value = [self._make_file()]
        with patch("querri.cli.files.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_QUIET, "file", "list"])
        assert result.exit_code == 0
        assert "file_1" in result.output

    # -- get ----------------------------------------------------------------

    def test_file_get(self) -> None:
        mock_client = MagicMock()
        mock_client.files.get.return_value = self._make_file()
        with patch("querri.cli.files.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "file", "get", "file_1"])
        assert result.exit_code == 0
        assert "data.csv" in result.output

    def test_file_get_json(self) -> None:
        mock_client = MagicMock()
        mock_client.files.get.return_value = self._make_file()
        with patch("querri.cli.files.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "file", "get", "file_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "file_1"

    def test_file_get_missing_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "file", "get"])
        assert result.exit_code != 0

    # -- delete -------------------------------------------------------------

    def test_file_delete(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.files.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "file", "delete", "file_1"])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_file_delete_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.files.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "file", "delete", "file_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] is True

    def test_file_delete_missing_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "file", "delete"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


class TestPoliciesCommands:
    """Tests for querri policy list/get/new/update/delete/assign/remove."""

    def _make_policy(self, **overrides):
        from querri.types.policy import Policy

        defaults = dict(
            id="pol_1",
            name="Sales Team",
            description="RLS for sales",
            source_ids=["src_1"],
            user_count=3,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
        )
        defaults.update(overrides)
        return Policy(**defaults)

    # -- list ---------------------------------------------------------------

    def test_policy_list(self) -> None:
        mock_client = MagicMock()
        mock_client.policies.list.return_value = [self._make_policy()]
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "policy", "list"])
        assert result.exit_code == 0
        assert "Sales Team" in result.output

    def test_policy_list_json(self) -> None:
        mock_client = MagicMock()
        mock_client.policies.list.return_value = [self._make_policy()]
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "policy", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "Sales Team"

    def test_policy_list_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.policies.list.return_value = [self._make_policy()]
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_QUIET, "policy", "list"])
        assert result.exit_code == 0
        assert "pol_1" in result.output

    # -- get ----------------------------------------------------------------

    def test_policy_get(self) -> None:
        mock_client = MagicMock()
        mock_client.policies.get.return_value = self._make_policy()
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "policy", "get", "pol_1"])
        assert result.exit_code == 0
        assert "Sales Team" in result.output

    def test_policy_get_json(self) -> None:
        mock_client = MagicMock()
        mock_client.policies.get.return_value = self._make_policy()
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "policy", "get", "pol_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "pol_1"

    def test_policy_get_missing_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "policy", "get"])
        assert result.exit_code != 0

    # -- new ----------------------------------------------------------------

    def test_policy_new(self) -> None:
        mock_client = MagicMock()
        mock_client.policies.create.return_value = self._make_policy()
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    *_GLOBAL,
                    "policy",
                    "new",
                    "--name",
                    "Sales Team",
                    "--source-ids",
                    "src_1",
                ],
            )
        assert result.exit_code == 0
        assert "Created" in result.output

    def test_policy_new_json(self) -> None:
        mock_client = MagicMock()
        mock_client.policies.create.return_value = self._make_policy()
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "policy", "new", "--name", "Sales Team"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "Sales Team"

    def test_policy_new_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.policies.create.return_value = self._make_policy()
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_QUIET, "policy", "new", "--name", "Sales Team"],
            )
        assert result.exit_code == 0
        assert result.output.strip() == "pol_1"

    def test_policy_new_missing_name(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "policy", "new"])
        assert result.exit_code != 0

    # -- update -------------------------------------------------------------

    def test_policy_update(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "policy", "update", "pol_1", "--name", "Updated"],
            )
        assert result.exit_code == 0
        assert "Updated" in result.output

    def test_policy_update_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "policy", "update", "pol_1", "--name", "X"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["updated"] is True

    def test_policy_update_missing_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "policy", "update"])
        assert result.exit_code != 0

    # -- delete -------------------------------------------------------------

    def test_policy_delete(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "policy", "delete", "pol_1"])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_policy_delete_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "policy", "delete", "pol_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] is True

    # -- assign -------------------------------------------------------------

    def test_policy_assign(self) -> None:
        mock_client = MagicMock()
        mock_client.policies.assign_users.return_value = {"assigned": True}
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "policy", "assign", "pol_1", "--user-ids", "usr_1,usr_2"],
            )
        assert result.exit_code == 0
        assert "Assigned" in result.output
        mock_client.policies.assign_users.assert_called_once_with(
            "pol_1",
            user_ids=["usr_1", "usr_2"],
        )

    def test_policy_assign_json(self) -> None:
        mock_client = MagicMock()
        mock_client.policies.assign_users.return_value = {"assigned": True}
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "policy", "assign", "pol_1", "--user-ids", "usr_1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["assigned"] is True

    def test_policy_assign_missing_user_ids(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "policy", "assign", "pol_1"])
        assert result.exit_code != 0

    # -- remove -------------------------------------------------------------

    def test_policy_remove(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, "policy", "remove", "pol_1", "usr_1"]
            )
        assert result.exit_code == 0
        assert "Removed" in result.output
        mock_client.policies.remove_user.assert_called_once_with("pol_1", "usr_1")

    def test_policy_remove_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.policies.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "policy", "remove", "pol_1", "usr_1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["removed"] is True

    def test_policy_remove_missing_user_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "policy", "remove", "pol_1"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Embed (Sessions)
# ---------------------------------------------------------------------------


class TestEmbedCommands:
    """Tests for querri session list/new/revoke."""

    def _make_session(self, **overrides):
        from querri.types.embed import EmbedSession

        defaults = dict(session_token="es_abc123", expires_in=3600, user_id="usr_1")
        defaults.update(overrides)
        return EmbedSession(**defaults)

    def _make_session_list(self):
        from querri.types.embed import EmbedSessionList, EmbedSessionListItem

        return EmbedSessionList(
            data=[
                EmbedSessionListItem(
                    session_token="es_abc123",
                    user_id="usr_1",
                    origin="https://example.com",
                    created_at="2025-01-01T00:00:00Z",
                    auth_method="api_key",
                ),
            ]
        )

    # -- list ---------------------------------------------------------------

    def test_session_list(self) -> None:
        mock_client = MagicMock()
        mock_client.embed.list_sessions.return_value = self._make_session_list()
        with patch("querri.cli.embed.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "session", "list"])
        assert result.exit_code == 0
        assert "es_abc123" in result.output

    def test_session_list_json(self) -> None:
        mock_client = MagicMock()
        mock_client.embed.list_sessions.return_value = self._make_session_list()
        with patch("querri.cli.embed.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "session", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "data" in data

    # -- new ----------------------------------------------------------------

    def test_session_new(self) -> None:
        mock_client = MagicMock()
        mock_client.embed.create_session.return_value = self._make_session()
        with patch("querri.cli.embed.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "session", "new", "--user-id", "usr_1"],
            )
        assert result.exit_code == 0
        assert "Created" in result.output or "es_abc123" in result.output

    def test_session_new_json(self) -> None:
        mock_client = MagicMock()
        mock_client.embed.create_session.return_value = self._make_session()
        with patch("querri.cli.embed.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "session", "new", "--user-id", "usr_1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["session_token"] == "es_abc123"

    def test_session_new_quiet_outputs_token(self) -> None:
        mock_client = MagicMock()
        mock_client.embed.create_session.return_value = self._make_session()
        with patch("querri.cli.embed.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_QUIET, "session", "new", "--user-id", "usr_1"],
            )
        assert result.exit_code == 0
        assert "es_abc123" in result.output

    def test_session_new_missing_user_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "session", "new"])
        assert result.exit_code != 0

    # -- revoke -------------------------------------------------------------

    def test_session_revoke_by_id(self) -> None:
        from querri.types.embed import EmbedSessionRevokeResponse

        mock_client = MagicMock()
        mock_client.embed.revoke_session.return_value = EmbedSessionRevokeResponse(
            id="ses_1",
            revoked=True,
        )
        with patch("querri.cli.embed.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "session", "revoke", "--session-id", "ses_1"],
            )
        assert result.exit_code == 0
        assert "Revoked" in result.output

    def test_session_revoke_by_token(self) -> None:
        from querri.types.embed import EmbedSessionRevokeResponse

        mock_client = MagicMock()
        mock_client.embed.revoke_session.return_value = EmbedSessionRevokeResponse(
            id="ses_1",
            revoked=True,
        )
        with patch("querri.cli.embed.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "session", "revoke", "--token", "es_abc123"],
            )
        assert result.exit_code == 0
        assert "Revoked" in result.output

    def test_session_revoke_json(self) -> None:
        from querri.types.embed import EmbedSessionRevokeResponse

        mock_client = MagicMock()
        mock_client.embed.revoke_session.return_value = EmbedSessionRevokeResponse(
            id="ses_1",
            revoked=True,
        )
        with patch("querri.cli.embed.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "session", "revoke", "--session-id", "ses_1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["revoked"] is True

    def test_session_revoke_missing_both(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "session", "revoke"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


class TestUsageCommands:
    """Tests for querri usage org/user."""

    def _make_org_usage(self):
        from querri.types.usage import OrgUsageReport

        return OrgUsageReport(
            period="current_month",
            period_start="2025-01-01T00:00:00Z",
            period_end="2025-01-31T23:59:59Z",
            total_ai_messages=150,
            active_user_count=5,
            project_count=10,
        )

    def _make_user_usage(self):
        from querri.types.usage import UserUsageReport

        return UserUsageReport(
            user_id="usr_1",
            period="current_month",
            period_start="2025-01-01T00:00:00Z",
            period_end="2025-01-31T23:59:59Z",
            ai_messages=42,
        )

    # -- org ----------------------------------------------------------------

    def test_usage_org(self) -> None:
        mock_client = MagicMock()
        mock_client.usage.org_usage.return_value = self._make_org_usage()
        with patch("querri.cli.usage.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "usage", "org"])
        assert result.exit_code == 0
        assert "150" in result.output or "current_month" in result.output

    def test_usage_org_json(self) -> None:
        mock_client = MagicMock()
        mock_client.usage.org_usage.return_value = self._make_org_usage()
        with patch("querri.cli.usage.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "usage", "org"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_ai_messages"] == 150

    # -- user ---------------------------------------------------------------

    def test_usage_user(self) -> None:
        mock_client = MagicMock()
        mock_client.usage.user_usage.return_value = self._make_user_usage()
        with patch("querri.cli.usage.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "usage", "user", "usr_1"])
        assert result.exit_code == 0
        assert "42" in result.output

    def test_usage_user_json(self) -> None:
        mock_client = MagicMock()
        mock_client.usage.user_usage.return_value = self._make_user_usage()
        with patch("querri.cli.usage.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "usage", "user", "usr_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ai_messages"] == 42

    def test_usage_user_missing_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "usage", "user"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class TestAuditCommands:
    """Tests for querri audit list."""

    def _make_event(self, **overrides):
        from querri.types.audit import AuditEvent

        defaults = dict(
            id="evt_1",
            actor_id="usr_1",
            action="create",
            target_type="project",
            target_id="proj_1",
            timestamp="2025-01-01T00:00:00Z",
        )
        defaults.update(overrides)
        return AuditEvent(**defaults)

    def test_audit_list(self) -> None:
        mock_client = MagicMock()
        mock_client.audit.list.return_value = [self._make_event()]
        with patch("querri.cli.audit.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "audit", "list"])
        assert result.exit_code == 0
        assert "create" in result.output

    def test_audit_list_json(self) -> None:
        mock_client = MagicMock()
        mock_client.audit.list.return_value = [self._make_event()]
        with patch("querri.cli.audit.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, *_JSON, "audit", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["action"] == "create"

    def test_audit_list_with_filters(self) -> None:
        mock_client = MagicMock()
        mock_client.audit.list.return_value = [self._make_event()]
        with patch("querri.cli.audit.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    *_GLOBAL,
                    "audit",
                    "list",
                    "--actor-id",
                    "usr_1",
                    "--action",
                    "create",
                    "--limit",
                    "10",
                ],
            )
        assert result.exit_code == 0
        mock_client.audit.list.assert_called_once_with(
            actor_id="usr_1",
            target_id=None,
            action="create",
            start_date=None,
            end_date=None,
            limit=10,
            after=None,
        )


# ---------------------------------------------------------------------------
# Chats — with active project/chat resolution
# ---------------------------------------------------------------------------


class TestChatsCommands:
    """Tests for querri chat list/get/new/delete/cancel.

    These tests exercise the _resolve_project and _resolve_chat helpers
    that fall back to active project/chat from the profile.
    """

    def _make_chat(self, **overrides):
        from querri.types.chat import Chat

        defaults = dict(
            id="chat_1",
            project_id="proj_1",
            name="Analysis",
            created_at="2025-01-01T00:00:00Z",
        )
        defaults.update(overrides)
        return Chat(**defaults)

    def _mock_profile(self, active_project_id=None, active_chat_id=None):
        """Create a mock TokenProfile with optional active project/chat."""
        profile = MagicMock()
        profile.active_project_id = active_project_id
        profile.active_chat_id = active_chat_id
        return profile

    # -- list ---------------------------------------------------------------

    def test_chat_list_explicit_project(self) -> None:
        mock_client = MagicMock()
        mock_client.projects.chats.list.return_value = [self._make_chat()]
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(main_app, [*_GLOBAL, "chat", "list", "proj_1"])
        assert result.exit_code == 0
        assert "Analysis" in result.output

    def test_chat_list_uses_active_project(self) -> None:
        """Falls back to active project from profile when no arg given."""
        mock_client = MagicMock()
        mock_client.projects.chats.list.return_value = [self._make_chat()]
        with (
            patch("querri.cli.chats.get_client", return_value=mock_client),
            patch("querri.cli.chats.resolve_project_id", return_value="proj_active"),
        ):
            result = runner.invoke(main_app, [*_GLOBAL, "chat", "list"])
        assert result.exit_code == 0
        mock_client.projects.chats.list.assert_called_once_with("proj_active", limit=25)

    def test_chat_list_explicit_overrides_active_project(self) -> None:
        """Explicit arg overrides active project."""
        mock_client = MagicMock()
        mock_client.projects.chats.list.return_value = [self._make_chat()]
        profile = self._mock_profile(active_project_id="proj_active")
        with (
            patch("querri.cli.chats.get_client", return_value=mock_client),
            patch("querri.cli.chats._get_profile", return_value=profile),
        ):
            result = runner.invoke(
                main_app, [*_GLOBAL, "chat", "list", "proj_explicit"]
            )
        assert result.exit_code == 0
        mock_client.projects.chats.list.assert_called_once_with(
            "proj_explicit", limit=25
        )

    def test_chat_list_no_active_project_errors(self) -> None:
        """Errors with helpful message when no active project and no arg."""
        profile = self._mock_profile(active_project_id=None)
        with (
            patch("querri.cli.chats._get_profile", return_value=profile),
            patch("querri.cli.chats.resolve_project_id", side_effect=SystemExit(1)),
        ):
            result = runner.invoke(main_app, [*_GLOBAL, "chat", "list"])
        assert result.exit_code != 0
        assert (
            "active project" in result.output.lower()
            or "project" in result.output.lower()
        )

    def test_chat_list_json(self) -> None:
        mock_client = MagicMock()
        mock_client.projects.chats.list.return_value = [self._make_chat()]
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_JSON, "chat", "list", "proj_1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_chat_list_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.projects.chats.list.return_value = [self._make_chat()]
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, *_QUIET, "chat", "list", "proj_1"]
            )
        assert result.exit_code == 0
        assert "chat_1" in result.output

    # -- get ----------------------------------------------------------------

    def test_chat_get_explicit(self) -> None:
        mock_client = MagicMock()
        mock_client.projects.chats.get.return_value = self._make_chat()
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app, [*_GLOBAL, "chat", "get", "proj_1", "chat_1"]
            )
        assert result.exit_code == 0
        mock_client.projects.chats.get.assert_called_once_with("proj_1", "chat_1")

    def test_chat_get_uses_active_chat(self) -> None:
        """Falls back to active chat from profile when no chat arg given."""
        mock_client = MagicMock()
        mock_client.projects.chats.get.return_value = self._make_chat()
        profile = self._mock_profile(
            active_project_id="proj_1", active_chat_id="chat_active"
        )
        with (
            patch("querri.cli.chats.get_client", return_value=mock_client),
            patch("querri.cli.chats.resolve_project_id", return_value="proj_1"),
            patch("querri.cli.chats._get_profile", return_value=profile),
        ):
            result = runner.invoke(main_app, [*_GLOBAL, "chat", "get"])
        assert result.exit_code == 0
        mock_client.projects.chats.get.assert_called_once_with("proj_1", "chat_active")

    def test_chat_get_json(self) -> None:
        mock_client = MagicMock()
        mock_client.projects.chats.get.return_value = self._make_chat()
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "chat", "get", "proj_1", "chat_1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "chat_1"

    def test_chat_get_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.projects.chats.get.return_value = self._make_chat()
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_QUIET, "chat", "get", "proj_1", "chat_1"],
            )
        assert result.exit_code == 0
        assert result.output.strip() == "chat_1"

    # -- new ----------------------------------------------------------------

    def test_chat_new(self) -> None:
        mock_client = MagicMock()
        mock_client.projects.chats.create.return_value = self._make_chat()
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "chat", "new", "proj_1", "--name", "Analysis"],
            )
        assert result.exit_code == 0
        assert "Created" in result.output

    def test_chat_new_json(self) -> None:
        mock_client = MagicMock()
        mock_client.projects.chats.create.return_value = self._make_chat()
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "chat", "new", "proj_1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "chat_1"

    def test_chat_new_quiet(self) -> None:
        mock_client = MagicMock()
        mock_client.projects.chats.create.return_value = self._make_chat()
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_QUIET, "chat", "new", "proj_1"],
            )
        assert result.exit_code == 0
        assert result.output.strip() == "chat_1"

    # -- delete -------------------------------------------------------------

    def test_chat_delete(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "chat", "delete", "proj_1", "chat_1"],
            )
        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        mock_client.projects.chats.delete.assert_called_once_with("proj_1", "chat_1")

    def test_chat_delete_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "chat", "delete", "proj_1", "chat_1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] is True

    # -- cancel -------------------------------------------------------------

    def test_chat_cancel(self) -> None:
        mock_client = MagicMock()
        mock_client.projects.chats.cancel.return_value = {"cancelled": True}
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "chat", "cancel", "proj_1", "chat_1"],
            )
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()
        mock_client.projects.chats.cancel.assert_called_once_with("proj_1", "chat_1")

    def test_chat_cancel_json(self) -> None:
        mock_client = MagicMock()
        mock_client.projects.chats.cancel.return_value = {"cancelled": True}
        with patch("querri.cli.chats.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "chat", "cancel", "proj_1", "chat_1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["cancelled"] is True

    def test_chat_cancel_uses_active_project_and_chat(self) -> None:
        """cancel falls back to active project + chat from profile."""
        mock_client = MagicMock()
        mock_client.projects.chats.cancel.return_value = {"cancelled": True}
        profile = self._mock_profile(
            active_project_id="proj_a", active_chat_id="chat_a"
        )
        with (
            patch("querri.cli.chats.get_client", return_value=mock_client),
            patch("querri.cli.chats.resolve_project_id", return_value="proj_a"),
            patch("querri.cli.chats._get_profile", return_value=profile),
        ):
            result = runner.invoke(main_app, [*_GLOBAL, "chat", "cancel"])
        assert result.exit_code == 0
        mock_client.projects.chats.cancel.assert_called_once_with("proj_a", "chat_a")


# ---------------------------------------------------------------------------
# Sharing — project sub-commands
# ---------------------------------------------------------------------------


class TestSharingCommands:
    """Tests for querri share project add/list/remove."""

    def _make_share(self, **overrides):
        from querri.types.sharing import ShareEntry

        defaults = dict(user_id="usr_1", permission="view")
        defaults.update(overrides)
        return ShareEntry(**defaults)

    # -- share project add --------------------------------------------------

    def test_share_project_add(self) -> None:
        mock_client = MagicMock()
        mock_client.sharing.share_project.return_value = {"shared": True}
        with patch("querri.cli.sharing.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "share", "project", "add", "proj_1", "--user-id", "usr_1"],
            )
        assert result.exit_code == 0
        assert "Shared" in result.output
        mock_client.sharing.share_project.assert_called_once_with(
            "proj_1",
            user_id="usr_1",
            permission="view",
        )

    def test_share_project_add_edit_permission(self) -> None:
        mock_client = MagicMock()
        mock_client.sharing.share_project.return_value = {"shared": True}
        with patch("querri.cli.sharing.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    *_GLOBAL,
                    "share",
                    "project",
                    "add",
                    "proj_1",
                    "--user-id",
                    "usr_1",
                    "--permission",
                    "edit",
                ],
            )
        assert result.exit_code == 0
        mock_client.sharing.share_project.assert_called_once_with(
            "proj_1",
            user_id="usr_1",
            permission="edit",
        )

    def test_share_project_add_json(self) -> None:
        mock_client = MagicMock()
        mock_client.sharing.share_project.return_value = {"shared": True}
        with patch("querri.cli.sharing.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    *_GLOBAL,
                    *_JSON,
                    "share",
                    "project",
                    "add",
                    "proj_1",
                    "--user-id",
                    "usr_1",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["shared"] is True

    def test_share_project_add_missing_user_id(self) -> None:
        result = runner.invoke(
            main_app,
            [*_GLOBAL, "share", "project", "add", "proj_1"],
        )
        assert result.exit_code != 0

    def test_share_project_add_missing_project_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "share", "project", "add"])
        assert result.exit_code != 0

    # -- share project list -------------------------------------------------

    def test_share_project_list(self) -> None:
        mock_client = MagicMock()
        mock_client.sharing.list_project_shares.return_value = [self._make_share()]
        with patch("querri.cli.sharing.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "share", "project", "list", "proj_1"],
            )
        assert result.exit_code == 0
        assert "usr_1" in result.output

    def test_share_project_list_json(self) -> None:
        mock_client = MagicMock()
        mock_client.sharing.list_project_shares.return_value = [self._make_share()]
        with patch("querri.cli.sharing.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "share", "project", "list", "proj_1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["user_id"] == "usr_1"

    def test_share_project_list_missing_project_id(self) -> None:
        result = runner.invoke(main_app, [*_GLOBAL, "share", "project", "list"])
        assert result.exit_code != 0

    # -- share project remove -----------------------------------------------

    def test_share_project_remove(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.sharing.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, "share", "project", "remove", "proj_1", "usr_1"],
            )
        assert result.exit_code == 0
        assert "Revoked" in result.output
        mock_client.sharing.revoke_project_share.assert_called_once_with(
            "proj_1", "usr_1"
        )

    def test_share_project_remove_json(self) -> None:
        mock_client = MagicMock()
        with patch("querri.cli.sharing.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [*_GLOBAL, *_JSON, "share", "project", "remove", "proj_1", "usr_1"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["revoked"] is True

    def test_share_project_remove_missing_user_id(self) -> None:
        result = runner.invoke(
            main_app,
            [*_GLOBAL, "share", "project", "remove", "proj_1"],
        )
        assert result.exit_code != 0
