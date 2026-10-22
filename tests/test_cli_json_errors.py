"""The CLI ``--json`` error contract: the 2.1.0 shape, plus ``exit_code``.

Every JSON error emitter must print exactly the keys and values 2.1.0 printed
for the same situation (``git show v2.1.0:querri/cli/_output.py`` and the
command modules are the reference), plus ``"exit_code"`` — the process exit
code. Each test pins the whole object with ``==``, so an added, dropped or
renamed key fails.

API errors go through the real CLI and SDK: respx answers at the HTTP
boundary, and the exception that reaches ``handle_api_error`` is the one the
SDK raised for that response.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from querri._auth import TokenProfile, TokenStore
from querri.cli._app import main_app

runner = CliRunner()

HOST = "https://test.querri.com"
API = HOST + "/api/v1"
BASE_ARGS = ["--api-key", "qk_test123456", "--org-id", "org_1", "--host", HOST]
#: No retries, so a 429 or 5xx answers once and the test does not sleep.
ENV = {"QUERRI_MAX_RETRIES": "0"}


@pytest.fixture(autouse=True)
def _isolated_token_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the token store at an empty temp dir, never ~/.querri."""
    monkeypatch.setattr(TokenStore, "STORE_DIR", tmp_path)
    monkeypatch.setattr(TokenStore, "STORE_FILE", tmp_path / "tokens.json")
    monkeypatch.delenv("QUERRI_USER_ID", raising=False)
    return tmp_path


def _json_out(result) -> dict:  # type: ignore[no-untyped-def]
    """The single JSON object the command printed on stdout."""
    return json.loads(result.stdout)


def _project_get(status: int, *, body=None, headers=None):  # type: ignore[no-untyped-def]
    """Run ``querri --json project get p1`` against a mocked error response."""
    with respx.mock:
        respx.get(f"{API}/projects/p1").mock(
            return_value=httpx.Response(status, json=body, headers=headers)
        )
        return runner.invoke(
            main_app, [*BASE_ARGS, "--json", "project", "get", "p1"], env=ENV
        )


# ---------------------------------------------------------------------------
# handle_api_error
# ---------------------------------------------------------------------------


class TestHandleApiErrorJson:
    """``handle_api_error``: 2.1.0 started ``code`` at the exit code, then let
    the API code (when sent) overwrite it, and added status/type/request_id/
    doc_url when set."""

    def test_403_with_api_code_is_api_error_and_code_is_the_api_code(self) -> None:
        result = _project_get(
            403,
            body={
                "detail": {
                    "error": {
                        "type": "permission_error",
                        "code": "permission_denied",
                        "message": "This action needs dashboards.list.view.",
                        "permission": "dashboards.list.view",
                        "reason": "role_denied",
                        "doc_url": "https://docs.querri.com/errors",
                    }
                }
            },
            headers={"X-Request-Id": "req_403"},
        )

        assert result.exit_code == 6
        assert _json_out(result) == {
            "error": "api_error",
            "message": "This action needs dashboards.list.view.",
            "code": "permission_denied",
            "status": "403",
            "type": "permission_error",
            "request_id": "req_403",
            "doc_url": "https://docs.querri.com/errors",
            "exit_code": 6,
        }

    def test_403_without_api_code_code_is_the_exit_code(self) -> None:
        result = _project_get(403, body={"detail": "Forbidden"})

        assert result.exit_code == 6
        assert _json_out(result) == {
            "error": "api_error",
            "message": "Forbidden",
            "code": 6,
            "status": "403",
            "exit_code": 6,
        }

    def test_401(self) -> None:
        result = _project_get(
            401,
            body={
                "error": {
                    "type": "authentication_error",
                    "code": "invalid_api_key",
                    "message": "Invalid API key.",
                }
            },
        )

        assert result.exit_code == 2
        assert _json_out(result) == {
            "error": "auth_failed",
            "message": "Authentication failed. Check your API key"
            " or set QUERRI_API_KEY environment variable.",
            "code": "invalid_api_key",
            "status": "401",
            "type": "authentication_error",
            "exit_code": 2,
        }

    def test_404(self) -> None:
        result = _project_get(
            404,
            body={"detail": {"error": {"code": "not_found", "message": "No p1."}}},
        )

        assert result.exit_code == 3
        assert _json_out(result) == {
            "error": "not_found",
            "message": "No p1.",
            "code": "not_found",
            "status": "404",
            "exit_code": 3,
        }

    def test_429(self) -> None:
        result = _project_get(
            429,
            body={"error": {"code": "rate_limit_exceeded", "message": "Slow down."}},
            headers={"Retry-After": "30"},
        )

        assert result.exit_code == 4
        assert _json_out(result) == {
            "error": "rate_limited",
            "message": "Rate limited. Retry after 30.0s.",
            "code": "rate_limit_exceeded",
            "status": "429",
            "exit_code": 4,
        }

    def test_500_without_api_code(self) -> None:
        result = _project_get(500, body={"detail": "Internal Server Error"})

        assert result.exit_code == 5
        assert _json_out(result) == {
            "error": "server_error",
            "message": "Internal Server Error",
            "code": 5,
            "status": "500",
            "exit_code": 5,
        }

    def test_501(self) -> None:
        result = _project_get(501, body={"detail": "Not implemented"})

        assert result.exit_code == 1
        assert _json_out(result) == {
            "error": "not_implemented",
            "message": "This feature is not yet available via the API. "
            "Use the Querri web app instead.",
            "code": 1,
            "status": "501",
            "exit_code": 1,
        }

    def test_409_last_admin_is_api_error(self) -> None:
        result = _project_get(
            409,
            body={
                "detail": {
                    "error": {
                        "type": "conflict_error",
                        "code": "last_admin",
                        "message": "The org needs an admin.",
                    }
                }
            },
        )

        assert result.exit_code == 1
        assert _json_out(result) == {
            "error": "api_error",
            "message": "The org needs an admin.",
            "code": "last_admin",
            "status": "409",
            "type": "conflict_error",
            "exit_code": 1,
        }


