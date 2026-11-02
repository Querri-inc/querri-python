"""querri workspace — choose which room you are working in.

A workspace decides where new objects are homed and what the agent can see when
it searches. Everything after ``querri workspace use`` carries that claim:

    querri workspace list
    querri workspace use finance
    querri file upload q3.csv --wait      # homed in Finance
    querri project new "Q3 review"        # homed in Finance
    querri project chat -m "what changed" # searches Finance only

``querri workspace use --none`` clears it (the "Everything" position: creates go
to your personal workspace, reads are unscoped).

``list``, ``show`` and ``members`` work with an API key or a login. ``new``,
``add-member`` and ``move`` still need a signed-in user (``querri auth login``):
they have no public API route yet.
"""

from __future__ import annotations

import sys
from typing import Any

import typer

from querri.cli._context import _get_profile, _save_profile, get_client
from querri.cli._output import (
    handle_api_error,
    print_error,
    print_id,
    print_json,
    print_success,
    print_table,
)

workspace_app = typer.Typer(
    name="workspace",
    help="Workspaces — where your data and projects live.",
    no_args_is_help=True,
)


def _legacy_kind(w: dict[str, Any]) -> str:
    """``kind`` for a pre-v1 payload (``is_default`` / ``is_private`` flags)."""
    if w.get("is_default"):
        return "company"
    return "personal" if w.get("is_private") else "named"


def _rows(workspaces: list[dict[str, Any]], active: str) -> list[dict[str, str]]:
    return [
        {
            "id": str(w.get("id", "")),
            "slug": str(w.get("slug", "")),
            "name": str(w.get("name", "")),
            "kind": str(w.get("kind") or _legacy_kind(w)),
            "members": (
                "" if w.get("member_count") is None else str(w["member_count"])
            ),
            "active": "*" if w.get("id") == active else "",
        }
        for w in workspaces
    ]


@workspace_app.command("list")
def list_workspaces(ctx: typer.Context) -> None:
    """List workspaces.

    Signed in: the workspaces you can enter. With an API key: every workspace
    in the organization. Kind is personal, named, or company (the org's shared
    workspace).
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        workspaces = client.workspaces.list()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    profile = _get_profile(ctx)
    active = client.workspace_id or (
        getattr(profile, "active_workspace_id", "") if profile else ""
    )

    if obj.get("json"):
        print_json(workspaces)
        return
    if obj.get("quiet"):
        for w in workspaces:
            print_id(str(w.get("id", "")))
        return
    if not workspaces:
        print_error("No workspaces. That should not happen — report it.")
        raise typer.Exit(code=1)

    print_table(
        _rows(workspaces, active or ""),
        [("active", ""), ("name", "Name"), ("slug", "Slug"),
         ("kind", "Kind"), ("members", "Members"), ("id", "ID")],
        ctx=ctx,
    )


@workspace_app.command("show")
def show_workspace(ctx: typer.Context) -> None:
    """Show the workspace this CLI is standing in."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    active = client.workspace_id

    if not active:
        if obj.get("json"):
            print_json({"workspace_id": None, "scope": "everything"})
            return
        print("No active workspace (Everything).", file=sys.stderr)
        print(
            "  New objects home in your personal workspace; reads are unscoped.\n"
            "  querri workspace use <slug>   # pick one",
            file=sys.stderr,
        )
        return

    try:
        ws = client.workspaces.get(active)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if ws is None:
        # Stored id that no longer resolves — say so rather than carrying on
        # sending a claim the server will ignore.
        msg = (
            f"Active workspace {active!r} is not one you can enter "
            "(deleted, or your membership was removed)."
        )
        if obj.get("json"):
            print_json({"workspace_id": active, "enterable": False, "error": msg})
        else:
            print_error(msg + "\n  querri workspace use <slug>")
        raise typer.Exit(code=1)

    if obj.get("json"):
        print_json(ws)
        return
    print_table(_rows([ws], active),
                [("name", "Name"), ("slug", "Slug"), ("kind", "Kind"), ("id", "ID")],
                ctx=ctx)


@workspace_app.command("use")
def use_workspace(
    ctx: typer.Context,
    name_or_id: str | None = typer.Argument(
        None, help="Workspace slug, name, or id."
    ),
    none: bool = typer.Option(
        False, "--none", help="Clear the active workspace (Everything)."
    ),
) -> None:
    """Set the active workspace for subsequent commands.

    Stored in the auth profile, so it persists across invocations. ``--workspace``
    on a single command overrides it without changing what is stored.
    """
    obj = ctx.ensure_object(dict)
    profile = _get_profile(ctx)
    if profile is None:
        print_error("Not logged in. Run 'querri auth login'.")
        raise typer.Exit(code=2)

    if none:
        profile.active_workspace_id = ""
        profile.active_workspace_name = ""
        _save_profile(ctx, profile)
        if obj.get("json"):
            print_json({"workspace_id": None})
        else:
            print_success("Active workspace cleared (Everything).")
        return

    if not name_or_id:
        print_error("Workspace slug, name, or id required (or --none to clear).")
        raise typer.Exit(code=1)

    # Build the client WITHOUT the stored workspace so a broken stored value
    # cannot block you from setting a working one.
    obj["workspace"] = None
    saved_active = profile.active_workspace_id
    profile.active_workspace_id = ""
    client = get_client(ctx)
    profile.active_workspace_id = saved_active

    try:
        workspaces = client.workspaces.list()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    needle = name_or_id.strip().lower()
    match = None
    for w in workspaces:
        if str(w.get("id", "")).lower() == needle:
            match = w
            break
    if match is None:
        for w in workspaces:
            if str(w.get("slug", "")).lower() == needle:
                match = w
                break
    if match is None:
        for w in workspaces:
            if needle in str(w.get("name", "")).lower():
                match = w
                break
    if match is None:
        known = ", ".join(str(w.get("slug")) for w in workspaces)
        print_error(f"No workspace matches {name_or_id!r}. Available: {known}")
        raise typer.Exit(code=1)

    profile.active_workspace_id = str(match["id"])
    profile.active_workspace_name = str(match.get("name", ""))
    _save_profile(ctx, profile)

    if obj.get("json"):
        print_json(match)
    elif obj.get("quiet"):
        print_id(str(match["id"]))
    else:
        print_success(f"Active workspace: {match.get('name')} ({match.get('slug')})")


