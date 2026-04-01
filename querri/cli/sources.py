"""querri sources — manage connector-based data sources.

For file-backed datasets, see ``querri data``.
"""

from __future__ import annotations

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

sources_app = typer.Typer(
    name="sources",
    help="Manage connector-based data sources. For file-backed datasets, see `querri data`.",
    no_args_is_help=True,
)


@sources_app.command("connectors")
def list_connectors(
    ctx: typer.Context,
) -> None:
    """List available connector types."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.sources.list_connectors()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(items)
    else:
        print_table(
            items,
            [("id", "ID"), ("name", "Name"), ("service", "Service"), ("status", "Status")],
            ctx=ctx,
        )


@sources_app.command("list")
def list_sources(
    ctx: typer.Context,
) -> None:
    """List data sources."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.sources.list()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(items)
    elif obj.get("quiet"):
        for s in items:
            print_id(s.get("id", ""))
    else:
        print_table(
            items,
            [("id", "ID"), ("name", "Name"), ("service", "Service"), ("connector_id", "Connector")],
            ctx=ctx,
        )


@sources_app.command("get")
def get_source(
    ctx: typer.Context,
    source_id: str = typer.Argument(help="Source ID."),
) -> None:
    """Get source details."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        source = client.sources.get(source_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(source)
    elif obj.get("quiet"):
        print_id(source.get("id", ""))
    else:
        print_detail(
            source,
            [(k, k) for k in source.keys()],
        )


@sources_app.command("update")
def update_source(
    ctx: typer.Context,
    source_id: str = typer.Argument(help="Source ID."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name."),
    config: Optional[str] = typer.Option(None, "--config", help="JSON config string."),
) -> None:
    """Update source configuration."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    config_dict = None
    if config:
        import json
        try:
            config_dict = json.loads(config)
        except json.JSONDecodeError as exc:
            from querri.cli._output import print_error
            print_error(f"Invalid JSON config: {exc}")
            raise typer.Exit(code=1)

    try:
        result = client.sources.update(source_id, name=name, config=config_dict)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Updated source {source_id}")


@sources_app.command("delete")
def delete_source(
    ctx: typer.Context,
    source_id: str = typer.Argument(help="Source ID."),
) -> None:
    """Delete a data source."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.sources.delete(source_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"id": source_id, "deleted": True})
    else:
        print_success(f"Deleted source {source_id}")


@sources_app.command("sync")
def sync_source(
    ctx: typer.Context,
    source_id: str = typer.Argument(help="Source ID."),
) -> None:
    """Trigger a source sync."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.sources.sync(source_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Sync queued for source {source_id}")
