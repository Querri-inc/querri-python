"""querri view — manage SQL-defined views."""

from __future__ import annotations

import json
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


def _print_sse_stream(stream) -> None:
    """Parse VercelStream v2 SSE data and print text + tool activity to terminal."""
    for line in stream:
        line = line.strip()
        if not line or line == "[DONE]":
            continue
        if line.startswith("data: "):
            line = line[6:]
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue

        event_type = event.get("type", "")

        if event_type == "text-delta":
            sys.stdout.write(event.get("delta", ""))
            sys.stdout.flush()
        elif event_type == "tool-input-available":
            tool_name = event.get("toolName", "?")
            print(f"\n  ⚡ {tool_name}", file=sys.stderr, end="", flush=True)
        elif event_type == "tool-output-available":
            output = event.get("output", {})
            if "error" in output:
                print(f" → error: {output['error']}", file=sys.stderr, flush=True)
            elif output.get("materialized"):
                rows = output.get("rows", "?")
                print(f" → materialized ✓ ({rows} rows)", file=sys.stderr, flush=True)
            elif output.get("saved"):
                print(f" → saved ✓", file=sys.stderr, flush=True)
            elif output.get("status") == "ok" and "total_rows" in output:
                print(f" → {output['total_rows']} rows, {len(output.get('columns', []))} cols", file=sys.stderr, flush=True)
            elif "sources" in output:
                print(f" → {len(output['sources'])} sources found", file=sys.stderr, flush=True)
            elif output.get("status") == "awaiting_user_choice":
                # Choices were presented in the text stream
                print("", file=sys.stderr, flush=True)
            else:
                print(" → done", file=sys.stderr, flush=True)
        elif event_type == "finish":
            print("", flush=True)  # Final newline


@view_app.command("chat")
def chat_with_view(
    ctx: typer.Context,
    view_uuid: Optional[str] = typer.Argument(default=None, help="View UUID."),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Message for the view agent."),
) -> None:
    """Chat with the view authoring agent to create or refine SQL.

    Examples:
        querri view chat <UUID> -m "join customers with orders by customer_id"
        querri view chat <UUID> -m "add a filter for active customers only"
    """
    if view_uuid is None:
        if sys.stdin.isatty():
            view_uuid = input("View UUID: ").strip()
        else:
            print_error("Missing required argument <VIEW_UUID>. Usage: querri view chat <VIEW_UUID> -m <MESSAGE>")
            raise typer.Exit(code=1)
    if message is None:
        if sys.stdin.isatty():
            message = input("Message: ").strip()
        else:
            print_error("Missing required option --message. Usage: querri view chat <VIEW_UUID> -m <MESSAGE>")
            raise typer.Exit(code=1)

    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    try:
        stream = client.views.chat(view_uuid, message=message)
        _print_sse_stream(stream)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))


@view_app.command("new")
def new_view(
    ctx: typer.Context,
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Describe the view you want to create."),
) -> None:
    """Create a new view from a natural-language description.

    Creates a draft view, runs the authoring agent with your prompt,
    and generates a name and description from the result.

    Examples:
        querri view new -p "monthly revenue by product line"
        querri view new -p "join customers with orders, show top 10 by total spend"
    """
    if prompt is None:
        if sys.stdin.isatty():
            prompt = input("Describe the view: ").strip()
        else:
            print_error("Missing required option --prompt. Usage: querri view new --prompt <DESCRIPTION>")
            raise typer.Exit(code=1)

    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    # 1. Create draft view (no name, no SQL)
    try:
        result = client.views.create()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    view_uuid = result.get("id", result.get("uuid", ""))
    print(f"Created draft view {view_uuid}", file=sys.stderr, flush=True)

    # 2. Run the agent with the prompt
    try:
        stream = client.views.chat(view_uuid, message=prompt)
        _print_sse_stream(stream)
    except Exception as exc:
        print_error(f"Agent error: {exc}")
        print(f"\nView UUID: {view_uuid} (draft — use 'querri view chat' to continue)", file=sys.stderr)
        raise typer.Exit(code=1)

    # 3. Generate name + description from the conversation
    try:
        meta = client.views.generate_metadata(view_uuid)
        name = meta.get("name", "")
        desc = meta.get("description", "")
        if name:
            print(f"\n  Name: {name}", file=sys.stderr, flush=True)
        if desc:
            print(f"  Description: {desc}", file=sys.stderr, flush=True)
    except Exception as exc:
        print(f"\n  (metadata generation failed: {exc})", file=sys.stderr)

    # 4. Print the view UUID for scripting
    if obj.get("json"):
        print_json({"id": view_uuid, "name": name, "description": desc})
    elif obj.get("quiet"):
        print_id(view_uuid)
    else:
        print(f"\n  View: {view_uuid}", file=sys.stderr)
