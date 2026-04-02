"""querri share — manage resource sharing and permissions."""

from __future__ import annotations

import sys
from typing import Optional

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    handle_api_error,
    print_error,
    print_json,
    print_success,
    print_table,
)

sharing_app = typer.Typer(
    name="sharing",
    help="Share projects, dashboards, and sources with users.",
    no_args_is_help=True,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _resolve_arg(value: Optional[str], name: str, prompt: str, usage: str) -> str:
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


# ── Project sharing ──────────────────────────────────────────────────────────


@sharing_app.command("share-project")
def share_project(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project ID."),
    user_id: Optional[str] = typer.Option(None, "--user-id", help="User ID to share with."),
    permission: str = typer.Option("view", "--permission", "-p", help="Permission: view or edit."),
) -> None:
    """Share a project with a user."""
    project_id = _resolve_arg(
        project_id, "PROJECT_ID", "Project ID: ",
        "querri share share-project PROJECT_ID --user-id USER_ID",
    )
    user_id = _resolve_arg(
        user_id, "USER_ID", "User ID: ",
        "querri share share-project PROJECT_ID --user-id USER_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.sharing.share_project(project_id, user_id=user_id, permission=permission)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Shared project {project_id} with user {user_id} ({permission})")


@sharing_app.command("revoke-project")
def revoke_project(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project ID."),
    user_id: Optional[str] = typer.Argument(None, help="User ID to revoke."),
) -> None:
    """Revoke a user's access to a project."""
    project_id = _resolve_arg(
        project_id, "PROJECT_ID", "Project ID: ",
        "querri share revoke-project PROJECT_ID USER_ID",
    )
    user_id = _resolve_arg(
        user_id, "USER_ID", "User ID: ",
        "querri share revoke-project PROJECT_ID USER_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.sharing.revoke_project_share(project_id, user_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"project_id": project_id, "user_id": user_id, "revoked": True})
    else:
        print_success(f"Revoked access to project {project_id} for user {user_id}")


@sharing_app.command("list-project")
def list_project_shares(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project ID."),
) -> None:
    """List users who have access to a project."""
    project_id = _resolve_arg(
        project_id, "PROJECT_ID", "Project ID: ",
        "querri share list-project PROJECT_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.sharing.list_project_shares(project_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json([s.model_dump(mode="json") for s in items])
    else:
        print_table(
            items,
            [("user_id", "User ID"), ("permission", "Permission")],
            ctx=ctx,
        )


# ── Dashboard sharing ────────────────────────────────────────────────────────


@sharing_app.command("share-dashboard")
def share_dashboard(
    ctx: typer.Context,
    dashboard_id: Optional[str] = typer.Argument(None, help="Dashboard ID."),
    user_id: Optional[str] = typer.Option(None, "--user-id", help="User ID to share with."),
    permission: str = typer.Option("view", "--permission", "-p", help="Permission: view or edit."),
) -> None:
    """Share a dashboard with a user."""
    dashboard_id = _resolve_arg(
        dashboard_id, "DASHBOARD_ID", "Dashboard ID: ",
        "querri share share-dashboard DASHBOARD_ID --user-id USER_ID",
    )
    user_id = _resolve_arg(
        user_id, "USER_ID", "User ID: ",
        "querri share share-dashboard DASHBOARD_ID --user-id USER_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.sharing.share_dashboard(dashboard_id, user_id=user_id, permission=permission)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Shared dashboard {dashboard_id} with user {user_id} ({permission})")


@sharing_app.command("revoke-dashboard")
def revoke_dashboard(
    ctx: typer.Context,
    dashboard_id: Optional[str] = typer.Argument(None, help="Dashboard ID."),
    user_id: Optional[str] = typer.Argument(None, help="User ID to revoke."),
) -> None:
    """Revoke a user's access to a dashboard."""
    dashboard_id = _resolve_arg(
        dashboard_id, "DASHBOARD_ID", "Dashboard ID: ",
        "querri share revoke-dashboard DASHBOARD_ID USER_ID",
    )
    user_id = _resolve_arg(
        user_id, "USER_ID", "User ID: ",
        "querri share revoke-dashboard DASHBOARD_ID USER_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.sharing.revoke_dashboard_share(dashboard_id, user_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"dashboard_id": dashboard_id, "user_id": user_id, "revoked": True})
    else:
        print_success(f"Revoked access to dashboard {dashboard_id} for user {user_id}")


@sharing_app.command("list-dashboard")
def list_dashboard_shares(
    ctx: typer.Context,
    dashboard_id: Optional[str] = typer.Argument(None, help="Dashboard ID."),
) -> None:
    """List users who have access to a dashboard."""
    dashboard_id = _resolve_arg(
        dashboard_id, "DASHBOARD_ID", "Dashboard ID: ",
        "querri share list-dashboard DASHBOARD_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.sharing.list_dashboard_shares(dashboard_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json([s.model_dump(mode="json") for s in items])
    else:
        print_table(
            items,
            [("user_id", "User ID"), ("permission", "Permission")],
            ctx=ctx,
        )


# ── Source sharing ────────────────────────────────────────────────────────────
# Note: Source sharing SDK methods (share_source, revoke_source_share,
# list_source_shares, org_share_source) are not yet in the SDK.
# These commands call the HTTP client directly.


@sharing_app.command("share-source")
def share_source(
    ctx: typer.Context,
    source_id: Optional[str] = typer.Argument(None, help="Source ID."),
    user_id: Optional[str] = typer.Option(None, "--user-id", help="User ID to share with."),
    permission: str = typer.Option("view", "--permission", "-p", help="Permission: view or edit."),
) -> None:
    """Share a data source with a user."""
    source_id = _resolve_arg(
        source_id, "SOURCE_ID", "Source ID: ",
        "querri share share-source SOURCE_ID --user-id USER_ID",
    )
    user_id = _resolve_arg(
        user_id, "USER_ID", "User ID: ",
        "querri share share-source SOURCE_ID --user-id USER_ID",
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
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Shared source {source_id} with user {user_id} ({permission})")


@sharing_app.command("revoke-source")
def revoke_source(
    ctx: typer.Context,
    source_id: Optional[str] = typer.Argument(None, help="Source ID."),
    user_id: Optional[str] = typer.Argument(None, help="User ID to revoke."),
) -> None:
    """Revoke a user's access to a data source."""
    source_id = _resolve_arg(
        source_id, "SOURCE_ID", "Source ID: ",
        "querri share revoke-source SOURCE_ID USER_ID",
    )
    user_id = _resolve_arg(
        user_id, "USER_ID", "User ID: ",
        "querri share revoke-source SOURCE_ID USER_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client._http.delete(f"/sources/{source_id}/shares/{user_id}")
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"source_id": source_id, "user_id": user_id, "revoked": True})
    else:
        print_success(f"Revoked access to source {source_id} for user {user_id}")


@sharing_app.command("list-source")
def list_source_shares(
    ctx: typer.Context,
    source_id: Optional[str] = typer.Argument(None, help="Source ID."),
) -> None:
    """List users who have access to a data source."""
    source_id = _resolve_arg(
        source_id, "SOURCE_ID", "Source ID: ",
        "querri share list-source SOURCE_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        resp = client._http.get(f"/sources/{source_id}/shares")
        body = resp.json()
        items = body.get("data", [])
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(items)
    else:
        print_table(
            items,
            [("user_id", "User ID"), ("permission", "Permission")],
            ctx=ctx,
        )


@sharing_app.command("org-share-source")
def org_share_source(
    ctx: typer.Context,
    source_id: Optional[str] = typer.Argument(None, help="Source ID."),
    permission: str = typer.Option("view", "--permission", "-p", help="Permission: view or edit."),
) -> None:
    """Share a data source with the entire organization."""
    source_id = _resolve_arg(
        source_id, "SOURCE_ID", "Source ID: ",
        "querri share org-share-source SOURCE_ID",
    )
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        resp = client._http.post(
            f"/sources/{source_id}/shares/org",
            json={"permission": permission},
        )
        result = resp.json()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Shared source {source_id} with organization ({permission})")
