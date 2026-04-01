"""querri data — manage file-backed data sources, queries, and AI Q&A.

For connector-based sources, see ``querri sources``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
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

data_app = typer.Typer(
    name="data",
    help="Manage file-backed data sources and queries. For connector-based sources, see `querri sources`.",
    no_args_is_help=True,
)


@data_app.command("sources")
def list_sources(
    ctx: typer.Context,
) -> None:
    """List all data sources."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.data.sources()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json([s.model_dump(mode="json") for s in items])
    elif obj.get("quiet"):
        for s in items:
            print_id(s.id)
    else:
        print_table(
            items,
            [("id", "ID"), ("name", "Name"), ("row_count", "Rows"), ("updated_at", "Updated")],
            ctx=ctx,
        )


@data_app.command("source")
def get_source(
    ctx: typer.Context,
    source_id: str = typer.Argument(help="Source ID."),
) -> None:
    """Get data source details."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        source = client.data.source(source_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(source)
    elif obj.get("quiet"):
        print_id(source.id)
    else:
        print_detail(
            source,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("columns", "Columns"),
                ("row_count", "Rows"),
                ("updated_at", "Updated"),
            ],
        )


@data_app.command("source-data")
def source_data(
    ctx: typer.Context,
    source_id: str = typer.Argument(help="Source ID."),
    page: int = typer.Option(1, "--page", "-p", help="Page number."),
    page_size: int = typer.Option(100, "--page-size", help="Rows per page."),
) -> None:
    """View data from a source."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.data.source_data(source_id, page=page, page_size=page_size)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        columns_list = result.columns or []
        if result.data:
            if not columns_list:
                columns_list = list(result.data[0].keys()) if result.data else []
            print_table(result.data, [(c, c) for c in columns_list], ctx=ctx)
            if result.total_rows:
                total_pages = (result.total_rows + page_size - 1) // page_size
                print(
                    f"\nPage {result.page}/{total_pages} ({result.total_rows} total rows)",
                    file=sys.stderr,
                )


@data_app.command("create-source")
def create_source(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", "-n", help="Source name."),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="JSON file with row data.",
        exists=True, file_okay=True, dir_okay=False, resolve_path=True,
    ),
) -> None:
    """Create a new data source from JSON data.

    Reads rows from --file or stdin (JSON array of objects).
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    try:
        if file:
            raw = file.read_text()
        else:
            if sys.stdin.isatty():
                print("Reading JSON rows from stdin (Ctrl+D to end):", file=sys.stderr)
            raw = sys.stdin.read()

        rows = json.loads(raw)
        if not isinstance(rows, list):
            print_json({"error": "validation_error", "message": "Expected a JSON array of objects.", "code": 1}) if obj.get("json") else None
            raise typer.Exit(code=1)
    except json.JSONDecodeError as exc:
        from querri.cli._output import print_error
        if obj.get("json"):
            from querri.cli._output import print_json_error
            print_json_error("validation_error", f"Invalid JSON: {exc}", 1)
        else:
            print_error(f"Invalid JSON: {exc}")
        raise typer.Exit(code=1)

    try:
        source = client.data.create_source(name=name, rows=rows)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(source)
    elif obj.get("quiet"):
        print_id(source.id)
    else:
        print_success(f"Created source {source.id} ({source.name})")


@data_app.command("delete-source")
def delete_source(
    ctx: typer.Context,
    source_id: str = typer.Argument(help="Source ID."),
) -> None:
    """Delete a data source."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.data.delete_source(source_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"id": source_id, "deleted": True})
    else:
        print_success(f"Deleted source {source_id}")


@data_app.command("query")
def query_data(
    ctx: typer.Context,
    sql: str = typer.Option(..., "--sql", "-s", help="SQL query string."),
    source_id: str = typer.Option(..., "--source-id", help="Source to query."),
    page: int = typer.Option(1, "--page", "-p", help="Page number."),
    page_size: int = typer.Option(100, "--page-size", help="Rows per page."),
) -> None:
    """Run a SQL query against a data source."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.data.query(sql=sql, source_id=source_id, page=page, page_size=page_size)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        if result.data:
            cols = list(result.data[0].keys())
            print_table(result.data, [(c, c) for c in cols], ctx=ctx)
            print(f"\n{result.total_rows} total rows", file=sys.stderr)


@data_app.command("ask")
def ask_data(
    ctx: typer.Context,
    source_id: str = typer.Argument(help="Source ID."),
    question: str = typer.Option(..., "--question", "-q", help="Natural language question."),
) -> None:
    """Ask a natural language question about a data source."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    # Note: The `ask` endpoint may use SSE or simple POST.
    # For now, implement as a simple POST via the HTTP client.
    try:
        resp = client._http.post(
            f"/data/sources/{source_id}/ask",
            json={"question": question},
        )
        result = resp.json()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        # Display answer text if available
        answer = result.get("answer", result.get("text", ""))
        if answer:
            print(answer)
        if result.get("data"):
            cols = list(result["data"][0].keys()) if result["data"] else []
            print_table(result["data"], [(c, c) for c in cols], ctx=ctx)
