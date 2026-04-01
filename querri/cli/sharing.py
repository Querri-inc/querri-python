"""querri sharing — manage resource sharing and permissions."""

from __future__ import annotations

from typing import Optional

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    handle_api_error,
    print_json,
    print_success,
    print_table,
)

sharing_app = typer.Typer(
    name="sharing",
    help="Share projects, dashboards, and sources with users.",
    no_args_is_help=True,
)


# ── Project sharing ──────────────────────────────────────────────────────────


@sharing_app.command("share-project")
def share_project(
    ctx: typer.Context,
    project_id: str = typer.Argument(help="Project ID."),
    user_id: str = typer.Option(..., "--user-id", help="User ID to share with."),
    permission: str = typer.Option("view", "--permission", "-p", help="Permission: view or edit."),
) -> None:
    """Share a project with a user."""
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
    project_id: str = typer.Argument(help="Project ID."),
    user_id: str = typer.Argument(help="User ID to revoke."),
) -> None:
    """Revoke a user's access to a project."""
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
    project_id: str = typer.Argument(help="Project ID."),
) -> None:
    """List users who have access to a project."""
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
            [("id", "ID"), ("resource_type", "Type"), ("created_by", "Shared By"), ("created_at", "Shared At")],
            ctx=ctx,
        )


# ── Dashboard sharing ────────────────────────────────────────────────────────


@sharing_app.command("share-dashboard")
def share_dashboard(
    ctx: typer.Context,
    dashboard_id: str = typer.Argument(help="Dashboard ID."),
    user_id: str = typer.Option(..., "--user-id", help="User ID to share with."),
    permission: str = typer.Option("view", "--permission", "-p", help="Permission: view or edit."),
) -> None:
    """Share a dashboard with a user."""
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
    dashboard_id: str = typer.Argument(help="Dashboard ID."),
    user_id: str = typer.Argument(help="User ID to revoke."),
) -> None:
    """Revoke a user's access to a dashboard."""
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
    dashboard_id: str = typer.Argument(help="Dashboard ID."),
) -> None:
    """List users who have access to a dashboard."""
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
            [("id", "ID"), ("resource_type", "Type"), ("created_by", "Shared By"), ("created_at", "Shared At")],
            ctx=ctx,
        )


# ── Source sharing ────────────────────────────────────────────────────────────
# Note: Source sharing SDK methods (share_source, revoke_source_share,
# list_source_shares, org_share_source) are not yet in the SDK.
# These commands call the HTTP client directly.


@sharing_app.command("share-source")
def share_source(
    ctx: typer.Context,
    source_id: str = typer.Argument(help="Source ID."),
    user_id: str = typer.Option(..., "--user-id", help="User ID to share with."),
    permission: str = typer.Option("view", "--permission", "-p", help="Permission: view or edit."),
) -> None:
    """Share a data source with a user."""
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
    source_id: str = typer.Argument(help="Source ID."),
    user_id: str = typer.Argument(help="User ID to revoke."),
) -> None:
    """Revoke a user's access to a data source."""
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
    source_id: str = typer.Argument(help="Source ID."),
) -> None:
    """List users who have access to a data source."""
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
            [("id", "ID"), ("resource_type", "Type"), ("created_by", "Shared By"), ("created_at", "Shared At")],
            ctx=ctx,
        )


@sharing_app.command("org-share-source")
def org_share_source(
    ctx: typer.Context,
    source_id: str = typer.Argument(help="Source ID."),
    permission: str = typer.Option("view", "--permission", "-p", help="Permission: view or edit."),
) -> None:
    """Share a data source with the entire organization."""
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
