"""querri share — manage resource sharing and permissions."""

from __future__ import annotations

import sys

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
    name="share",
    help="Share projects, dashboards, and sources with users.",
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
sharing_app.add_typer(share_source_app, name="source")


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
) -> None:
    """Share a project with a user."""
    project_id = _resolve_arg(
        project_id,
        "PROJECT_ID",
        "Project ID: ",
        "querri share project add PROJECT_ID --user-id USER_ID",
    )
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
) -> None:
    """Share a dashboard with a user."""
    dashboard_id = _resolve_arg(
        dashboard_id,
        "DASHBOARD_ID",
        "Dashboard ID: ",
        "querri share dashboard add DASHBOARD_ID --user-id USER_ID",
    )
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
) -> None:
    """Share a data source with a user."""
    source_id = _resolve_arg(
        source_id,
        "SOURCE_ID",
        "Source ID: ",
        "querri share source add SOURCE_ID --user-id USER_ID",
    )
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
) -> None:
    """Share a data source with the entire organization."""
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
            f"/sources/{source_id}/shares/org",
            json={"permission": permission},
        )
        result = resp.json()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Shared source {source_id} with organization ({permission})")
