"""querri source — manage data sources, queries, and AI Q&A."""

from __future__ import annotations

import json
import sys
from pathlib import Path

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

sources_app = typer.Typer(
    name="sources",
    help="Manage data sources — list, query, create, and explore.",
    no_args_is_help=True,
)


@sources_app.command("list")
def list_sources(
    ctx: typer.Context,
    search: str | None = typer.Option(None, "--search", "-s", help="Filter by name (substring match)."),
) -> None:
    """List data sources."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.sources.list(search=search)
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
    source_id: str | None = typer.Argument(default=None, help="Source ID."),
) -> None:
    """Get source details."""
    if source_id is None:
        if sys.stdin.isatty():
            source_id = input("Source ID: ").strip()
        else:
            print_error("Missing required argument <SOURCE_ID>. Usage: querri source get <SOURCE_ID>")
            raise typer.Exit(code=1)
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


@sources_app.command("describe")
def describe_source(
    ctx: typer.Context,
    source_id: str | None = typer.Argument(default=None, help="Source ID."),
) -> None:
    """Show source schema: columns, types, row count, and description."""
    if source_id is None:
        if sys.stdin.isatty():
            source_id = input("Source ID: ").strip()
        else:
            print_error("Missing required argument <SOURCE_ID>. Usage: querri source describe <SOURCE_ID>")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        source = client.sources.get(source_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(source)
    else:
        # Print basic info
        print_detail(
            source,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("row_count", "Rows"),
                ("description", "Description"),
                ("summary", "Summary"),
                ("updated_at", "Updated"),
            ],
        )
        # Print column schema as a table
        columns = source.get("columns", [])
        column_details = source.get("column_details", {})
        column_types = source.get("column_types", {})
        if columns:
            print(file=sys.stderr)  # blank line
            col_data = []
            for col in columns:
                detail = column_details.get(col, {})
                row: dict = {
                    "column": col,
                    "type": detail.get("type") or column_types.get(col, "unknown"),
                }
                if detail.get("non_null_count") is not None:
                    row["non_null"] = str(detail["non_null_count"])
                if detail.get("unique_count") is not None:
                    row["unique"] = str(detail["unique_count"])
                if detail.get("min_value") is not None:
                    row["min"] = f"{detail['min_value']:.2f}"
                if detail.get("max_value") is not None:
                    row["max"] = f"{detail['max_value']:.2f}"
                if detail.get("mean") is not None:
                    row["mean"] = f"{detail['mean']:.2f}"
                if detail.get("summary"):
                    row["summary"] = detail["summary"]
                col_data.append(row)

            # Build header list dynamically based on what data is present
            all_keys = set()
            for r in col_data:
                all_keys.update(r.keys())

            headers_list = [("column", "Column"), ("type", "Type")]
            if "non_null" in all_keys:
                headers_list.append(("non_null", "Non-Null"))
            if "unique" in all_keys:
                headers_list.append(("unique", "Unique"))
            if "min" in all_keys:
                headers_list.append(("min", "Min"))
            if "max" in all_keys:
                headers_list.append(("max", "Max"))
            if "mean" in all_keys:
                headers_list.append(("mean", "Mean"))
            if "summary" in all_keys:
                headers_list.append(("summary", "Summary"))

            print_table(col_data, headers_list, ctx=ctx)


@sources_app.command("data")
def source_data(
    ctx: typer.Context,
    source_id: str | None = typer.Argument(default=None, help="Source ID."),
    page: int = typer.Option(1, "--page", help="Page number."),
    page_size: int = typer.Option(25, "--page-size", help="Rows per page."),
) -> None:
    """View paginated row data from a source."""
    if source_id is None:
        if sys.stdin.isatty():
            source_id = input("Source ID: ").strip()
        else:
            print_error("Missing required argument <SOURCE_ID>. Usage: querri source data <SOURCE_ID>")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.sources.source_data(source_id, page=page, page_size=page_size)
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


@sources_app.command("query")
def query_data(
    ctx: typer.Context,
    sql: str | None = typer.Option(None, "--sql", help="SQL query string."),
    source_id: str | None = typer.Option(None, "--source-id", help="Source to query."),
    page: int = typer.Option(1, "--page", help="Page number."),
    page_size: int = typer.Option(25, "--page-size", help="Rows per page."),
) -> None:
    """Run a SQL query against a data source."""
    if source_id is None:
        if sys.stdin.isatty():
            source_id = input("Source ID: ").strip()
        else:
            print_error("Missing required option --source-id. Usage: querri source query --source-id <ID> --sql <SQL>")
            raise typer.Exit(code=1)
    if sql is None:
        if sys.stdin.isatty():
            sql = input("SQL query: ").strip()
        else:
            print_error("Missing required option --sql. Usage: querri source query --source-id <ID> --sql <SQL>")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.sources.query(sql=sql, source_id=source_id, page=page, page_size=page_size)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        if result.data:
            cols = list(result.data[0].keys())
            print_table(result.data, [(c, c) for c in cols], ctx=ctx)
            print(f"\n{result.total_rows} total rows", file=sys.stderr)


@sources_app.command("ask")
def ask_data(
    ctx: typer.Context,
    source_id: str | None = typer.Argument(default=None, help="Source ID."),
    question_arg: str | None = typer.Argument(default=None, help="Natural language question."),
    question_opt: str | None = typer.Option(None, "--question", "-q", help="Natural language question."),
) -> None:
    """Ask a natural language question about a data source.

    Examples:
        querri source ask SOURCE_ID "What are my top 10?"
        querri source ask SOURCE_ID --question "What are my top 10?"
    """
    # Merge positional and option forms — option takes priority
    question = question_opt or question_arg

    if source_id is None:
        if sys.stdin.isatty():
            source_id = input("Source ID: ").strip()
        else:
            print_error("Missing required argument <SOURCE_ID>. Usage: querri source ask <SOURCE_ID> \"<QUESTION>\"")
            raise typer.Exit(code=1)
    if question is None:
        if sys.stdin.isatty():
            question = input("Question: ").strip()
        else:
            print_error("Missing question. Usage: querri source ask <SOURCE_ID> \"<QUESTION>\"")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    try:
        result = client.sources.ask(source_id, question=question)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        # Display answer text if available
        answer = result.get("answer", result.get("text", ""))
        if answer:
            print(answer)
        # Show generated SQL for transparency
        if result.get("generated_sql"):
            print(f"SQL: {result['generated_sql']}", file=sys.stderr)
        if result.get("data"):
            cols = list(result["data"][0].keys()) if result["data"] else []
            print_table(result["data"], [(c, c) for c in cols], ctx=ctx)
            if result.get("total_rows") is not None:
                print(f"\n{result['total_rows']} total rows", file=sys.stderr)
        else:
            print("No results returned.", file=sys.stderr)


@sources_app.command("new")
def new_data_source(
    ctx: typer.Context,
    name: str | None = typer.Option(None, "--name", "-n", help="Source name."),
    file: Path | None = typer.Option(
        None, "--file", "-f", help="JSON file with row data.",
        exists=True, file_okay=True, dir_okay=False, resolve_path=True,
    ),
) -> None:
    """Create a new data source from JSON data.

    Reads rows from --file or stdin (JSON array of objects).
    """
    if name is None:
        if sys.stdin.isatty():
            name = input("Source name: ").strip()
        else:
            print_error("Missing required option --name. Usage: querri source new --name <NAME>")
            raise typer.Exit(code=1)
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
            if obj.get("json"):
                print_json({"error": "validation_error", "message": "Expected a JSON array of objects.", "code": 1})
            raise typer.Exit(code=1)
    except json.JSONDecodeError as exc:
        if obj.get("json"):
            from querri.cli._output import print_json_error
            print_json_error("validation_error", f"Invalid JSON: {exc}", 1)
        else:
            print_error(f"Invalid JSON: {exc}")
        raise typer.Exit(code=1)

    try:
        source = client.sources.create_data_source(name=name, rows=rows)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(source)
    elif obj.get("quiet"):
        print_id(source.id)
    else:
        print_success(f"Created source {source.id} ({source.name})")


@sources_app.command("update")
def update_source(
    ctx: typer.Context,
    source_id: str | None = typer.Argument(default=None, help="Source ID."),
    name: str | None = typer.Option(None, "--name", "-n", help="New name."),
    description: str | None = typer.Option(None, "--description", "-d", help="User notes about the source."),
    config: str | None = typer.Option(None, "--config", help="JSON config string."),
) -> None:
    """Update source configuration."""
    if source_id is None:
        if sys.stdin.isatty():
            source_id = input("Source ID: ").strip()
        else:
            print_error("Missing required argument <SOURCE_ID>. Usage: querri source update <SOURCE_ID>")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    config_dict = None
    if config:
        try:
            config_dict = json.loads(config)
        except json.JSONDecodeError as exc:
            print_error(f"Invalid JSON config: {exc}")
            raise typer.Exit(code=1)

    try:
        result = client.sources.update(source_id, name=name, description=description, config=config_dict)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Updated source {source_id}")


@sources_app.command("delete")
def delete_source(
    ctx: typer.Context,
    source_id: str | None = typer.Argument(default=None, help="Source ID."),
) -> None:
    """Delete a data source."""
    if source_id is None:
        if sys.stdin.isatty():
            source_id = input("Source ID: ").strip()
        else:
            print_error("Missing required argument <SOURCE_ID>. Usage: querri source delete <SOURCE_ID>")
            raise typer.Exit(code=1)
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
    source_id: str | None = typer.Argument(default=None, help="Source ID."),
) -> None:
    """Trigger a source sync."""
    if source_id is None:
        if sys.stdin.isatty():
            source_id = input("Source ID: ").strip()
        else:
            print_error("Missing required argument <SOURCE_ID>. Usage: querri source sync <SOURCE_ID>")
            raise typer.Exit(code=1)
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
