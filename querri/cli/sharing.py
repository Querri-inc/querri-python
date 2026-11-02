"""querri share — manage resource sharing and permissions."""

from __future__ import annotations

import sys

import typer

from querri.cli._context import _resolve_workspace, get_client
from querri.cli._output import (
    handle_api_error,
    print_error,
    print_json,
    print_success,
    print_table,
)

sharing_app = typer.Typer(
    name="share",
    help="Share projects, dashboards, and sources with users or workspaces.",
    no_args_is_help=True,
)

share_project_app = typer.Typer(
    name="project", help="Share projects.", no_args_is_help=True
)
share_dashboard_app = typer.Typer(
    name="dashboard", help="Share dashboards.", no_args_is_help=True
)
share_source_app = typer.Typer(
    name="source", help="Share data sources.", no_args_is_help=True
)

sharing_app.add_typer(share_project_app, name="project")
sharing_app.add_typer(share_dashboard_app, name="dashboard")
share_workspace_app = typer.Typer(
    name="workspace",
    help=(
        "Share any item with a whole workspace (project, dashboard, source, "
        "connector, site, collection — whatever the server shares)."
    ),
    no_args_is_help=True,
)

sharing_app.add_typer(share_source_app, name="source")
sharing_app.add_typer(share_workspace_app, name="workspace")


# ── Helpers ─────────────────────────────────────────────────────────────────


def _resolve_arg(value: str | None, name: str, prompt: str, usage: str) -> str:
    """Resolve a possibly-missing CLI argument via interactive prompt or error."""
    if value:
        return value
    if sys.stdin.isatty():
        value = input(prompt).strip()
        if not value:
            print_error(f"{name} is required.")
            raise typer.Exit(code=1)
        return value
    else:
        print_error(f"Missing required argument {name}. Usage: {usage}")
        raise typer.Exit(code=1)


_RELATION_BY_PERMISSION = {"view": "viewer", "edit": "editor"}


