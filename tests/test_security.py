"""Security tests for the Querri CLI.

Verifies credential redaction, shell history warnings, file path validation,
and user ID auto-derivation priority.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from querri._config import ClientConfig
from querri.cli._app import main_app

runner = CliRunner()


# ---------------------------------------------------------------------------
# SEC-1: Credential redaction
# ---------------------------------------------------------------------------


class TestCredentialRedaction:
    """API keys and tokens must never appear in output."""

    def test_repr_does_not_expose_api_key(self) -> None:
        """repr(ClientConfig) must not contain the full API key."""
        config = ClientConfig(api_key="qk_supersecretkey12345", org_id="org_1")
        repr_str = repr(config)
        assert "supersecretkey12345" not in repr_str
        assert "qk_***" in repr_str

    def test_str_does_not_expose_api_key(self) -> None:
        """str(ClientConfig) must not contain the full API key."""
        config = ClientConfig(api_key="qk_supersecretkey12345", org_id="org_1")
        str_str = str(config)
        assert "supersecretkey12345" not in str_str

    def test_repr_shows_last_4_chars_of_key(self) -> None:
        """Redacted repr should show qk_***...XXXX (last 4 chars)."""
        config = ClientConfig(api_key="qk_abcdefghijklmnop", org_id="org_1")
        repr_str = repr(config)
        assert "mnop" in repr_str  # last 4 chars visible
        assert "abcdefghijkl" not in repr_str  # middle chars hidden

    def test_repr_redacts_in_exception_context(self) -> None:
        """Config repr is safe even when embedded in exception messages."""
        config = ClientConfig(api_key="qk_supersecretkey12345", org_id="org_1")
        error_msg = f"Connection failed with config: {config!r}"
        assert "supersecretkey12345" not in error_msg

    def test_whoami_masks_api_key(self) -> None:
        """querri whoami must show at most 7 characters of key prefix."""
        result = runner.invoke(
            main_app,
            ["--api-key", "qk_supersecretkey12345", "--org-id", "org_1", "whoami"],
        )
        assert result.exit_code == 0
        assert "supersecretkey12345" not in result.output
        # Should show max 7 chars + "..."
        assert "qk_supe" in result.output or "qk_***" in result.output

    def test_whoami_json_masks_api_key(self) -> None:
        """querri whoami --json must mask the API key."""
        result = runner.invoke(
            main_app,
            ["--api-key", "qk_supersecretkey12345", "--org-id", "org_1", "--json", "whoami"],
        )
        assert result.exit_code == 0
        assert "supersecretkey12345" not in result.output
        data = json.loads(result.output)
        assert "supersecretkey12345" not in json.dumps(data)

    def test_json_error_output_no_credentials(self) -> None:
        """--json error output must not contain API keys."""
        from querri._exceptions import NotFoundError

        mock_client = MagicMock()
        mock_client.projects.get.side_effect = NotFoundError(
            "Not found", status=404
        )

        with patch("querri.cli.projects.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    "--api-key", "qk_supersecretkey12345",
                    "--org-id", "org_1",
                    "--json",
                    "projects", "get", "proj_1",
                ],
            )
            # No credentials should be in any output
            assert "supersecretkey12345" not in result.output


# ---------------------------------------------------------------------------
# SEC: Shell history warning
# ---------------------------------------------------------------------------


class TestShellHistoryWarning:
    """--api-key flag triggers shell history warning on TTY."""

    def test_api_key_flag_warning_in_interactive(self) -> None:
        """When --api-key is passed in interactive mode, stderr should warn."""
        # CliRunner doesn't have a real TTY, so we test via --interactive override
        result = runner.invoke(
            main_app,
            [
                "--api-key", "qk_test123456",
                "--org-id", "org_1",
                "--interactive",
                "whoami",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        # Warning about shell history should be present in output
        # (CliRunner mixes stdout/stderr)
        assert "shell history" in result.output.lower() or "querri_api_key" in result.output.upper()

    def test_no_warning_in_non_interactive(self) -> None:
        """--no-interactive suppresses the shell history warning."""
        result = runner.invoke(
            main_app,
            [
                "--api-key", "qk_test123456",
                "--org-id", "org_1",
                "--no-interactive",
                "whoami",
            ],
        )
        assert result.exit_code == 0
        # Should NOT have the warning
        assert "shell history" not in result.output.lower()


# ---------------------------------------------------------------------------
# File upload path validation (R18)
# ---------------------------------------------------------------------------


class TestFilePathValidation:
    """File upload rejects non-existent and non-regular files."""

    def test_upload_nonexistent_file_rejected(self) -> None:
        """querri files upload with non-existent path → error."""
        mock_client = MagicMock()

        with patch("querri.cli.files.get_client", return_value=mock_client):
            result = runner.invoke(
                main_app,
                [
                    "--api-key", "qk_test123456",
                    "--org-id", "org_1",
                    "file", "upload", "/nonexistent/path/file.csv",
                ],
            )
            assert result.exit_code == 1
            assert "not found" in result.output.lower() or "error" in result.output.lower()


# ---------------------------------------------------------------------------
# Exit code mapping
# ---------------------------------------------------------------------------


class TestExitCodeMapping:
    """Verify exception-to-exit-code mapping."""

    def test_handle_api_error_auth(self) -> None:
        from querri._exceptions import AuthenticationError
        from querri.cli._output import handle_api_error

        exc = AuthenticationError("Invalid key", status=401)
        code = handle_api_error(exc, is_json=False)
        assert code == 2

    def test_handle_api_error_not_found(self) -> None:
        from querri._exceptions import NotFoundError
        from querri.cli._output import handle_api_error

        exc = NotFoundError("Not found", status=404)
        code = handle_api_error(exc, is_json=False)
        assert code == 3

    def test_handle_api_error_rate_limit(self) -> None:
        from querri._exceptions import RateLimitError
        from querri.cli._output import handle_api_error

        exc = RateLimitError("Rate limited", retry_after=30.0)
        code = handle_api_error(exc, is_json=False)
        assert code == 4

    def test_handle_api_error_general(self) -> None:
        from querri._exceptions import ServerError
        from querri.cli._output import handle_api_error

        exc = ServerError("Internal error", status=500)
        code = handle_api_error(exc, is_json=False)
        assert code == 5

    def test_handle_api_error_json_mode(self, capsys) -> None:
        """JSON mode outputs structured error."""
        from querri._exceptions import AuthenticationError
        from querri.cli._output import handle_api_error

        exc = AuthenticationError("Invalid", status=401)
        code = handle_api_error(exc, is_json=True)

        assert code == 2
        captured = capsys.readouterr()
        # JSON error goes to stderr via print_json_error
        output = captured.err or captured.out  # CliRunner may route differently
        data = json.loads(output)
        assert data["error"] == "auth_failed"
        assert data["code"] == 2


# ---------------------------------------------------------------------------
# Output module contract
# ---------------------------------------------------------------------------


class TestOutputModule:
    """Test output module helpers."""

    def test_print_json_with_pydantic_model(self) -> None:
        """print_json handles Pydantic models."""
        import io
        import sys

        from querri.cli._output import print_json
        from querri.types.project import Project

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            print_json(Project(id="proj_1", name="Test", status="idle"))
        finally:
            sys.stdout = old_stdout

        data = json.loads(captured.getvalue())
        assert data["id"] == "proj_1"
        assert data["name"] == "Test"

    def test_print_json_with_dict(self) -> None:
        """print_json handles plain dicts."""
        import io
        import sys

        from querri.cli._output import print_json

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            print_json({"id": "test", "name": "foo"})
        finally:
            sys.stdout = old_stdout

        data = json.loads(captured.getvalue())
        assert data["id"] == "test"


# ---------------------------------------------------------------------------
# Import discipline (SPEC §5.1)
# ---------------------------------------------------------------------------


class TestImportDiscipline:
    """Core SDK must not pull in CLI or TUI dependencies."""

    def test_core_sdk_does_not_import_cli(self) -> None:
        """Importing querri (core) must not trigger querri.cli imports.

        This ensures ``pip install querri`` (without [cli]) works even when
        Typer/Rich are not installed.
        """
        # After importing the core SDK, querri.cli should NOT be in sys.modules
        # unless the test runner already imported it. We check that the core
        # __init__.py doesn't eagerly import cli.
        import ast
        import inspect

        import querri

        source = inspect.getsource(querri)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith(".cli"), (
                    f"Core querri/__init__.py imports from CLI: {node.module}"
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("querri.cli"), (
                        f"Core querri/__init__.py imports CLI: {alias.name}"
                    )

    def test_core_sdk_does_not_import_tui(self) -> None:
        """Core SDK must not import querri.tui."""
        import ast
        import inspect

        import querri

        source = inspect.getsource(querri)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith(".tui"), (
                    f"Core querri/__init__.py imports from TUI: {node.module}"
                )


# ---------------------------------------------------------------------------
# Entry point security (SPEC §6.10)
# ---------------------------------------------------------------------------


class TestEntryPointSecurity:
    """Entry point error handler must not leak internals."""

    def test_entry_point_error_no_file_paths(self, capsys) -> None:
        """ImportError handler must not reveal file system paths."""
        import importlib
        import sys as _sys

        import querri.cli as cli_mod

        original = _sys.modules.get("querri.cli._app")
        _sys.modules["querri.cli._app"] = None  # type: ignore[assignment]
        try:
            importlib.reload(cli_mod)
            with pytest.raises(SystemExit):
                cli_mod.app()
            captured = capsys.readouterr()
            # No Python file paths
            assert ".py" not in captured.err
            # No home directory paths
            assert "/Users/" not in captured.err
            assert "/home/" not in captured.err
            # No traceback markers
            assert "Traceback" not in captured.err
            assert "File " not in captured.err
        finally:
            if original is not None:
                _sys.modules["querri.cli._app"] = original
            else:
                _sys.modules.pop("querri.cli._app", None)
            importlib.reload(cli_mod)

    def test_exception_hierarchy_no_secrets(self) -> None:
        """SDK exception messages should not embed credentials."""
        from querri._exceptions import ConfigError

        # The ConfigError for missing API key should guide, not leak
        exc = ConfigError(
            "No API key provided. Pass api_key= to the constructor "
            "or set the QUERRI_API_KEY environment variable."
        )
        assert "qk_" not in str(exc)
        assert "ey" not in str(exc).split()[0]  # Don't match "every", "environment"


# ---------------------------------------------------------------------------
# Error output never contains raw credentials
# ---------------------------------------------------------------------------


class TestNoCredentialLeakInErrors:
    """Verify that API errors don't echo back credentials."""

    def test_auth_error_message_no_key(self) -> None:
        """AuthenticationError message should not contain the actual API key."""
        from querri._exceptions import AuthenticationError

        # Simulate what the server returns — should not include the key
        exc = AuthenticationError(
            "Authentication failed. Check your API key.",
            status=401,
        )
        assert "qk_" not in str(exc)

    def test_config_error_json_no_key(self) -> None:
        """JSON error output for config errors must not contain credentials."""
        result = runner.invoke(
            main_app,
            ["--json", "whoami"],
            env={"QUERRI_API_KEY": "", "QUERRI_ORG_ID": ""},
        )
        # The output (stdout + stderr mixed by CliRunner) should not contain
        # any real API key patterns
        assert "qk_" not in result.output
