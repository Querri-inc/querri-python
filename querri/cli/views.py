"""querri view — manage SQL-defined views."""

from __future__ import annotations

import json
import sys

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


@view_app.command("new")
def new_view(
    ctx: typer.Context,
    name: str | None = typer.Option(None, "--name", "-n", help="View name."),
    sql: str | None = typer.Option(None, "--sql", "-s", help="SQL definition."),
    description: str | None = typer.Option(
        None, "--description", "-d", help="View description."
    ),
    prompt: str | None = typer.Option(
        None, "--prompt", help="Describe the view with AI (optional)."
    ),
) -> None:
    """Create a new view — directly with SQL or via the AI authoring agent.

    If --prompt is given (or entered interactively), the AI agent writes the
    SQL and auto-generates a name and description from the conversation.

    If --sql is given without --prompt, the view is created directly.

    Running with no arguments drops into interactive mode — all fields are
    optional. Provide at least a prompt or SQL definition.

    Examples:
        querri view new                                                   # interactive
        querri view new --prompt "monthly revenue by product line"       # AI agent
        querri view new --name "Orders" --sql "SELECT * FROM orders"    # direct
        querri view new -n "Revenue" --prompt "revenue by region"
                                                       # AI + custom name
    """
    is_interactive = sys.stdin.isatty()

    # Interactive: collect all inputs inline when no flags were passed
    if (
        is_interactive
        and name is None
        and sql is None
        and description is None
        and prompt is None
    ):
        name = input("Name (optional): ").strip() or None
        sql = input("SQL definition (optional): ").strip() or None
        description = input("Description (optional): ").strip() or None
        prompt = input("AI prompt (optional, press Enter to skip): ").strip() or None

    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    if prompt:
        # ── AI agent flow ──────────────────────────────────────────────────────
        # Create a draft view, optionally seeding name/sql/description
        try:
            result = client.views.create(
                name=name or None,
                sql_definition=sql or None,
                description=description or None,
            )
        except Exception as exc:
            raise typer.Exit(
                code=handle_api_error(exc, is_json=obj.get("json"))
            ) from None

        view_id = result.get("id", result.get("uuid", ""))
        print(f"Created draft view {view_id}", file=sys.stderr, flush=True)

        # Run the authoring agent
        try:
            stream = client.views.chat(view_id, message=prompt)
            _print_sse_stream(stream)
        except Exception as exc:
            print_error(f"Agent error: {exc}")
            print(
                f"\nView UUID: {view_id} (draft — use 'querri view chat' to continue)",
                file=sys.stderr,
            )
            raise typer.Exit(code=1) from None

        # Auto-generate name + description unless user already supplied a name
        generated_name = name or ""
        generated_desc = description or ""
        if not name:
            try:
                meta = client.views.generate_metadata(view_id)
                generated_name = meta.get("name", "")
                generated_desc = meta.get("description", "")
                if generated_name:
                    print(f"\n  Name: {generated_name}", file=sys.stderr, flush=True)
                if generated_desc:
                    print(
                        f"  Description: {generated_desc}", file=sys.stderr, flush=True
                    )
            except Exception as exc:
                print(f"\n  (metadata generation failed: {exc})", file=sys.stderr)

        if obj.get("json"):
            print_json(
                {"id": view_id, "name": generated_name, "description": generated_desc}
            )
        elif obj.get("quiet"):
            print_id(view_id)
        else:
            print(f"\n  View: {view_id}", file=sys.stderr)

    elif sql:
        # ── Direct create flow ────────────────────────────────────────────────
        try:
            result = client.views.create(
                name=name, sql_definition=sql, description=description
            )
        except Exception as exc:
            raise typer.Exit(
                code=handle_api_error(exc, is_json=obj.get("json"))
            ) from None

        if obj.get("json"):
            print_json(result)
        elif obj.get("quiet"):
            print_id(result.get("id", result.get("uuid", "")))
        else:
            view_id = result.get("id", result.get("uuid", ""))
            label = f" ({name})" if name else ""
            print_success(f"Created view {view_id}{label}")

    else:
        if not is_interactive:
            print_error(
                "Provide --prompt (AI agent) or --sql (direct). "
                "Usage: querri view new --prompt <DESC> | --sql <SQL>"
            )
        else:
            print_error("Need a prompt or SQL definition. Try: querri view new --help")
        raise typer.Exit(code=1)


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
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(items)
    elif obj.get("quiet"):
        for v in items:
            print_id(v.get("id", v.get("uuid", "")))
    else:
        print_table(
            items,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("status", "Status"),
                ("description", "Description"),
            ],
            ctx=ctx,
        )