def _share_with_workspace(
    ctx: typer.Context,
    resource_type: str,
    resource_id: str,
    workspace: str,
    permission_or_relation: str,
) -> None:
    """Share one item with a workspace; ``view``/``edit`` map to the
    workspace grant's ``viewer``/``editor``."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    workspace_id = _resolve_workspace(client, workspace, obj)
    relation = _RELATION_BY_PERMISSION.get(
        permission_or_relation, permission_or_relation
    )
    try:
        result = client.sharing.share_workspace(
            resource_type, resource_id, workspace_id, relation=relation
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    if obj.get("json"):
        print_json(result)
    else:
        print_success(
            f"Shared {resource_type} {resource_id} with workspace "
            f"{workspace_id} ({relation})"
        )


# ── Project sharing ──────────────────────────────────────────────────────────


@share_project_app.command("add")
def add_project_share(
    ctx: typer.Context,
    project_id: str | None = typer.Argument(None, help="Project ID."),
    user_id: str | None = typer.Option(
        None, "--user-id", help="User ID to share with."
    ),
    permission: str = typer.Option(
        "view", "--permission", help="Permission: view or edit."
    ),
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Share with a whole workspace (id, slug or name) instead of a user.",
    ),
) -> None:
    """Share a project with a user."""
    project_id = _resolve_arg(
        project_id,
        "PROJECT_ID",
        "Project ID: ",
        "querri share project add PROJECT_ID --user-id USER_ID",
    )
    if workspace:
        _share_with_workspace(ctx, "project", project_id, workspace, permission)
        return
    user_id = _resolve_arg(
        user_id,
        "USER_ID",
        "User ID: ",
        "querri share project add PROJECT_ID --user-id USER_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.sharing.share_project(
            project_id, user_id=user_id, permission=permission
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Shared project {project_id} with user {user_id} ({permission})")


@share_project_app.command("remove")
def remove_project_share(
    ctx: typer.Context,
    project_id: str | None = typer.Argument(None, help="Project ID."),
    user_id: str | None = typer.Argument(None, help="User ID to remove."),
) -> None:
    """Revoke a user's access to a project."""
    project_id = _resolve_arg(
        project_id,
        "PROJECT_ID",
        "Project ID: ",
        "querri share project remove PROJECT_ID USER_ID",
    )
    user_id = _resolve_arg(
        user_id,
        "USER_ID",
        "User ID: ",
        "querri share project remove PROJECT_ID USER_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.sharing.revoke_project_share(project_id, user_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json({"project_id": project_id, "user_id": user_id, "revoked": True})
    else:
        print_success(f"Revoked access to project {project_id} for user {user_id}")


@share_project_app.command("list")
def list_project_shares(
    ctx: typer.Context,
    project_id: str | None = typer.Argument(None, help="Project ID."),
) -> None:
    """List users who have access to a project."""
    project_id = _resolve_arg(
        project_id,
        "PROJECT_ID",
        "Project ID: ",
        "querri share project list PROJECT_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.sharing.list_project_shares(project_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json([s.model_dump(mode="json") for s in items])
    else:
        print_table(
            items,
            [("user_id", "User ID"), ("permission", "Permission")],
            ctx=ctx,
        )


# ── Dashboard sharing ────────────────────────────────────────────────────────


@share_dashboard_app.command("add")
def add_dashboard_share(
    ctx: typer.Context,
    dashboard_id: str | None = typer.Argument(None, help="Dashboard ID."),
    user_id: str | None = typer.Option(
        None, "--user-id", help="User ID to share with."
    ),
    permission: str = typer.Option(
        "view", "--permission", help="Permission: view or edit."
    ),
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Share with a whole workspace (id, slug or name) instead of a user.",
    ),
) -> None:
    """Share a dashboard with a user."""
    dashboard_id = _resolve_arg(
        dashboard_id,
        "DASHBOARD_ID",
        "Dashboard ID: ",
        "querri share dashboard add DASHBOARD_ID --user-id USER_ID",
    )
    if workspace:
        _share_with_workspace(ctx, "dashboard", dashboard_id, workspace, permission)
        return
    user_id = _resolve_arg(
        user_id,
        "USER_ID",
        "User ID: ",
        "querri share dashboard add DASHBOARD_ID --user-id USER_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.sharing.share_dashboard(
            dashboard_id, user_id=user_id, permission=permission
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result)
    else:
        print_success(
            f"Shared dashboard {dashboard_id} with user {user_id} ({permission})"
        )


@share_dashboard_app.command("remove")
def remove_dashboard_share(
    ctx: typer.Context,
    dashboard_id: str | None = typer.Argument(None, help="Dashboard ID."),
    user_id: str | None = typer.Argument(None, help="User ID to remove."),
) -> None:
    """Revoke a user's access to a dashboard."""
    dashboard_id = _resolve_arg(
        dashboard_id,
        "DASHBOARD_ID",
        "Dashboard ID: ",
        "querri share dashboard remove DASHBOARD_ID USER_ID",
    )
    user_id = _resolve_arg(
        user_id,
        "USER_ID",
        "User ID: ",
        "querri share dashboard remove DASHBOARD_ID USER_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.sharing.revoke_dashboard_share(dashboard_id, user_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json({"dashboard_id": dashboard_id, "user_id": user_id, "revoked": True})
    else:
        print_success(f"Revoked access to dashboard {dashboard_id} for user {user_id}")


@share_dashboard_app.command("list")
def list_dashboard_shares(
    ctx: typer.Context,
    dashboard_id: str | None = typer.Argument(None, help="Dashboard ID."),
) -> None:
    """List users who have access to a dashboard."""
    dashboard_id = _resolve_arg(
        dashboard_id,
        "DASHBOARD_ID",
        "Dashboard ID: ",
        "querri share dashboard list DASHBOARD_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.sharing.list_dashboard_shares(dashboard_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json([s.model_dump(mode="json") for s in items])
    else:
        print_table(
            items,
            [("user_id", "User ID"), ("permission", "Permission")],
            ctx=ctx,
        )


# ── Source sharing ────────────────────────────────────────────────────────────
# Note: Source sharing SDK methods are not yet in the SDK.
# These commands call the HTTP client directly.


@share_source_app.command("add")
def add_source_share(
    ctx: typer.Context,
    source_id: str | None = typer.Argument(None, help="Source ID."),
    user_id: str | None = typer.Option(
        None, "--user-id", help="User ID to share with."
    ),
    permission: str = typer.Option(
        "view", "--permission", help="Permission: view or edit."
    ),
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Share with a whole workspace (id, slug or name) instead of a user.",
    ),
) -> None:
    """Share a data source with a user."""
    source_id = _resolve_arg(
        source_id,
        "SOURCE_ID",
        "Source ID: ",
        "querri share source add SOURCE_ID --user-id USER_ID",
    )
    if workspace:
        _share_with_workspace(ctx, "source", source_id, workspace, permission)
        return
    user_id = _resolve_arg(
        user_id,
        "USER_ID",
        "User ID: ",
        "querri share source add SOURCE_ID --user-id USER_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        resp = client._http.post(
            f"/sources/{source_id}/shares",
            json={"user_id": user_id, "permission": permission},
        )
        result = resp.json()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Shared source {source_id} with user {user_id} ({permission})")


@share_source_app.command("remove")
def remove_source_share(
    ctx: typer.Context,
    source_id: str | None = typer.Argument(None, help="Source ID."),
    user_id: str | None = typer.Argument(None, help="User ID to remove."),
) -> None:
    """Revoke a user's access to a data source."""
    source_id = _resolve_arg(
        source_id,
        "SOURCE_ID",
        "Source ID: ",
        "querri share source remove SOURCE_ID USER_ID",
    )
    user_id = _resolve_arg(
        user_id,
        "USER_ID",
        "User ID: ",
        "querri share source remove SOURCE_ID USER_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client._http.delete(f"/sources/{source_id}/shares/{user_id}")
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json({"source_id": source_id, "user_id": user_id, "revoked": True})
    else:
        print_success(f"Revoked access to source {source_id} for user {user_id}")


@share_source_app.command("list")
def list_source_shares(
    ctx: typer.Context,
    source_id: str | None = typer.Argument(None, help="Source ID."),
) -> None:
    """List users who have access to a data source."""
    source_id = _resolve_arg(
        source_id,
        "SOURCE_ID",
        "Source ID: ",
        "querri share source list SOURCE_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        resp = client._http.get(f"/sources/{source_id}/shares")
        body = resp.json()
        items = body.get("data", [])
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(items)
    else:
        print_table(
            items,
            [("user_id", "User ID"), ("permission", "Permission")],
            ctx=ctx,
        )


@share_source_app.command("org")
def org_source_share(
    ctx: typer.Context,
    source_id: str | None = typer.Argument(None, help="Source ID."),
    permission: str = typer.Option(
        "view", "--permission", help="Permission: view or edit."
    ),
    enabled: bool = typer.Option(
        True,
        "--enabled/--disable",
        help="Enable (default) or disable org-wide sharing.",
    ),
) -> None:
    """Enable or disable org-wide sharing for a data source."""
    source_id = _resolve_arg(
        source_id,
        "SOURCE_ID",
        "Source ID: ",
        "querri share source org SOURCE_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        resp = client._http.post(
            f"/sources/{source_id}/org-share",
            json={"enabled": enabled, "permission": permission},
        )
        result = resp.json()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result)
    elif result.get("org_shared"):
        print_success(f"Shared source {source_id} with organization ({permission})")
    else:
        print_success(f"Disabled org-wide sharing for source {source_id}")


# ── Workspace sharing (any resource type) ────────────────────────────────────


@share_workspace_app.command("add")
def add_workspace_share(
    ctx: typer.Context,
    resource_type: str = typer.Argument(
        ..., help="Item type: project, dashboard, source, connector, site, collection…"
    ),
    resource_id: str = typer.Argument(..., help="Item id."),
    to: str = typer.Option(..., "--to", help="Workspace (id, slug or name)."),
    relation: str = typer.Option(
        "viewer", "--relation", "-r", help="viewer (default) or editor."
    ),
) -> None:
    """Share an item with every member of a workspace. It stays homed where it
    is; the server says which types it can share."""
    _share_with_workspace(ctx, resource_type, resource_id, to, relation)


@share_workspace_app.command("remove")
def remove_workspace_share(
    ctx: typer.Context,
    resource_type: str = typer.Argument(..., help="Item type."),
    resource_id: str = typer.Argument(..., help="Item id."),
    from_: str = typer.Option(
        ..., "--from", help="Workspace to un-share from (id, slug or name)."
    ),
) -> None:
    """Stop sharing an item with a workspace."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    workspace_id = _resolve_workspace(client, from_, obj)
    try:
        result = client.sharing.unshare_workspace(
            resource_type, resource_id, workspace_id
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    if obj.get("json"):
        print_json(result or {
            "resource_type": resource_type, "resource_id": resource_id,
            "workspace_id": workspace_id, "revoked": True,
        })
    else:
        print_success(
            f"Stopped sharing {resource_type} {resource_id} with {workspace_id}"
        )


@share_workspace_app.command("list")
def list_workspace_shares(
    ctx: typer.Context,
    resource_type: str = typer.Argument(..., help="Item type."),
    resource_id: str = typer.Argument(..., help="Item id."),
) -> None:
    """List the workspaces an item is shared with."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        shares = client.sharing.list_workspace_shares(resource_type, resource_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    if obj.get("json"):
        print_json(shares)
        return
    if not shares:
        print_error(f"{resource_type} {resource_id} is not shared with a workspace.")
        return
    print_table(
        shares,
        [("workspace_id", "Workspace"), ("relation", "Relation")],
        ctx=ctx,
    )