# ---------------------------------------------------------------------------
# print_json_error and its callers
# ---------------------------------------------------------------------------


class TestPrintJsonError:
    """``print_json_error``: 2.1.0 printed ``error``, ``message``, ``code`` (the
    exit code) and ``hint`` when set."""

    def test_direct_with_hint(self, capsys: pytest.CaptureFixture[str]) -> None:
        from querri.cli._output import print_json_error

        print_json_error("bad", "Bad thing.", 1, hint="Try again.")

        assert json.loads(capsys.readouterr().out) == {
            "error": "bad",
            "message": "Bad thing.",
            "code": 1,
            "hint": "Try again.",
            "exit_code": 1,
        }

    def test_project_run_wait_timeout(self) -> None:
        with respx.mock:
            respx.post(f"{API}/projects/p1/run").mock(
                return_value=httpx.Response(
                    200, json={"id": "p1", "run_id": "r1", "status": "submitted"}
                )
            )
            respx.get(f"{API}/projects/p1/run/status").mock(
                return_value=httpx.Response(
                    200, json={"id": "p1", "status": "running", "is_running": True}
                )
            )
            result = runner.invoke(
                main_app,
                [*BASE_ARGS, "--json", "project", "run", "p1", "--user-id", "u1",
                 "--wait", "--timeout", "0"],
                env=ENV,
            )

        assert result.exit_code == 1
        assert _json_out(result) == {
            "error": "timeout",
            "message": "Run did not complete within 0s",
            "code": 1,
            "exit_code": 1,
        }

    def test_no_project(self) -> None:
        result = runner.invoke(
            main_app, [*BASE_ARGS, "--json", "project", "run"], env=ENV
        )

        assert result.exit_code == 1
        assert _json_out(result) == {
            "error": "no_project",
            "message": "No active project. Run 'querri project select <name>'"
            " or pass --project.",
            "code": 1,
            "exit_code": 1,
        }

    def test_no_user_id(self) -> None:
        result = runner.invoke(
            main_app, [*BASE_ARGS, "--json", "project", "run", "p1"], env=ENV
        )

        assert result.exit_code == 1
        assert _json_out(result) == {
            "error": "no_user_id",
            "message": "Could not determine user ID.",
            "code": 1,
            "exit_code": 1,
        }

    def test_source_new_invalid_json(self) -> None:
        result = runner.invoke(
            main_app,
            [*BASE_ARGS, "--json", "source", "new", "--name", "s"],
            input="{not json",
            env=ENV,
        )

        assert result.exit_code == 1
        data = _json_out(result)
        assert data["message"].startswith("Invalid JSON: ")
        assert data == {
            "error": "validation_error",
            "message": data["message"],
            "code": 1,
            "exit_code": 1,
        }


# ---------------------------------------------------------------------------
# Emitters that build their own object
# ---------------------------------------------------------------------------


class TestOwnEmitters:
    def test_config_error(self) -> None:
        """``_context._handle_config_error``: 2.1.0 keys plus exit_code."""
        result = runner.invoke(
            main_app,
            ["--json", "whoami"],
            env={"QUERRI_API_KEY": "", "QUERRI_ACCESS_TOKEN": "", "QUERRI_ORG_ID": ""},
        )

        assert result.exit_code == 2
        data = _json_out(result)
        assert data == {
            "error": "auth_failed",
            "message": data["message"],
            "hint": "Run 'querri auth login' or set QUERRI_API_KEY and "
            "QUERRI_ORG_ID environment variables.",
            "code": 2,
            "exit_code": 2,
        }

    def test_source_new_not_an_array(self) -> None:
        result = runner.invoke(
            main_app,
            [*BASE_ARGS, "--json", "source", "new", "--name", "s"],
            input='{"a": 1}',
            env=ENV,
        )

        assert result.exit_code == 1
        assert _json_out(result) == {
            "error": "validation_error",
            "message": "Expected a JSON array of objects.",
            "code": 1,
            "exit_code": 1,
        }

    def test_view_run_timeout(self) -> None:
        """2.1.0 printed ``{"error": "<message>"}`` here — no message/code."""
        with respx.mock:
            respx.post(f"{API}/views/run").mock(
                return_value=httpx.Response(
                    202, json={"run_id": "run_1", "status": "queued"}
                )
            )
            respx.get(f"{API}/views/runs/run_1").mock(
                return_value=httpx.Response(
                    200, json={"run_id": "run_1", "status": "running"}
                )
            )
            result = runner.invoke(
                main_app,
                [*BASE_ARGS, "--json", "view", "run", "--timeout", "0"],
                env=ENV,
            )

        assert result.exit_code == 1
        assert _json_out(result) == {
            "error": "View run run_1 did not finish within 0.0s "
            "(last status='running').",
            "exit_code": 1,
        }

    def test_auth_switch_org_single_org(self) -> None:
        """2.1.0 printed ``error`` and ``message`` only (no ``code``)."""
        store = TokenStore()
        store.save_profile(
            "default",
            TokenProfile(
                access_token="at",
                refresh_token="rt",
                org_id="org_1",
                all_organizations={"org_1": "Only Org"},
            ),
        )

        result = runner.invoke(main_app, ["--json", "auth", "switch-org"])

        assert result.exit_code == 1
        assert _json_out(result) == {
            "error": "single_org",
            "message": "Only one organization available.",
            "exit_code": 1,
        }
