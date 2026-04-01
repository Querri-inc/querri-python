"""querri dashboards — manage dashboards and refreshes."""

from __future__ import annotations

import time
from typing import Optional

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    handle_api_error,
    print_detail,
    print_id,
    print_json,
    print_success,
    print_table,
)

dashboards_app = typer.Typer(
    name="dashboards",
    help="Manage dashboards — create, view, and refresh.",
    no_args_is_help=True,
)


@dashboards_app.command("list")
def list_dashboards(
    ctx: typer.Context,
    limit: int = typer.Option(25, "--limit", "-n", help="Max results."),
    after: Optional[str] = typer.Option(None, "--after", help="Cursor for pagination."),
) -> None:
    """List dashboards."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.dashboards.list(limit=limit, after=after)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json([d.model_dump(mode="json") for d in items])
    elif obj.get("quiet"):
        for d in items:
            print_id(d.id)
    else:
        print_table(
            items,
            [("id", "ID"), ("name", "Name"), ("widget_count", "Widgets"), ("updated_at", "Updated")],
            ctx=ctx,
        )


@dashboards_app.command("get")
def get_dashboard(
    ctx: typer.Context,
    dashboard_id: str = typer.Argument(help="Dashboard ID."),
) -> None:
    """Get dashboard details."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        dashboard = client.dashboards.get(dashboard_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(dashboard)
    elif obj.get("quiet"):
        print_id(dashboard.id)
    else:
        print_detail(
            dashboard,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("description", "Description"),
                ("widget_count", "Widgets"),
                ("created_by", "Created By"),
                ("created_at", "Created"),
                ("updated_at", "Updated"),
            ],
        )


@dashboards_app.command("create")
def create_dashboard(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", "-n", help="Dashboard name."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Description."),
) -> None:
    """Create a new dashboard."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        dashboard = client.dashboards.create(name=name, description=description)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(dashboard)
    elif obj.get("quiet"):
        print_id(dashboard.id)
    else:
        print_success(f"Created dashboard {dashboard.id}")


@dashboards_app.command("update")
def update_dashboard(
    ctx: typer.Context,
    dashboard_id: str = typer.Argument(help="Dashboard ID."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description."),
) -> None:
    """Update a dashboard."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.dashboards.update(dashboard_id, name=name, description=description)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"id": dashboard_id, "updated": True})
    else:
        print_success(f"Updated dashboard {dashboard_id}")


@dashboards_app.command("delete")
def delete_dashboard(
    ctx: typer.Context,
    dashboard_id: str = typer.Argument(help="Dashboard ID."),
) -> None:
    """Delete a dashboard."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.dashboards.delete(dashboard_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"id": dashboard_id, "deleted": True})
    else:
        print_success(f"Deleted dashboard {dashboard_id}")


@dashboards_app.command("refresh")
def refresh_dashboard(
    ctx: typer.Context,
    dashboard_id: str = typer.Argument(help="Dashboard ID."),
    wait: bool = typer.Option(False, "--wait", "-w", help="Block until refresh completes."),
) -> None:
    """Trigger a dashboard refresh."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.dashboards.refresh(dashboard_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if wait:
        try:
            while True:
                status = client.dashboards.refresh_status(dashboard_id)
                if status.status != "refreshing":
                    break
                time.sleep(2)
        except Exception as exc:
            raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

        if obj.get("json"):
            print_json(status)
        else:
            print_success(f"Dashboard refresh completed: {status.status}")
    else:
        if obj.get("json"):
            print_json(result)
        else:
            print_success(f"Dashboard refresh started (status: {result.status})")


@dashboards_app.command("refresh-status")
def refresh_status(
    ctx: typer.Context,
    dashboard_id: str = typer.Argument(help="Dashboard ID."),
) -> None:
    """Check dashboard refresh status."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        status = client.dashboards.refresh_status(dashboard_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(status)
    else:
        print_detail(
            status,
            [("id", "ID"), ("status", "Status"), ("project_count", "Projects")],
        )
