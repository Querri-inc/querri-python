"""v1 admin surface: workspaces, roles, settings/flags, workspace sharing,
Library move/facts/kinds/categories, view-build names, chat choice cards, and
per-org library context.

Real clients against respx-mocked routes (the SDK's HTTP layer, error parsing
and the CLI's argument handling all run); only the network is faked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from querri._auth import TokenProfile, TokenStore
from querri._base_client import AsyncHTTPClient, SyncHTTPClient
from querri._config import ClientConfig
from querri.cli import library as library_cli
from querri.cli._app import main_app
from querri.resources.flags import AsyncFlags, Flags
from querri.resources.library import AsyncLibrary, Library
from querri.resources.settings import AsyncSettings, Settings
from querri.resources.sharing import AsyncSharing, Sharing
from querri.resources.users import AsyncUsers, Users
from querri.resources.workspaces import AsyncWorkspaces, Workspaces

BASE = "https://test.querri.com/api/v1"
CLI_HOST = "https://cli-test.querri.com"
CLI_BASE = f"{CLI_HOST}/api/v1"
_GLOBAL = ["--api-key", "qk_test123456", "--org-id", "org_1", "--host", CLI_HOST]

runner = CliRunner()

_WS = [
    {"id": "workspace_fin", "name": "Finance", "slug": "finance",
     "kind": "named", "member_count": 3},
    {"id": "repo_default", "name": "Company", "slug": "company",
     "kind": "company", "member_count": 12},
]


def _cfg() -> ClientConfig:
    return ClientConfig(
        api_key="qk_test", org_id="org_test", base_url=BASE,
        timeout=10.0, max_retries=0,
    )


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(TokenStore, "STORE_DIR", tmp_path)
    monkeypatch.setattr(TokenStore, "STORE_FILE", tmp_path / "tokens.json")
    monkeypatch.setattr(
        library_cli, "_LIBRARY_CONTEXT_FILE", tmp_path / "library_context.json"
    )
    for var in ("QUERRI_LIBRARY_ID", "QUERRI_WORKSPACE_ID", "QUERRI_API_KEY",
                "QUERRI_ACCESS_TOKEN", "QUERRI_ORG_ID", "QUERRI_HOST",
                # TokenStore.save() is a no-op under CI, which would leave the
                # profile a test just saved unwritten on the runner.
                "CI"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def _body(route: respx.Route, i: int = 0) -> Any:
    return json.loads(route.calls[i].request.content)


def _sse_stream(events: list[dict[str, Any]]) -> httpx.Response:
    lines = [f"data: {json.dumps(e)}" for e in events] + ["data: [DONE]"]
    return httpx.Response(
        200, headers={"content-type": "text/event-stream"},
        content="\n".join(lines).encode(),
    )


# ═══ Workspaces (v1) ═════════════════════════════════════════════════════


class TestWorkspacesResource:
    @respx.mock
    def test_list_get_members_use_v1_routes(self) -> None:
        respx.get(f"{BASE}/workspaces").mock(
            return_value=httpx.Response(200, json={"data": _WS, "has_more": False})
        )
        respx.get(f"{BASE}/workspaces/workspace_fin").mock(
            return_value=httpx.Response(200, json=_WS[0])
        )
        respx.get(f"{BASE}/workspaces/workspace_fin/members").mock(
            return_value=httpx.Response(200, json={"data": [
                {"user_id": "u1", "email": "a@x.com", "name": "A", "role": "admin"},
            ]})
        )
        ws = Workspaces(SyncHTTPClient(_cfg()))
        assert [w["kind"] for w in ws.list()] == ["named", "company"]
        assert ws.get("workspace_fin") == _WS[0]
        assert ws.get("finance") == _WS[0]  # by slug, via list
        assert ws.get("FINANCE") == _WS[0]
        assert ws.members("workspace_fin")[0]["email"] == "a@x.com"

    @respx.mock
    def test_get_unknown_is_none(self) -> None:
        respx.get(f"{BASE}/workspaces/workspace_gone").mock(
            return_value=httpx.Response(404, json={"error": {"message": "nope"}})
        )
        assert Workspaces(SyncHTTPClient(_cfg())).get("workspace_gone") is None

    @respx.mock
    async def test_async_parity(self) -> None:
        respx.get(f"{BASE}/workspaces").mock(
            return_value=httpx.Response(200, json={"data": _WS})
        )
        respx.get(f"{BASE}/workspaces/workspace_x").mock(
            return_value=httpx.Response(404, json={})
        )
        respx.get(f"{BASE}/workspaces/repo_default/members").mock(
            return_value=httpx.Response(200, json={"data": [{"user_id": "u1"}]})
        )
        ws = AsyncWorkspaces(AsyncHTTPClient(_cfg()))
        assert len(await ws.list()) == 2
        assert (await ws.get("company"))["id"] == "repo_default"  # type: ignore[index]
        assert await ws.get("workspace_x") is None
        assert await ws.members("repo_default") == [{"user_id": "u1"}]


class TestWorkspaceCli:
    @respx.mock
    def test_list_shows_kind_and_members_with_an_api_key(self) -> None:
        respx.get(f"{CLI_BASE}/workspaces").mock(
            return_value=httpx.Response(200, json={"data": _WS})
        )
        result = runner.invoke(main_app, [*_GLOBAL, "workspace", "list"])
        assert result.exit_code == 0, result.output
        assert "company" in result.output and "named" in result.output
        assert "12" in result.output

    @respx.mock
    def test_members_by_slug(self) -> None:
        respx.get(f"{CLI_BASE}/workspaces").mock(
            return_value=httpx.Response(200, json={"data": _WS})
        )
        respx.get(f"{CLI_BASE}/workspaces/workspace_fin/members").mock(
            return_value=httpx.Response(200, json={"data": [
                {"user_id": "u1", "email": "a@x.com", "name": "Ann", "role": "admin"},
            ]})
        )
        result = runner.invoke(
            main_app, [*_GLOBAL, "--json", "workspace", "members", "finance"]
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)[0]["email"] == "a@x.com"


class TestSwitchOrgClearsScope:
    def test_switch_org_clears_workspace_and_project(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        TokenStore().save_profile("default", TokenProfile(
            access_token="at", refresh_token="rt", org_id="org_a",
            all_organizations={"org_a": "A", "org_b": "B"},
            active_workspace_id="workspace_a", active_workspace_name="A team",
            active_project_id="proj_a", active_project_name="A project",
        ))

        def _refresh(profile: TokenProfile, host: str, **kw: Any) -> TokenProfile:
            profile.access_token = "at_b"
            return profile

        monkeypatch.setattr("querri.cli.auth.refresh_tokens", _refresh)
        result = runner.invoke(main_app, ["auth", "switch-org", "org_b"])
        assert result.exit_code == 0, result.output
        profile = TokenStore.load().profiles["default"]
        assert profile.org_id == "org_b"
        assert profile.active_workspace_id == ""
        assert profile.active_workspace_name == ""
        assert profile.active_project_id == ""


# ═══ Users: role_id ═══════════════════════════════════════════════════════


class TestUserRoles:
    @respx.mock
    def test_update_role_id(self) -> None:
        route = respx.patch(f"{BASE}/users/u1").mock(
            return_value=httpx.Response(200, json={"id": "u1", "email": "a@x.com",
                                                   "role": "member"})
        )
        Users(SyncHTTPClient(_cfg())).update("u1", role_id="ev-datapro")
        assert _body(route) == {"role_id": "ev-datapro"}

    @respx.mock
    def test_create_with_role_id_does_not_default_role(self) -> None:
        route = respx.post(f"{BASE}/users").mock(
            return_value=httpx.Response(200, json={"id": "u1", "email": "a@x.com",
                                                   "role": "admin"})
        )
        users = Users(SyncHTTPClient(_cfg()))
        users.create(email="a@x.com", role_id="role_admins")
        users.create(email="b@x.com")
        users.create(email="c@x.com", role="guest")
        # A defaulted "member" would contradict an Admin-seat custom role.
        assert _body(route, 0) == {"email": "a@x.com", "role_id": "role_admins"}
        assert _body(route, 1) == {"email": "b@x.com", "role": "member"}
        assert _body(route, 2) == {"email": "c@x.com", "role": "guest"}

    @respx.mock
    async def test_async_update_and_get_or_create(self) -> None:
        patch = respx.patch(f"{BASE}/users/u1").mock(
            return_value=httpx.Response(200, json={"id": "u1", "email": "a@x.com",
                                                   "role": "guest"})
        )
        put = respx.put(f"{BASE}/users/external/ext1").mock(
            return_value=httpx.Response(200, json={"id": "u2", "email": "b@x.com",
                                                   "role": "member"})
        )
        users = AsyncUsers(AsyncHTTPClient(_cfg()))
        await users.update("u1", role="guest", role_id="viewer-plus")
        await users.get_or_create(external_id="ext1", role_id="viewer-plus")
        assert _body(patch) == {"role": "guest", "role_id": "viewer-plus"}
        assert _body(put) == {"role_id": "viewer-plus"}

    @respx.mock
    def test_cli_user_update_role_id_surfaces_server_refusal(self) -> None:
        route = respx.patch(f"{CLI_BASE}/users/u1").mock(
            return_value=httpx.Response(404, json={"error": {
                "code": "role_not_found",
                "message": "No role 'nope' in this organization.",
            }})
        )
        result = runner.invoke(
            main_app, [*_GLOBAL, "user", "update", "u1", "--role-id", "nope"]
        )
        assert result.exit_code != 0
        assert _body(route) == {"role_id": "nope"}
        assert "No role 'nope'" in result.output


# ═══ Settings + flags ═════════════════════════════════════════════════════


class TestSettingsAndFlags:
    @respx.mock
    def test_sdk(self) -> None:
        respx.get(f"{BASE}/settings/context").mock(
            return_value=httpx.Response(200, json={"glossary": "ARR = annual"})
        )
        respx.get(f"{BASE}/flags").mock(
            return_value=httpx.Response(200, json={"data": {"a": True, "b": False}})
        )
        http = SyncHTTPClient(_cfg())
        assert Settings(http).get_context() == {"glossary": "ARR = annual"}
        assert Flags(http).list() == {"a": True, "b": False}

    @respx.mock
    async def test_async_sdk(self) -> None:
        respx.get(f"{BASE}/settings/context").mock(
            return_value=httpx.Response(200, json={"glossary": "x"})
        )
        respx.get(f"{BASE}/flags").mock(
            return_value=httpx.Response(200, json={"data": {"a": 3}})
        )
        http = AsyncHTTPClient(_cfg())
        assert await AsyncSettings(http).get_context() == {"glossary": "x"}
        assert await AsyncFlags(http).list() == {"a": 3}

    @respx.mock
    def test_cli(self) -> None:
        respx.get(f"{CLI_BASE}/settings/context").mock(
            return_value=httpx.Response(200, json={
                "analysis_preferences": "Fiscal year starts in July.",
                "glossary": "",
            })
        )
        respx.get(f"{CLI_BASE}/flags").mock(
            return_value=httpx.Response(200, json={"data": {
                "mcp_connectors": True, "dashboard_vision": False,
            }})
        )
        ctx_out = runner.invoke(main_app, [*_GLOBAL, "settings", "context"])
        assert ctx_out.exit_code == 0, ctx_out.output
        assert "Fiscal year starts in July." in ctx_out.output
        assert "glossary" not in ctx_out.output  # empty fields hidden
        flags_out = runner.invoke(
            main_app, [*_GLOBAL, "--json", "flags", "list", "--on"]
        )
        assert json.loads(flags_out.output) == {"mcp_connectors": True}


# ═══ Workspace sharing ════════════════════════════════════════════════════


class TestWorkspaceSharing:
    @respx.mock
    def test_sdk_round_trip(self) -> None:
        url = f"{BASE}/sharing/workspace"
        lst = respx.get(url).mock(return_value=httpx.Response(
            200,
            json={"data": [{"workspace_id": "workspace_fin", "relation": "viewer"}]},
        ))
        post = respx.post(url).mock(return_value=httpx.Response(200, json={"ok": True}))
        delete = respx.delete(url).mock(return_value=httpx.Response(200, json={}))
        sharing = Sharing(SyncHTTPClient(_cfg()))
        shares = sharing.list_workspace_shares("collection", "coll_1")
        assert shares[0]["relation"] == "viewer"
        sharing.share_workspace(
            "collection", "coll_1", "workspace_fin", relation="editor"
        )
        sharing.unshare_workspace("collection", "coll_1", "workspace_fin")
        assert lst.calls[0].request.url.params["resource_type"] == "collection"
        assert _body(post) == {"resource_type": "collection", "resource_id": "coll_1",
                               "workspace_id": "workspace_fin", "relation": "editor"}
        assert _body(delete) == {"resource_type": "collection", "resource_id": "coll_1",
                                 "workspace_id": "workspace_fin"}

    @respx.mock
    async def test_async_parity(self) -> None:
        url = f"{BASE}/sharing/workspace"
        respx.get(url).mock(return_value=httpx.Response(200, json={"data": []}))
        post = respx.post(url).mock(return_value=httpx.Response(200, json={}))
        respx.delete(url).mock(return_value=httpx.Response(204))
        sharing = AsyncSharing(AsyncHTTPClient(_cfg()))
        assert await sharing.list_workspace_shares("site", "s1") == []
        await sharing.share_workspace("site", "s1", "repo_default")
        assert await sharing.unshare_workspace("site", "s1", "repo_default") == {}
        assert _body(post)["relation"] == "viewer"

    @respx.mock
    def test_cli_add_resolves_slug_and_passes_type_through(self) -> None:
        respx.get(f"{CLI_BASE}/workspaces").mock(
            return_value=httpx.Response(200, json={"data": _WS})
        )
        post = respx.post(f"{CLI_BASE}/sharing/workspace").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = runner.invoke(main_app, [
            *_GLOBAL, "share", "workspace", "add", "kpi", "kpi_1",
            "--to", "finance", "--relation", "editor",
        ])
        assert result.exit_code == 0, result.output
        assert _body(post) == {"resource_type": "kpi", "resource_id": "kpi_1",
                               "workspace_id": "workspace_fin", "relation": "editor"}

    @respx.mock
    def test_cli_surfaces_the_servers_refusal(self) -> None:
        respx.post(f"{CLI_BASE}/sharing/workspace").mock(
            return_value=httpx.Response(422, json={"error": {
                "message": "resource_type must be one of: source, project",
            }})
        )
        result = runner.invoke(main_app, [
            *_GLOBAL, "share", "workspace", "add", "kpi", "k1", "--to", "repo_default",
        ])
        assert result.exit_code != 0
        assert "must be one of: source, project" in result.output

    @respx.mock
    def test_cli_project_add_workspace_maps_edit_to_editor(self) -> None:
        post = respx.post(f"{CLI_BASE}/sharing/workspace").mock(
            return_value=httpx.Response(200, json={})
        )
        result = runner.invoke(main_app, [
            *_GLOBAL, "share", "project", "add", "p1",
            "--workspace", "repo_default", "--permission", "edit",
        ])
        assert result.exit_code == 0, result.output
        assert _body(post) == {"resource_type": "project", "resource_id": "p1",
                               "workspace_id": "repo_default", "relation": "editor"}

    @respx.mock
    def test_cli_remove_and_list(self) -> None:
        url = f"{CLI_BASE}/sharing/workspace"
        delete = respx.delete(url).mock(return_value=httpx.Response(200, json={}))
        respx.get(url).mock(return_value=httpx.Response(200, json={"data": [
            {"workspace_id": "repo_default", "relation": "viewer"},
        ]}))
        removed = runner.invoke(main_app, [
            *_GLOBAL, "share", "workspace", "remove", "source", "s1",
            "--from", "repo_default",
        ])
        assert removed.exit_code == 0, removed.output
        assert "relation" not in _body(delete)
        listed = runner.invoke(main_app, [
            *_GLOBAL, "share", "workspace", "list", "source", "s1",
        ])
        assert "repo_default" in listed.output


# ═══ Library SDK ══════════════════════════════════════════════════════════


class TestLibrarySdk:
    @respx.mock
    def test_move_facts_kinds(self) -> None:
        move = respx.post(f"{BASE}/library/nodes/fact_1/move").mock(
            return_value=httpx.Response(200, json={
                "data": {"id": "fact_1", "workspace_id": "workspace_fin"},
                "library_id": "lib_1",
            })
        )
        facts = respx.get(f"{BASE}/library/facts").mock(
            return_value=httpx.Response(200, json={"data": [
                {"_id": "fact_1", "name": "Rule", "node_kind": "Fact"},
            ], "has_more": False})
        )
        respx.get(f"{BASE}/library/fact-kinds").mock(
            return_value=httpx.Response(200, json={"data": ["rule", "definition"]})
        )
        lib = Library(SyncHTTPClient(_cfg()))
        moved = lib.move_node("fact_1", "workspace_fin")
        assert moved["workspace_id"] == "workspace_fin"
        assert _body(move) == {"workspace_id": "workspace_fin"}
        listed = lib.list_facts(library_id="lib_1", workspace_id="workspace_fin")
        assert listed.results[0].id == "fact_1"
        assert facts.calls[0].request.url.params["workspace_id"] == "workspace_fin"
        assert lib.fact_kinds() == ["rule", "definition"]

    @respx.mock
    def test_list_facts_accepts_the_library_envelope(self) -> None:
        respx.get(f"{BASE}/library/facts").mock(return_value=httpx.Response(200, json={
            "data": {"results": [{"id": "f1", "name": "n", "node_kind": "Fact"}]},
            "library_id": "lib_1",
        }))
        result = Library(SyncHTTPClient(_cfg())).list_facts()
        assert result.library_id == "lib_1"
        assert result.results[0].id == "f1"

    @respx.mock
    def test_creates_send_workspace_id_and_fact_warnings_parse(self) -> None:
        fact = respx.post(f"{BASE}/library/facts").mock(
            return_value=httpx.Response(200, json={
                "id": "f1", "name": "n", "statement": "s", "fact_kind": "rule",
                "library_id": "lib_1", "workspace_id": "workspace_fin",
                "warnings": [{"code": "targets_not_visible", "node_ids": ["src_9"],
                              "message": "src_9 is not visible from Finance"}],
            })
        )
        kpi = respx.post(f"{BASE}/library/kpis").mock(
            return_value=httpx.Response(200, json={"id": "kpi_1"})
        )
        coll = respx.post(f"{BASE}/library/collections").mock(
            return_value=httpx.Response(200, json={"id": "coll_1"})
        )
        q = respx.post(f"{BASE}/library/questions/refining").mock(
            return_value=httpx.Response(200, json={
                "id": "q1", "name": "n", "node_kind": "RefiningQuestion",
                "library_id": "lib_1",
            })
        )
        lib = Library(SyncHTTPClient(_cfg()))
        out = lib.record_fact(library_id="lib_1", statement="s", fact_kind="rule",
                              workspace_id="workspace_fin")
        lib.create_kpi(library_id="lib_1", name="ARR", workspace_id="workspace_fin")
        lib.create_collection(library_id="lib_1", name="Rev")
        lib.create_refining_question(library_id="lib_1", name="n", question_text="q",
                                     workspace_id="workspace_fin")
        assert out.warnings[0]["code"] == "targets_not_visible"
        assert _body(fact)["workspace_id"] == "workspace_fin"
        assert _body(kpi)["workspace_id"] == "workspace_fin"
        assert "workspace_id" not in _body(coll)
        assert _body(q)["workspace_id"] == "workspace_fin"

    @respx.mock
    async def test_async_parity(self) -> None:
        respx.post(f"{BASE}/library/nodes/k1/move").mock(
            return_value=httpx.Response(200, json={"id": "k1", "workspace_id": "w"})
        )
        respx.get(f"{BASE}/library/facts").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/library/fact-kinds").mock(
            return_value=httpx.Response(200, json={"data": ["rule"]})
        )
        anchor = respx.post(f"{BASE}/library/questions/anchor").mock(
            return_value=httpx.Response(200, json={
                "id": "q1", "name": "n", "node_kind": "AnchorQuestion",
                "library_id": "lib_1",
            })
        )
        lib = AsyncLibrary(AsyncHTTPClient(_cfg()))
        assert (await lib.move_node("k1", "w"))["workspace_id"] == "w"
        assert (await lib.list_facts()).results == []
        assert await lib.fact_kinds() == ["rule"]
        await lib.create_anchor_question(library_id="lib_1", name="n",
                                         question_text="q", workspace_id="w")
        assert _body(anchor)["workspace_id"] == "w"


# ═══ Library CLI ══════════════════════════════════════════════════════════


def _use_library(lib_id: str = "lib_1") -> None:
    result = runner.invoke(main_app, [*_GLOBAL, "library", "use", lib_id])
    assert result.exit_code == 0, result.output


class TestLibraryContextScoping:
    def test_active_library_is_per_org(self, _isolated: Path) -> None:
        _use_library("lib_org1")
        data = json.loads((_isolated / "library_context.json").read_text())
        assert data["scopes"] == {f"{CLI_HOST}|org_1": {"library_id": "lib_org1"}}

        other_org = [
            "--api-key", "qk_test123456", "--org-id", "org_2", "--host", CLI_HOST,
        ]
        result = runner.invoke(main_app, [*other_org, "library", "status"])
        assert result.exit_code == 1
        assert "No active library for this organization" in result.output

    @respx.mock
    def test_legacy_global_file_is_offered_not_adopted(self, _isolated: Path) -> None:
        (_isolated / "library_context.json").write_text(
            json.dumps({"library_id": "lib_old", "chat_id::lib_old": "c1"})
        )
        result = runner.invoke(main_app, [*_GLOBAL, "library", "status"])
        assert result.exit_code == 1
        assert "querri library use lib_old" in result.output

        _use_library("lib_new")
        data = json.loads((_isolated / "library_context.json").read_text())
        assert data["legacy"]["library_id"] == "lib_old"
        assert data["scopes"][f"{CLI_HOST}|org_1"]["library_id"] == "lib_new"


class TestLibraryCli:
    @respx.mock
    def test_create_collection_sends_the_active_workspace(self) -> None:
        _use_library()
        route = respx.post(f"{CLI_BASE}/library/collections").mock(
            return_value=httpx.Response(200, json={"id": "coll_1", "name": "Rev"})
        )
        result = runner.invoke(main_app, [
            *_GLOBAL, "--workspace", "workspace_fin",
            "library", "create-collection", "Rev",
        ])
        assert result.exit_code == 0, result.output
        assert _body(route)["workspace_id"] == "workspace_fin"
        assert route.calls[0].request.headers["X-Querri-Workspace"] == "workspace_fin"

    @respx.mock
    def test_move_resolves_workspace_slug(self) -> None:
        respx.get(f"{CLI_BASE}/workspaces").mock(
            return_value=httpx.Response(200, json={"data": _WS})
        )
        move = respx.post(f"{CLI_BASE}/library/nodes/fact_1/move").mock(
            return_value=httpx.Response(200, json={"id": "fact_1",
                                                   "workspace_id": "workspace_fin"})
        )
        result = runner.invoke(main_app, [
            *_GLOBAL, "library", "move", "fact_1", "--to", "Finance",
        ])
        assert result.exit_code == 0, result.output
        assert _body(move) == {"workspace_id": "workspace_fin"}

    @respx.mock
    def test_facts_and_fact_kinds(self) -> None:
        _use_library()
        respx.get(f"{CLI_BASE}/library/facts").mock(
            return_value=httpx.Response(200, json={"data": [
                {"id": "fact_1", "name": "Net revenue rule", "summary": "Excl. tax",
                 "node_kind": "Fact"},
            ]})
        )
        respx.get(f"{CLI_BASE}/library/fact-kinds").mock(
            return_value=httpx.Response(200, json={"data": ["rule", "definition"]})
        )
        facts = runner.invoke(main_app, [*_GLOBAL, "library", "facts"])
        assert facts.exit_code == 0, facts.output
        assert "Net revenue rule" in facts.output
        kinds = runner.invoke(main_app, [*_GLOBAL, "library", "fact-kinds"])
        assert kinds.output.split() == ["rule", "definition"]

    @respx.mock
    def test_record_fact_rejects_unknown_kind_with_the_list(self) -> None:
        _use_library()
        respx.get(f"{CLI_BASE}/library/fact-kinds").mock(
            return_value=httpx.Response(200, json={"data": ["rule", "definition"]})
        )
        post = respx.post(f"{CLI_BASE}/library/facts")
        result = runner.invoke(main_app, [
            *_GLOBAL, "library", "record-fact", "x", "--kind", "timing_note",
        ])
        assert result.exit_code == 1
        assert "Valid kinds: rule, definition" in result.output
        assert not post.called

    @respx.mock
    def test_record_fact_canonicalises_kind_and_prints_warnings(self) -> None:
        _use_library()
        respx.get(f"{CLI_BASE}/library/fact-kinds").mock(
            return_value=httpx.Response(200, json={"data": ["rule", "definition"]})
        )
        post = respx.post(f"{CLI_BASE}/library/facts").mock(
            return_value=httpx.Response(200, json={
                "id": "f1", "name": "n", "statement": "s", "fact_kind": "rule",
                "library_id": "lib_1",
                "warnings": [{"code": "targets_not_visible", "node_ids": ["src_9"],
                              "message": "Not visible from this workspace"}],
            })
        )
        result = runner.invoke(main_app, [
            *_GLOBAL, "library", "record-fact", "s", "--kind", "RULE", "-a", "src_9",
        ])
        assert result.exit_code == 0, result.output
        assert _body(post)["fact_kind"] == "rule"
        assert "warning: Not visible from this workspace [src_9]" in result.output

    def test_record_fact_help_names_the_real_kinds(self) -> None:
        result = runner.invoke(main_app, ["library", "record-fact", "--help"])
        assert "definition" in result.output and "fact-kinds" in result.output

    @respx.mock
    def test_kpi_create_matches_categories_any_case(self) -> None:
        _use_library()
        respx.get(f"{CLI_BASE}/library/kpi-categories").mock(
            return_value=httpx.Response(200, json={"data": {"results": [
                {"id": "c1", "name": "Efficiency"}, {"id": "c2", "name": "Growth"},
            ]}, "library_id": "lib_1"})
        )
        kpis = respx.post(f"{CLI_BASE}/library/kpis").mock(
            return_value=httpx.Response(200, json={"id": "kpi_1", "name": "ARR"})
        )
        ok = runner.invoke(main_app, [
            *_GLOBAL, "library", "kpi-create", "ARR", "-c", "efficiency",
        ])
        assert ok.exit_code == 0, ok.output
        assert _body(kpis)["categories"] == ["Efficiency"]
        bad = runner.invoke(main_app, [
            *_GLOBAL, "library", "kpi-create", "ARR", "-c", "speed",
        ])
        assert bad.exit_code == 1
        assert "Valid: Efficiency, Growth" in bad.output
        assert kpis.call_count == 1

    def test_kpi_create_help_says_build_a_view_for_breakdowns(self) -> None:
        result = runner.invoke(main_app, ["library", "kpi-create", "--help"])
        assert "View" in result.output and "breakdown" in result.output

    @respx.mock
    def test_get_view_node_shows_build_state(self) -> None:
        respx.get(f"{CLI_BASE}/library/nodes/view_1").mock(
            return_value=httpx.Response(200, json={
                "_id": "view_1", "name": "orders_by_month", "node_kind": "ViewStub",
                "library_id": "lib_1", "tenant_id": "org_1",
                "workspace_id": "workspace_fin",
                "build": {"status": "ready", "row_count": 4210},
                "shared_to": [{"workspace_id": "repo_default", "relation": "viewer"}],
            })
        )
        result = runner.invoke(main_app, [*_GLOBAL, "library", "get", "view_1"])
        assert result.exit_code == 0, result.output
        for text in ("ready", "4210", "workspace_fin", "repo_default (viewer)"):
            assert text in result.output

    @respx.mock
    def test_view_build_resolves_names(self) -> None:
        _use_library()

        def _nodes(request: httpx.Request) -> httpx.Response:
            kind = request.url.params["node_kind"]
            rows = {
                "Collection": [{"id": "coll_1", "name": "Revenue", "node_kind": kind}],
                "SourceStub": [
                    {"id": "src_1", "name": "Orders 2026", "node_kind": kind},
                    {"id": "src_2", "name": "customers", "node_kind": kind},
                ],
                "ViewStub": [],
            }[kind]
            return httpx.Response(200, json={"data": {"results": rows},
                                             "library_id": "lib_1"})

        respx.get(f"{CLI_BASE}/library/nodes").mock(side_effect=_nodes)
        build = respx.post(f"{CLI_BASE}/library/collections/coll_1/views").mock(
            return_value=_sse_stream([{"type": "data-view-built",
                                       "data": {"view_uuid": "v1", "status": "ok"}}])
        )
        result = runner.invoke(main_app, [
            *_GLOBAL, "library", "view-build", "revenue",
            "-s", "orders 2026", "-s", "CUSTOMERS", "-s", "src_raw_id",
        ])
        assert result.exit_code == 0, result.output
        assert _body(build)["source_node_ids"] == ["src_1", "src_2", "src_raw_id"]

    @respx.mock
    def test_view_build_refuses_an_ambiguous_name(self) -> None:
        _use_library()

        def _nodes(request: httpx.Request) -> httpx.Response:
            kind = request.url.params["node_kind"]
            rows = [] if kind != "SourceStub" else [
                {"id": "src_a", "name": "Orders", "node_kind": kind},
                {"id": "src_b", "name": "orders", "node_kind": kind},
            ]
            return httpx.Response(200, json={"data": {"results": rows}})

        respx.get(f"{CLI_BASE}/library/nodes").mock(side_effect=_nodes)
        build = respx.post(url__regex=r".*/views$")
        result = runner.invoke(main_app, [
            *_GLOBAL, "library", "view-build", "coll_1", "-s", "orders",
        ])
        assert result.exit_code == 1
        assert "ambiguous" in result.output
        assert "src_a" in result.output and "src_b" in result.output
        assert not build.called


# ═══ Library chat choice cards ════════════════════════════════════════════

_CARD = {
    "presented": True,
    "question": "Build this view?",
    "options": [{"label": "Build the view"}, {"label": "Change the plan"},
                {"label": "Not now"}],
    "multi_select": False,
    "allow_other": True,
    "review": [{"label": "View", "value": "one row per order"}],
    "confirm_label": "Build the view",
}


def _card_turn() -> httpx.Response:
    return _sse_stream([
        {"type": "text-delta", "id": "t1", "delta": "Orders has 4,210 rows."},
        {"type": "tool-input-available", "toolCallId": "tc1", "toolName": "ask_choices",
         "input": {}},
        {"type": "tool-output-available", "toolCallId": "tc1", "output": _CARD},
        {"type": "text-delta", "id": "t2", "delta": "Let me know."},
        {"type": "data-librarian", "data": {"chat_id": "chat_1",
                                            "assistant_message": "Let me know."}},
    ])


def _done_turn() -> httpx.Response:
    return _sse_stream([
        {"type": "text-delta", "id": "t3", "delta": "Built orders_by_month."},
        {"type": "data-librarian", "data": {
            "chat_id": "chat_1", "assistant_message": "Built orders_by_month.",
        }},
    ])


class TestLibraryChatChoices:
    @respx.mock
    def test_prints_card_and_full_narrative(self) -> None:
        _use_library()
        respx.post(f"{CLI_BASE}/library/chat").mock(return_value=_card_turn())
        result = runner.invoke(main_app, [*_GLOBAL, "library", "chat", "orders view"])
        assert result.exit_code == 0, result.output
        # Both segments, not only assistant_message's last-turn text.
        assert "Orders has 4,210 rows." in result.output
        assert "? Build this view?" in result.output
        assert "1. Build the view" in result.output
        assert "View: one row per order" in result.output
        assert "--answer" in result.output

    @respx.mock
    def test_answer_by_number_sends_the_label_in_the_same_chat(self) -> None:
        _use_library()
        chat = respx.post(f"{CLI_BASE}/library/chat").mock(
            side_effect=[_card_turn(), _done_turn()]
        )
        result = runner.invoke(main_app, [
            *_GLOBAL, "library", "chat", "orders view", "--answer", "1",
        ])
        assert result.exit_code == 0, result.output
        second = _body(chat, 1)
        assert second["message"] == "Build the view"
        assert second["chat_id"] == "chat_1"
        assert "Built orders_by_month." in result.output

    @respx.mock
    def test_answer_out_of_range_is_refused(self) -> None:
        _use_library()
        chat = respx.post(f"{CLI_BASE}/library/chat").mock(return_value=_card_turn())
        result = runner.invoke(main_app, [
            *_GLOBAL, "library", "chat", "x", "--answer", "7",
        ])
        assert result.exit_code == 1
        assert "matches no option" in result.output
        assert chat.call_count == 1

    @respx.mock
    def test_json_emits_the_card_and_turns_with_answer(self) -> None:
        _use_library()
        respx.post(f"{CLI_BASE}/library/chat").mock(
            side_effect=[_card_turn(), _card_turn(), _done_turn()]
        )
        one = runner.invoke(main_app, [*_GLOBAL, "--json", "library", "chat", "x"])
        payload = json.loads(one.output)
        assert payload["choices"]["confirm_label"] == "Build the view"
        assert payload["narrative"] == "Orders has 4,210 rows.\n\nLet me know."
        two = runner.invoke(main_app, [
            *_GLOBAL, "--json", "library", "chat", "x", "--answer", "not now",
        ])
        turns = json.loads(two.output)["turns"]
        assert len(turns) == 2
        assert turns[1]["choices"] is None

    @respx.mock
    def test_interactive_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _use_library()
        monkeypatch.setattr(library_cli, "_is_interactive", lambda: True)
        chat = respx.post(f"{CLI_BASE}/library/chat").mock(
            side_effect=[_card_turn(), _done_turn()]
        )
        result = runner.invoke(
            main_app, [*_GLOBAL, "library", "chat", "x"], input="bogus 9\n2\n"
        )
        assert result.exit_code == 0, result.output
        # Free text is allowed on this card, so the first reply is sent as-is.
        assert _body(chat, 1)["message"] == "bogus 9"


def test_interactive_prompt_resolves_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(["9", "3"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    card = {**_CARD, "allow_other": False}
    assert library_cli._prompt_choice(card) == "Not now"