@workspace_app.command("new")
def new_workspace(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Display name."),
    slug: str | None = typer.Option(
        None, "--slug", help="URL slug (derived from name)."
    ),
    description: str = typer.Option("", "--description", "-d"),
    use: bool = typer.Option(
        False, "--use", help="Make it the active workspace after creating."
    ),
) -> None:
    """Create a workspace. Requires an organization admin.

    A new workspace is PRIVATE: you are its first member and nobody else can
    enter until you add them (``querri workspace add-member``).
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        ws = client.workspaces.create(name, slug=slug, description=description)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    ws_id = str(ws.get("_id") or ws.get("id") or "")
    if use:
        profile = _get_profile(ctx)
        if profile is not None:
            profile.active_workspace_id = ws_id
            profile.active_workspace_name = str(ws.get("name", ""))
            _save_profile(ctx, profile)

    if obj.get("json"):
        print_json(ws)
    elif obj.get("quiet"):
        print_id(ws_id)
    else:
        print_success(
            f"Created workspace {ws.get('name')} ({ws.get('slug')}) → {ws_id}"
        )
        if use:
            print_success("It is now the active workspace.")


@workspace_app.command("move")
def move_item(
    ctx: typer.Context,
    source_ids: list[str] = typer.Argument(..., help="Source/file UUIDs to re-home."),
    to: str = typer.Option(
        ..., "--to", help="Destination workspace slug, name, or id."
    ),
    transfer_ownership: bool = typer.Option(
        False,
        "--transfer-ownership",
        help="Required when the move crosses an ownership boundary.",
    ),
) -> None:
    """Re-home uploaded files into another workspace.

    Moves both copies of each item's home (the file and its data source) so it
    cannot end up in two rooms depending on which surface you arrive through.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    dest = to.strip()
    if not (dest == "repo_default" or dest.startswith("workspace_")):
        target = client.workspaces.get(dest)
        if target is None:
            for w in client.workspaces.list():
                if dest.lower() in str(w.get("name", "")).lower():
                    target = w
                    break
        if target is None:
            print_error(f"No workspace matches {to!r}.")
            raise typer.Exit(code=1)
        dest = str(target["id"])

    results = []
    failures = 0
    for sid in source_ids:
        try:
            results.append({"id": sid, **client.workspaces.move(
                sid, dest, transfer_ownership=transfer_ownership)})
        except Exception as exc:
            failures += 1
            results.append({"id": sid, "error": str(exc)})

    if obj.get("json"):
        print_json(results)
    else:
        for r in results:
            if "error" in r:
                print_error(f"{r['id']}: {r['error']}")
            elif r.get("changed"):
                print_success(f"{r['id']} → {r['workspace_id']}")
            else:
                print(f"  {r['id']} already in {r['workspace_id']}", file=sys.stderr)
    if failures:
        raise typer.Exit(code=1)


@workspace_app.command("members")
def list_members(
    ctx: typer.Context,
    workspace: str | None = typer.Argument(None, help="Workspace (default: active)."),
) -> None:
    """Show a workspace's roster."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    ws_id = workspace or client.workspace_id
    if not ws_id:
        print_error("No workspace given and none active.")
        raise typer.Exit(code=1)
    if not (ws_id == "repo_default" or ws_id.startswith("workspace_")):
        found = client.workspaces.get(ws_id)
        if found is None:
            print_error(f"No workspace matches {ws_id!r}.")
            raise typer.Exit(code=1)
        ws_id = str(found["id"])
    try:
        members = client.workspaces.members(ws_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    if obj.get("json"):
        print_json(members)
        return
    if obj.get("quiet"):
        for m in members:
            print_id(str(m.get("user_id", "")))
        return
    print_table(
        members,
        [("name", "Name"), ("email", "Email"), ("role", "Role"), ("user_id", "User")],
        ctx=ctx,
    )


@workspace_app.command("add-member")
def add_member(
    ctx: typer.Context,
    user_id: str = typer.Argument(..., help="User id to add."),
    workspace: str | None = typer.Option(
        None, "--to", help="Workspace (default: active)."
    ),
    role: str = typer.Option("member", "--role", help="member | creator | admin."),
) -> None:
    """Add someone to a workspace."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    ws_id = workspace or client.workspace_id
    if not ws_id:
        print_error("No workspace given and none active.")
        raise typer.Exit(code=1)
    if not (ws_id == "repo_default" or ws_id.startswith("workspace_")):
        found = client.workspaces.get(ws_id)
        if found is None:
            print_error(f"No workspace matches {ws_id!r}.")
            raise typer.Exit(code=1)
        ws_id = str(found["id"])
    try:
        payload = client.workspaces.add_member(ws_id, user_id, role=role)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    if obj.get("json"):
        print_json(payload)
    else:
        print_success(f"Added {user_id} to {ws_id} as {role}.")
