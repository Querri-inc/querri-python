"""querri step — view project steps and step data."""

from __future__ import annotations

import sys

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    handle_api_error,
    print_error,
    print_json,
    print_table,
)

steps_app = typer.Typer(
    name="steps",
    help="View project steps and their data outputs.",
    no_args_is_help=True,
)


@steps_app.command("list")
def list_steps(
    ctx: typer.Context,
    project_id: str | None = typer.Argument(default=None, help="Project ID."),
) -> None:
    """List steps in a project."""
    if project_id is None:
        if sys.stdin.isatty():
            project_id = input("Project ID: ").strip()
        else:
            print_error(
                "Missing required argument <PROJECT_ID>."
                " Usage: querri step list <PROJECT_ID>"
            )
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        steps = client.projects.list_steps(project_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json([s.model_dump(mode="json") for s in steps])
    else:
        print_table(
            steps,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("type", "Type"),
                ("status", "Status"),
                ("order", "Order"),
                ("has_data", "Data"),
            ],
            ctx=ctx,
        )


@steps_app.command("data")
def step_data(
    ctx: typer.Context,
    project_id: str | None = typer.Argument(default=None, help="Project ID."),
    step_id: str | None = typer.Argument(default=None, help="Step ID."),
    page: int = typer.Option(1, "--page", help="Page number."),
    page_size: int = typer.Option(25, "--page-size", help="Rows per page."),
) -> None:
    """View data output from a project step."""
    if project_id is None:
        if sys.stdin.isatty():
            project_id = input("Project ID: ").strip()
        else:
            print_error(
                "Missing required argument <PROJECT_ID>."
                " Usage: querri step data"
                " <PROJECT_ID> <STEP_ID>"
            )
            raise typer.Exit(code=1)
    if step_id is None:
        if sys.stdin.isatty():
            step_id = input("Step ID: ").strip()
        else:
            print_error(
                "Missing required argument <STEP_ID>."
                " Usage: querri step data"
                " <PROJECT_ID> <STEP_ID>"
            )
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.projects.get_step_data(
            project_id,
            step_id,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result)
    else:
        columns_list = result.columns or []
        if result.data:
            # Derive columns from data keys if not provided
            if not columns_list:
                columns_list = list(result.data[0].keys()) if result.data else []
            print_table(
                result.data,
                [(c, c) for c in columns_list],
                ctx=ctx,
            )
            if result.total_rows:
                print(
                    f"\nShowing page {result.page}/"
                    f"{(result.total_rows + page_size - 1) // page_size} "
                    f"({result.total_rows} total rows)",
                    file=sys.stderr,
                )
