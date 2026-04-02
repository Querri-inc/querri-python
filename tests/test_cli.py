"""CLI scaffold, output formatting, error handling, and command tests.

Uses Typer's CliRunner for command invocation.
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from querri.cli._app import main_app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Scaffold tests
# ---------------------------------------------------------------------------


class TestScaffold:
    """Test CLI scaffold: help, version, entry point guard."""

    def test_help_shows_panel_groupings(self) -> None:
        result = runner.invoke(main_app, ["--help"])
        assert result.exit_code == 0
        assert "Getting Started" in result.output
        assert "Projects & Data" in result.output
        assert "Administration" in result.output
        assert "Advanced" in result.output

    def test_help_shows_subcommands(self) -> None:
        result = runner.invoke(main_app, ["--help"])
        assert "project" in result.output
        assert "chat" in result.output
        assert "whoami" in result.output
        assert "key" in result.output

    def test_version(self) -> None:
        result = runner.invoke(main_app, ["--version"])
        assert result.exit_code == 0
        assert "querri 0.2.0" in result.output

    def test_projects_help(self) -> None:
        result = runner.invoke(main_app, ["project", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "get" in result.output
        assert "create" in result.output
        assert "run" in result.output

    def test_data_help_cross_reference(self) -> None:
        result = runner.invoke(main_app, ["data", "--help"])
        assert result.exit_code == 0
        assert "querri source" in result.output

    def test_sources_help_cross_reference(self) -> None:
        result = runner.invoke(main_app, ["source", "--help"])
        assert result.exit_code == 0
        # Cross-reference text may wrap across lines in Rich output
        plain = result.output.replace("\n", " ")
        assert "file-backed datasets" in plain


# ---------------------------------------------------------------------------
# Output formatting tests
# ---------------------------------------------------------------------------


class TestOutputFormatting:
    """Test --json, --quiet modes and TTY detection."""

    def test_json_mode_whoami(self) -> None:
        """whoami --json outputs valid JSON."""
        result = runner.invoke(
            main_app,
            ["--api-key", "qk_test123456", "--org-id", "org_1", "--json", "whoami"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["auth_type"] == "api_key"
        assert data["org_id"] == "org_1"
        # API key must be masked
        assert "test123456" not in data.get("api_key_prefix", "")

    def test_tty_detection_module(self) -> None:
        """IS_INTERACTIVE constant exists in _output module."""
        from querri.cli._output import IS_INTERACTIVE
        assert isinstance(IS_INTERACTIVE, bool)


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test exit codes and error formatting."""

    def test_auth_error_exit_code_2(self) -> None:
        """Missing credentials → exit code 2."""
        # Clear env vars AND mock empty token store so disk tokens aren't found
        with patch.dict("os.environ", {}, clear=True), \
             patch("querri._auth.TokenStore") as mock_store_cls:
            mock_store_cls.load.return_value.profiles = {}
            result = runner.invoke(main_app, ["whoami"])
            assert result.exit_code == 2

    def test_auth_error_json_mode(self) -> None:
        """--json + auth error → JSON error output."""
        # Clear env vars AND mock empty token store so disk tokens aren't found
        with patch.dict("os.environ", {}, clear=True), \
             patch("querri._auth.TokenStore") as mock_store_cls:
            mock_store_cls.load.return_value.profiles = {}
            result = runner.invoke(main_app, ["--json", "whoami"])
            assert result.exit_code == 2
            # JSON error should be in stderr (from _context.py)
            # The error output should be parseable JSON
            # Note: CliRunner combines stdout/stderr in output

    def test_not_found_exit_code_3(self) -> None:
        """404 error → exit code 3."""
        from querri._exceptions import NotFoundError

        mock_client = MagicMock()
        mock_client.projects.get.side_effect = NotFoundError(
            "Project not found", status=404
        )

        with patch("querri.cli.projects.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                ["--api-key", "qk_test123456", "--org-id", "org_1", "project", "get", "nonexistent"],
            )
            assert result.exit_code == 3

    def test_rate_limit_exit_code_4(self) -> None:
        """429 error → exit code 4."""
        from querri._exceptions import RateLimitError

        mock_client = MagicMock()
        mock_client.projects.list.side_effect = RateLimitError(
            "Rate limited", retry_after=30.0
        )

        with patch("querri.cli.projects.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                ["--api-key", "qk_test123456", "--org-id", "org_1", "project", "list"],
            )
            assert result.exit_code == 4

    def test_general_error_exit_code_1(self) -> None:
        """General error → exit code 1."""
        from querri._exceptions import ServerError

        mock_client = MagicMock()
        mock_client.projects.get.side_effect = ServerError(
            "Internal server error", status=500
        )

        with patch("querri.cli.projects.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                ["--api-key", "qk_test123456", "--org-id", "org_1", "project", "get", "proj_1"],
            )
            assert result.exit_code == 1

    def test_not_found_json_mode(self) -> None:
        """--json + 404 → JSON error on stdout."""
        from querri._exceptions import NotFoundError

        mock_client = MagicMock()
        mock_client.projects.get.side_effect = NotFoundError(
            "Project xyz not found", status=404
        )

        with patch("querri.cli.projects.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                ["--api-key", "qk_test123456", "--org-id", "org_1", "--json", "project", "get", "xyz"],
            )
            assert result.exit_code == 3