@view_app.command("get")
def get_view(
    ctx: typer.Context,
    view_id: str | None = typer.Argument(default=None, help="View ID."),
) -> None:
    """Get view details."""
    if view_id is None:
        if sys.stdin.isatty():
            view_id = input("View ID: ").strip()
        else:
            print_error(
                "Missing required argument <VIEW_ID>. Usage: querri view get <VIEW_ID>"
            )
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        view = client.views.get(view_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(view)
    elif obj.get("quiet"):
        print_id(view.get("id", view.get("uuid", "")))
    else:
        print_detail(
            view,
            [(k, k) for k in view],
        )


@view_app.command("update")
def update_view(
    ctx: typer.Context,
    view_id: str | None = typer.Argument(default=None, help="View ID."),
    sql: str | None = typer.Option(None, "--sql", "-s", help="Updated SQL definition."),
    description: str | None = typer.Option(
        None, "--description", "-d", help="Updated description."
    ),
) -> None:
    """Update a view's SQL definition or description."""
    if view_id is None:
        if sys.stdin.isatty():
            view_id = input("View ID: ").strip()
        else:
            print_error(
                "Missing required argument <VIEW_ID>."
                " Usage: querri view update <VIEW_ID>"
            )
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    try:
        result = client.views.update(
            view_id, sql_definition=sql, description=description
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Updated view {view_id}")


@view_app.command("delete")
def delete_view(
    ctx: typer.Context,
    view_id: str | None = typer.Argument(default=None, help="View ID."),
) -> None:
    """Delete a view."""
    if view_id is None:
        if sys.stdin.isatty():
            view_id = input("View ID: ").strip()
        else:
            print_error(
                "Missing required argument <VIEW_ID>."
                " Usage: querri view delete <VIEW_ID>"
            )
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.views.delete(view_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json({"id": view_id, "deleted": True})
    else:
        print_success(f"Deleted view {view_id}")


@view_app.command("run")
def run_views(
    ctx: typer.Context,
    view_ids: str | None = typer.Option(
        None, "--view-ids", help="Comma-separated view IDs to materialize."
    ),
) -> None:
    """Run view materialization.

    Omit --view-ids to materialize the full DAG.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    uuids = None
    if view_ids:
        uuids = [u.strip() for u in view_ids.split(",") if u.strip()]

    try:
        result = client.views.run(view_uuids=uuids)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result)
    else:
        print_success("View materialization started")
        if result.get("status"):
            print(f"  Status: {result['status']}", file=sys.stderr)


@view_app.command("preview")
def preview_view(
    ctx: typer.Context,
    view_id: str | None = typer.Argument(default=None, help="View ID."),
    limit: int = typer.Option(25, "--limit", "-l", help="Max rows to return."),
) -> None:
    """Preview view results without materializing."""
    if view_id is None:
        if sys.stdin.isatty():
            view_id = input("View ID: ").strip()
        else:
            print_error(
                "Missing required argument <VIEW_ID>."
                " Usage: querri view preview <VIEW_ID>"
            )
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    try:
        result = client.views.preview(view_id, limit=limit)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

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
                print(" → saved ✓", file=sys.stderr, flush=True)
            elif output.get("status") == "ok" and "total_rows" in output:
                print(
                    f" → {output['total_rows']} rows, "
                    f"{len(output.get('columns', []))} cols",
                    file=sys.stderr,
                    flush=True,
                )
            elif "sources" in output:
                print(
                    f" → {len(output['sources'])} sources found",
                    file=sys.stderr,
                    flush=True,
                )
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
    view_id: str | None = typer.Argument(default=None, help="View ID."),
    message: str | None = typer.Option(
        None, "--message", "-m", help="Message for the view agent."
    ),
) -> None:
    """Chat with the view authoring agent to create or refine SQL.

    Examples:
        querri view chat <UUID> -m "join customers with orders by customer_id"
        querri view chat <UUID> -m "add a filter for active customers only"
    """
    if view_id is None:
        if sys.stdin.isatty():
            view_id = input("View ID: ").strip()
        else:
            print_error(
                "Missing required argument <VIEW_ID>."
                " Usage: querri view chat"
                " <VIEW_ID> -m <MESSAGE>"
            )
            raise typer.Exit(code=1)
    if message is None:
        if sys.stdin.isatty():
            message = input("Message: ").strip()
        else:
            print_error(
                "Missing required option --message."
                " Usage: querri view chat"
                " <VIEW_ID> -m <MESSAGE>"
            )
            raise typer.Exit(code=1)

    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    try:
        stream = client.views.chat(view_id, message=message)
        _print_sse_stream(stream)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
