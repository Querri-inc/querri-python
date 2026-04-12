"""querri view — manage SQL-defined views."""

from __future__ import annotations

import sys
from typing import Optional

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    handle_api_error,
    print_detail,
    print_error,
    print_id,
    print_json,
    print_success,
    print_table,
)

view_app = typer.Typer(
    name="views",
    help="Manage SQL-defined views.",
    no_args_is_help=True,
)


@view_app.command("create")
def create_view(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name", "-n", help="View name."),
    sql: Optional[str] = typer.Option(None, "--sql", "-s", help="SQL definition."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="View description."),
) -> None:
    """Create a new SQL-defined view."""
    if name is None:
        if sys.stdin.isatty():
            name = input("View name: ").strip()
        else:
            print_error("Missing required option --name. Usage: querri view create --name <NAME> --sql <SQL>")
            raise typer.Exit(code=1)
    if sql is None:
        if sys.stdin.isatty():
            sql = input("SQL definition: ").strip()
        else:
            print_error("Missing required option --sql. Usage: querri view create --name <NAME> --sql <SQL>")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    try:
        result = client.views.create(name=name, sql_definition=sql, description=description)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    elif obj.get("quiet"):
        print_id(result.get("id", result.get("uuid", "")))
    else:
        view_id = result.get("id", result.get("uuid", ""))
        print_success(f"Created view {view_id} ({name})")


@view_app.command("list")
def list_views(
    ctx: typer.Context,
) -> None:
    """List all views."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.views.list()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(items)
    elif obj.get("quiet"):
        for v in items:
            print_id(v.get("id", v.get("uuid", "")))
    else:
        print_table(
            items,
            [("id", "ID"), ("name", "Name"), ("status", "Status"), ("description", "Description")],
            ctx=ctx,
        )


@view_app.command("get")
def get_view(
    ctx: typer.Context,
    view_uuid: Optional[str] = typer.Argument(default=None, help="View UUID."),
) -> None:
    """Get view details."""
    if view_uuid is None:
        if sys.stdin.isatty():
            view_uuid = input("View UUID: ").strip()
        else:
            print_error("Missing required argument <VIEW_UUID>. Usage: querri view get <VIEW_UUID>")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        view = client.views.get(view_uuid)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(view)
    elif obj.get("quiet"):
        print_id(view.get("id", view.get("uuid", "")))
    else:
        print_detail(
            view,
            [(k, k) for k in view.keys()],
        )


@view_app.command("update")
def update_view(
    ctx: typer.Context,
    view_uuid: Optional[str] = typer.Argument(default=None, help="View UUID."),
    sql: Optional[str] = typer.Option(None, "--sql", "-s", help="Updated SQL definition."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Updated description."),
) -> None:
    """Update a view's SQL definition or description."""
    if view_uuid is None:
        if sys.stdin.isatty():
            view_uuid = input("View UUID: ").strip()
        else:
            print_error("Missing required argument <VIEW_UUID>. Usage: querri view update <VIEW_UUID>")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    try:
        result = client.views.update(view_uuid, sql_definition=sql, description=description)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Updated view {view_uuid}")


@view_app.command("delete")
def delete_view(
    ctx: typer.Context,
    view_uuid: Optional[str] = typer.Argument(default=None, help="View UUID."),
) -> None:
    """Delete a view."""
    if view_uuid is None:
        if sys.stdin.isatty():
            view_uuid = input("View UUID: ").strip()
        else:
            print_error("Missing required argument <VIEW_UUID>. Usage: querri view delete <VIEW_UUID>")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.views.delete(view_uuid)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"uuid": view_uuid, "deleted": True})
    else:
        print_success(f"Deleted view {view_uuid}")


@view_app.command("run")
def run_views(
    ctx: typer.Context,
    view_uuids: Optional[str] = typer.Option(None, "--view-uuids", help="Comma-separated view UUIDs to materialize."),
) -> None:
    """Run view materialization.

    Omit --view-uuids to materialize the full DAG.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    uuids = None
    if view_uuids:
        uuids = [u.strip() for u in view_uuids.split(",") if u.strip()]

    try:
        result = client.views.run(view_uuids=uuids)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success("View materialization started")
        if result.get("status"):
            print(f"  Status: {result['status']}", file=sys.stderr)


@view_app.command("preview")
def preview_view(
    ctx: typer.Context,
    view_uuid: Optional[str] = typer.Argument(default=None, help="View UUID."),
    limit: int = typer.Option(100, "--limit", "-l", help="Max rows to return."),
) -> None:
    """Preview view results without materializing."""
    if view_uuid is None:
        if sys.stdin.isatty():
            view_uuid = input("View UUID: ").strip()
        else:
            print_error("Missing required argument <VIEW_UUID>. Usage: querri view preview <VIEW_UUID>")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    try:
        result = client.views.preview(view_uuid, limit=limit)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        rows = result.get("rows", result.get("data", []))
        if rows:
            cols = list(rows[0].keys())
            print_table(rows, [(c, c) for c in cols], ctx=ctx)
            total = result.get("total_rows", len(rows))
            print(f"\n{total} total rows (showing up to {limit})", file=sys.stderr)
        else:
            print("No data returned.", file=sys.stderr)