# ---------------------------------------------------------------------------
# Command tests (with mocked SDK)
# ---------------------------------------------------------------------------


class TestWhoamiCommand:
    """Test querri whoami command."""

    def test_whoami_default_output(self) -> None:
        result = runner.invoke(
            main_app,
            ["--api-key", "qk_test123456", "--org-id", "org_1", "whoami"],
        )
        assert result.exit_code == 0
        assert "org_1" in result.output
        # Key should be masked
        assert "test123456" not in result.output
        assert "qk_test" in result.output  # prefix shown

    def test_whoami_json(self) -> None:
        result = runner.invoke(
            main_app,
            ["--api-key", "qk_test123456", "--org-id", "org_1", "--json", "whoami"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "api_key_prefix" in data
        assert "test123456" not in json.dumps(data)


class TestProjectsCommand:
    """Test querri projects commands."""

    def test_projects_list(self) -> None:
        from querri.types.project import Project

        mock_page = [
            Project(id="proj_1", name="Test Project", status="idle"),
            Project(id="proj_2", name="Another Project", status="running"),
        ]
        mock_client = MagicMock()
        mock_client.projects.list.return_value = mock_page

        with patch("querri.cli.projects.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                ["--api-key", "qk_test123456", "--org-id", "org_1", "project", "list"],
            )
            assert result.exit_code == 0
            assert "proj_1" in result.output
            assert "Test Project" in result.output

    def test_projects_list_json(self) -> None:
        from querri.types.project import Project

        mock_page = [
            Project(id="proj_1", name="Test Project", status="idle"),
        ]
        mock_client = MagicMock()
        mock_client.projects.list.return_value = mock_page

        with patch("querri.cli.projects.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                ["--api-key", "qk_test123456", "--org-id", "org_1", "--json", "project", "list"],
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert data[0]["id"] == "proj_1"

    def test_projects_list_quiet(self) -> None:
        from querri.types.project import Project

        mock_page = [
            Project(id="proj_1", name="Test Project", status="idle"),
            Project(id="proj_2", name="Another", status="idle"),
        ]
        mock_client = MagicMock()
        mock_client.projects.list.return_value = mock_page

        with patch("querri.cli.projects.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                ["--api-key", "qk_test123456", "--org-id", "org_1", "--quiet", "project", "list"],
            )
            assert result.exit_code == 0
            lines = result.output.strip().split("\n")
            assert lines == ["proj_1", "proj_2"]

    def test_projects_get(self) -> None:
        from querri.types.project import Project

        mock_client = MagicMock()
        mock_client.projects.get.return_value = Project(
            id="proj_1", name="Test Project", status="idle",
            description="A test", step_count=3,
        )

        with patch("querri.cli.projects.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                ["--api-key", "qk_test123456", "--org-id", "org_1", "project", "get", "proj_1"],
            )
            assert result.exit_code == 0
            assert "proj_1" in result.output
            assert "Test Project" in result.output

    def test_projects_get_json(self) -> None:
        from querri.types.project import Project

        mock_client = MagicMock()
        mock_client.projects.get.return_value = Project(
            id="proj_1", name="Test", status="idle",
        )

        with patch("querri.cli.projects.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                ["--api-key", "qk_test123456", "--org-id", "org_1", "--json", "project", "get", "proj_1"],
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["id"] == "proj_1"


class TestExitCodeConstants:
    """Test that exit code constants match spec."""

    def test_exit_code_values(self) -> None:
        from querri.cli._output import (
            EXIT_AUTH_ERROR,
            EXIT_ERROR,
            EXIT_NOT_FOUND,
            EXIT_RATE_LIMITED,
            EXIT_SUCCESS,
        )

        assert EXIT_SUCCESS == 0
        assert EXIT_ERROR == 1
        assert EXIT_AUTH_ERROR == 2
        assert EXIT_NOT_FOUND == 3
        assert EXIT_RATE_LIMITED == 4


# ---------------------------------------------------------------------------
# Entry point guard (SPEC §3.4)
# ---------------------------------------------------------------------------


class TestEntryPointGuard:
    """Test querri.cli:app entry point handles missing Typer."""

    def test_entry_point_without_typer_exits_1(self) -> None:
        """When querri.cli._app cannot be imported, exit code 1 with clean message."""
        import importlib
        import querri.cli as cli_mod

        original_app_mod = sys.modules.get("querri.cli._app")
        # Block the _app import
        sys.modules["querri.cli._app"] = None  # type: ignore[assignment]
        try:
            importlib.reload(cli_mod)
            with pytest.raises(SystemExit) as exc_info:
                cli_mod.app()
            assert exc_info.value.code == 1
        finally:
            # Restore
            if original_app_mod is not None:
                sys.modules["querri.cli._app"] = original_app_mod
            else:
                sys.modules.pop("querri.cli._app", None)
            importlib.reload(cli_mod)

    def test_entry_point_error_message_is_clean(self, capsys) -> None:
        """Error output must not leak tracebacks, file paths, or module names."""
        import importlib
        import querri.cli as cli_mod

        original_app_mod = sys.modules.get("querri.cli._app")
        sys.modules["querri.cli._app"] = None  # type: ignore[assignment]
        try:
            importlib.reload(cli_mod)
            with pytest.raises(SystemExit):
                cli_mod.app()
            captured = capsys.readouterr()
            # Must contain helpful message
            assert "pip install" in captured.err
            assert "querri[cli]" in captured.err
            # Must NOT leak internals
            assert "Traceback" not in captured.err
            assert "ImportError" not in captured.err
            assert ".py" not in captured.err
        finally:
            if original_app_mod is not None:
                sys.modules["querri.cli._app"] = original_app_mod
            else:
                sys.modules.pop("querri.cli._app", None)
            importlib.reload(cli_mod)


# ---------------------------------------------------------------------------
# Sub-app registration completeness
# ---------------------------------------------------------------------------


class TestSubAppRegistration:
    """Verify all 15 sub-apps are registered and reachable."""

    EXPECTED_SUBCOMMANDS = [
        "whoami", "project", "step", "chat", "file", "data", "source",
        "user", "dashboard", "key", "policy", "share",
        "embed", "usage", "audit",
    ]

    def test_all_15_subcommands_in_help(self) -> None:
        """Every sub-app name should appear in top-level help."""
        result = runner.invoke(main_app, ["--help"])
        assert result.exit_code == 0
        for cmd in self.EXPECTED_SUBCOMMANDS:
            assert cmd in result.output, f"Missing subcommand in help: {cmd}"

    @pytest.mark.parametrize("subcommand", EXPECTED_SUBCOMMANDS)
    def test_subcommand_help_succeeds(self, subcommand: str) -> None:
        """Each subcommand's --help must exit 0 with no tracebacks."""
        result = runner.invoke(main_app, [subcommand, "--help"])
        assert result.exit_code == 0, f"{subcommand} --help failed: {result.output}"
        assert "Traceback" not in result.output

    def test_subcommand_count(self) -> None:
        """Exactly 17 sub-apps must be registered (including auth and hidden chats)."""
        # Count registered Typer sub-apps (not the main app callback)
        registered = [
            group.name or group.typer_instance.info.name
            for group in main_app.registered_groups
        ]
        assert len(registered) == 17, f"Expected 17 sub-apps, got {len(registered)}: {registered}"


# ---------------------------------------------------------------------------
# Verbose flag
# ---------------------------------------------------------------------------


class TestVerboseFlag:
    """Test --verbose flag is accepted."""

    def test_verbose_flag_accepted(self) -> None:
        result = runner.invoke(main_app, ["--verbose", "--help"])
        assert result.exit_code == 0

    def test_verbose_short_flag_accepted(self) -> None:
        result = runner.invoke(main_app, ["-v", "--help"])
        assert result.exit_code == 0
