"""Tests for custom roles as code: the Roles resource and ``querri role`` CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from querri._base_client import AsyncHTTPClient, SyncHTTPClient
from querri._config import ClientConfig
from querri.cli import roles as roles_cli
from querri.cli._app import main_app
from querri.resources.roles import AsyncRoles, Roles
from querri.types.role import RoleDefinition

BASE = "https://test.querri.com/api/v1"
CLI_HOST = "https://cli-test.querri.com"
CLI_BASE = f"{CLI_HOST}/api/v1"
_GLOBAL = ["--api-key", "qk_test123456", "--org-id", "org_1", "--host", CLI_HOST]

runner = CliRunner()


def _make_config() -> ClientConfig:
    return ClientConfig(
        api_key="qk_test",
        org_id="org_test",
        base_url=BASE,
        timeout=10.0,
        max_retries=0,
    )


def _role(**overrides: Any) -> dict[str, Any]:
    role: dict[str, Any] = {
        "schema": "querri.role/v1",
        "key": "ev-datapro",
        "name": "EV DataPro",
        "description": "Projects only",
        "base": "creator",
        "enabled": True,
        "grants": [],
        "denies": ["tools.charts.use", "chat.code.view"],
        "settings": {
            "chat.think_longer.use": {"default": "fast", "user_can_change": False}
        },
        "config": {"home_chat": "project"},
        "id": "role_123",
        "system": False,
        "seat_class": "creator",
        "user_count": 4,
        "updated_at": "2026-10-30T12:00:00Z",
    }
    role.update(overrides)
    return role


_SYSTEM = _role(key="creator", name="Creator", system=True, id="role_sys")

_OUTPUT_ONLY = {"id", "system", "seat_class", "user_count", "updated_at"}


def _result(action: str = "updated", **overrides: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "key": "ev-datapro",
        "action": action,
        "changes": [
            {
                "field": "denies",
                "before": ["tools.dashboards.use"],
                "after": ["chat.code.view"],
            }
        ],
        "role": _role(),
        "error": None,
    }
    result.update(overrides)
    return result


# =========================================================================
# Types
# =========================================================================


def test_to_definition_strips_output_only_and_keeps_unknown_fields() -> None:
    role = RoleDefinition.model_validate(_role(future_field={"a": 1}))
    doc = role.to_definition()
    assert not _OUTPUT_ONLY & doc.keys()
    assert doc["schema"] == "querri.role/v1"
    assert doc["future_field"] == {"a": 1}
    assert doc["denies"] == ["tools.charts.use", "chat.code.view"]


# =========================================================================
# Resource — sync
# =========================================================================


class TestRolesSync:
    @respx.mock
    def test_list_returns_data(self) -> None:
        respx.get(f"{BASE}/roles").mock(
            return_value=httpx.Response(
                200, json={"data": [_role(), _SYSTEM], "catalog_version": 3}
            )
        )
        roles = Roles(SyncHTTPClient(_make_config())).list()
        assert [r.key for r in roles] == ["ev-datapro", "creator"]
        assert roles[1].system is True
        assert roles[0].user_count == 4

    @respx.mock
    def test_get(self) -> None:
        respx.get(f"{BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(200, json=_role())
        )
        role = Roles(SyncHTTPClient(_make_config())).get("ev-datapro")
        assert role.name == "EV DataPro"
        assert role.config == {"home_chat": "project"}

    @respx.mock
    def test_catalog_keeps_extra_fields(self) -> None:
        respx.get(f"{BASE}/roles/catalog").mock(
            return_value=httpx.Response(
                200,
                json={
                    "catalog_version": 7,
                    "permissions": [
                        {
                            "key": "tools.charts.use",
                            "area": "tools",
                            "kind": "action",
                            "defaults": {"guest": False, "creator": True},
                            "requires": ["chat.use"],
                            "label": "Use charts",
                        }
                    ],
                },
            )
        )
        cat = Roles(SyncHTTPClient(_make_config())).catalog()
        assert cat.catalog_version == 7
        perm = cat.permissions[0]
        assert perm.requires == ["chat.use"]
        assert perm.model_extra == {"label": "Use charts"}

    @respx.mock
    def test_apply_puts_to_key_without_output_only_fields(self) -> None:
        route = respx.put(f"{BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(200, json=_result())
        )
        result = Roles(SyncHTTPClient(_make_config())).apply(
            RoleDefinition.model_validate(_role())
        )
        assert result.action == "updated"
        assert result.changes[0].field == "denies"
        req = route.calls[0].request
        assert "dry_run" not in req.url.params
        body = json.loads(req.content)
        assert body["key"] == "ev-datapro"
        assert not _OUTPUT_ONLY & body.keys()

    @respx.mock
    def test_apply_dry_run_query_param(self) -> None:
        route = respx.put(f"{BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(200, json=_result("would_update"))
        )
        result = Roles(SyncHTTPClient(_make_config())).apply(
            {"key": "ev-datapro", "name": "EV DataPro"}, dry_run=True
        )
        assert result.action == "would_update"
        assert route.calls[0].request.url.params["dry_run"] == "true"

    def test_apply_without_key_raises(self) -> None:
        with pytest.raises(ValueError, match="key"):
            Roles(SyncHTTPClient(_make_config())).apply({"name": "No key"})

    @respx.mock
    def test_import_roles_body(self) -> None:
        route = respx.post(f"{BASE}/roles/import").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        _result("created"),
                        _result(
                            "failed",
                            key="bad",
                            role=None,
                            changes=[],
                            error={"code": "escalation_denied", "message": "no"},
                        ),
                    ],
                    "applied": 1,
                    "failed": 1,
                },
            )
        )
        out = Roles(SyncHTTPClient(_make_config())).import_roles(
            [_role(), {"key": "bad", "name": "Bad"}], dry_run=True
        )
        assert out.failed == 1
        assert out.results[1].failed
        assert out.results[1].error is not None
        assert out.results[1].error.code == "escalation_denied"
        body = json.loads(route.calls[0].request.content)
        assert body["dry_run"] is True
        assert [r["key"] for r in body["roles"]] == ["ev-datapro", "bad"]
        assert not _OUTPUT_ONLY & body["roles"][0].keys()

    @respx.mock
    def test_delete_with_reassign_to(self) -> None:
        route = respx.delete(f"{BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(200, json={"deleted": "ev-datapro"})
        )
        resp = Roles(SyncHTTPClient(_make_config())).delete(
            "ev-datapro", reassign_to="creator"
        )
        assert resp.deleted == "ev-datapro"
        assert route.calls[0].request.url.params["reassign_to"] == "creator"

    @respx.mock
    def test_export_skips_system_and_fetches_summaries(self) -> None:
        summary = {"key": "lite", "name": "Lite", "base": "guest", "system": False}
        respx.get(f"{BASE}/roles").mock(
            return_value=httpx.Response(200, json={"data": [_role(), _SYSTEM, summary]})
        )
        detail = respx.get(f"{BASE}/roles/lite").mock(
            return_value=httpx.Response(
                200, json=_role(key="lite", name="Lite", base="guest")
            )
        )
        docs = Roles(SyncHTTPClient(_make_config())).export()
        assert [d["key"] for d in docs] == ["ev-datapro", "lite"]
        assert detail.called
        assert all(not _OUTPUT_ONLY & d.keys() for d in docs)


# =========================================================================
# Resource — async
# =========================================================================


class TestRolesAsync:
    @respx.mock
    async def test_list_and_get(self) -> None:
        respx.get(f"{BASE}/roles").mock(
            return_value=httpx.Response(200, json={"data": [_role()]})
        )
        respx.get(f"{BASE}/roles/role_123").mock(
            return_value=httpx.Response(200, json=_role())
        )
        roles = AsyncRoles(AsyncHTTPClient(_make_config()))
        assert [r.key for r in await roles.list()] == ["ev-datapro"]
        assert (await roles.get("role_123")).id == "role_123"

    @respx.mock
    async def test_catalog(self) -> None:
        respx.get(f"{BASE}/roles/catalog").mock(
            return_value=httpx.Response(
                200, json={"catalog_version": 1, "permissions": [{"key": "a.b"}]}
            )
        )
        cat = await AsyncRoles(AsyncHTTPClient(_make_config())).catalog()
        assert cat.permissions[0].key == "a.b"

    @respx.mock
    async def test_apply_dry_run(self) -> None:
        route = respx.put(f"{BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(200, json=_result("would_create"))
        )
        result = await AsyncRoles(AsyncHTTPClient(_make_config())).apply(
            _role(), dry_run=True
        )
        assert result.action == "would_create"
        assert route.calls[0].request.url.params["dry_run"] == "true"

    @respx.mock
    async def test_import_and_delete(self) -> None:
        imp = respx.post(f"{BASE}/roles/import").mock(
            return_value=httpx.Response(
                200, json={"results": [_result("created")], "applied": 1, "failed": 0}
            )
        )
        dele = respx.delete(f"{BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(200, json={"deleted": "ev-datapro"})
        )
        roles = AsyncRoles(AsyncHTTPClient(_make_config()))
        out = await roles.import_roles([_role()])
        assert out.applied == 1
        assert json.loads(imp.calls[0].request.content)["dry_run"] is False
        await roles.delete("ev-datapro", reassign_to="creator")
        assert dele.calls[0].request.url.params["reassign_to"] == "creator"

    @respx.mock
    async def test_export(self) -> None:
        respx.get(f"{BASE}/roles").mock(
            return_value=httpx.Response(200, json={"data": [_role(), _SYSTEM]})
        )
        roles = AsyncRoles(AsyncHTTPClient(_make_config()))
        assert [d["key"] for d in await roles.export()] == ["ev-datapro"]
        assert len(await roles.export(include_system=True)) == 2


# =========================================================================
# CLI
# =========================================================================


def _write(path: Path, data: Any) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestRolesCli:
    @respx.mock
    def test_apply_single_definition_puts(self, tmp_path: Path) -> None:
        route = respx.put(f"{CLI_BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(200, json=_result())
        )
        f = _write(tmp_path / "ev.json", _role())
        result = runner.invoke(main_app, [*_GLOBAL, "role", "apply", "-f", str(f)])
        assert result.exit_code == 0, result.output
        assert route.called
        assert "ev-datapro: updated" in result.output
        assert "denies: +chat.code.view -tools.dashboards.use" in result.output

    @respx.mock
    def test_apply_roles_file_imports_and_fails_nonzero(self, tmp_path: Path) -> None:
        route = respx.post(f"{CLI_BASE}/roles/import").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        _result("unchanged", changes=[]),
                        _result(
                            "failed",
                            key="bad",
                            role=None,
                            changes=[],
                            error={
                                "code": "escalation_denied",
                                "message": "You cannot grant admin.roles.manage",
                            },
                        ),
                    ],
                    "applied": 1,
                    "failed": 1,
                },
            )
        )
        f = _write(
            tmp_path / "roles.json",
            {"roles": [_role(), {"key": "bad", "name": "Bad"}]},
        )
        result = runner.invoke(main_app, [*_GLOBAL, "roles", "apply", "-f", str(f)])
        assert result.exit_code == 1
        assert route.called
        assert "ev-datapro: unchanged" in result.output
        assert "bad: failed [escalation_denied]" in result.output

    @respx.mock
    def test_apply_dry_run(self, tmp_path: Path) -> None:
        route = respx.put(f"{CLI_BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(
                200,
                json=_result(
                    "would_update",
                    changes=[
                        {
                            "field": "config",
                            "before": {"home_chat": "chat"},
                            "after": {"home_chat": "project"},
                        }
                    ],
                ),
            )
        )
        f = _write(tmp_path / "ev.json", [_role()])
        result = runner.invoke(
            main_app, [*_GLOBAL, "role", "apply", "-f", str(f), "--dry-run"]
        )
        assert result.exit_code == 0, result.output
        assert route.calls[0].request.url.params["dry_run"] == "true"
        assert 'config.home_chat: "chat" -> "project"' in result.output

    def test_apply_rejects_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "ev.yaml"
        f.write_text("key: ev\n", encoding="utf-8")
        result = runner.invoke(main_app, [*_GLOBAL, "role", "apply", "-f", str(f)])
        assert result.exit_code == 1
        assert "YAML is not supported" in result.output

    @respx.mock
    def test_get_prints_reapplyable_definition(self) -> None:
        respx.get(f"{CLI_BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(200, json=_role())
        )
        result = runner.invoke(main_app, [*_GLOBAL, "role", "get", "ev-datapro"])
        assert result.exit_code == 0, result.output
        doc = json.loads(result.output)
        assert doc["key"] == "ev-datapro"
        assert not _OUTPUT_ONLY & doc.keys()

    @respx.mock
    def test_export_round_trip_reapplies_unchanged(self, tmp_path: Path) -> None:
        respx.get(f"{CLI_BASE}/roles").mock(
            return_value=httpx.Response(
                200, json={"data": [_role(), _role(key="b", name="B"), _SYSTEM]}
            )
        )
        out = tmp_path / "roles.json"
        result = runner.invoke(main_app, [*_GLOBAL, "role", "export", "-o", str(out)])
        assert result.exit_code == 0, result.output
        exported = json.loads(out.read_text())
        assert [r["key"] for r in exported["roles"]] == ["ev-datapro", "b"]

        route = respx.post(f"{CLI_BASE}/roles/import").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        _result("unchanged", changes=[]),
                        _result("unchanged", key="b", changes=[]),
                    ],
                    "applied": 2,
                    "failed": 0,
                },
            )
        )
        result = runner.invoke(main_app, [*_GLOBAL, "role", "apply", "-f", str(out)])
        assert result.exit_code == 0, result.output
        # What was exported is exactly what is sent back.
        sent = json.loads(route.calls[0].request.content)["roles"]
        assert sent == exported["roles"]
        # And it is the server's definition minus output-only fields.
        expected = {k: v for k, v in _role().items() if k not in _OUTPUT_ONLY}
        assert sent[0] == expected

    @respx.mock
    def test_delete_confirms(self) -> None:
        route = respx.delete(f"{CLI_BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(200, json={"deleted": "ev-datapro"})
        )
        declined = runner.invoke(
            main_app, [*_GLOBAL, "role", "delete", "ev-datapro"], input="n\n"
        )
        assert declined.exit_code == 1
        assert not route.called

        accepted = runner.invoke(
            main_app,
            [*_GLOBAL, "role", "delete", "ev-datapro", "--reassign-to", "creator"],
            input="y\n",
        )
        assert accepted.exit_code == 0, accepted.output
        assert route.calls[0].request.url.params["reassign_to"] == "creator"

    @respx.mock
    def test_delete_yes_skips_prompt(self) -> None:
        route = respx.delete(f"{CLI_BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(200, json={"deleted": "ev-datapro"})
        )
        result = runner.invoke(
            main_app, [*_GLOBAL, "role", "delete", "ev-datapro", "--yes"]
        )
        assert result.exit_code == 0, result.output
        assert route.called

    @respx.mock
    def test_list_and_catalog_tables(self) -> None:
        respx.get(f"{CLI_BASE}/roles").mock(
            return_value=httpx.Response(200, json={"data": [_role(), _SYSTEM]})
        )
        respx.get(f"{CLI_BASE}/roles/catalog").mock(
            return_value=httpx.Response(
                200,
                json={
                    "permissions": [
                        {"key": "tools.charts.use", "area": "tools", "kind": "action",
                         "defaults": {"guest": False, "creator": True, "admin": True}},
                        {"key": "chat.code.view", "area": "chat", "kind": "action"},
                    ]
                },
            )
        )
        listed = runner.invoke(main_app, [*_GLOBAL, "role", "list"])
        assert listed.exit_code == 0, listed.output
        assert "ev-datapro\tEV DataPro\tcreator\tyes\t4\t" in listed.output
        cat = runner.invoke(main_app, [*_GLOBAL, "role", "catalog", "--area", "tools"])
        assert cat.exit_code == 0, cat.output
        assert "tools.charts.use\ttools\taction\tno\tyes\tyes" in cat.output
        assert "chat.code.view" not in cat.output

    @respx.mock
    def test_apply_watch_reapplies_on_save(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        route = respx.put(f"{CLI_BASE}/roles/ev-datapro").mock(
            return_value=httpx.Response(200, json=_result())
        )
        f = _write(tmp_path / "ev.json", _role())
        ticks = {"n": 0}

        def fake_sleep(_: float) -> None:
            ticks["n"] += 1
            if ticks["n"] == 1:  # the user saves the file
                _write(f, _role(name="EV DataPro 2"))
                st = f.stat()
                os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
            elif ticks["n"] == 2:  # no change: no re-apply
                pass
            else:
                raise KeyboardInterrupt

        monkeypatch.setattr(roles_cli.time, "sleep", fake_sleep)
        result = runner.invoke(
            main_app, [*_GLOBAL, "role", "apply", "-f", str(f), "--watch"]
        )
        assert result.exit_code == 0, result.output
        assert route.call_count == 2
        assert json.loads(route.calls[1].request.content)["name"] == "EV DataPro 2"
