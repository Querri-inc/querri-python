"""querri audit — view audit log events."""

from __future__ import annotations

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    handle_api_error,
    print_json,
    print_table,
)

audit_app = typer.Typer(
    name="audit",
    help="View audit log events.",
    no_args_is_help=True,
)


@audit_app.command("list")
def list_events(
    ctx: typer.Context,
    actor_id: str | None = typer.Option(None, "--actor-id", help="Filter by actor ID."),
    target_id: str | None = typer.Option(None, "--target-id", help="Filter by target ID."),
    action: str | None = typer.Option(None, "--action", help="Filter by action type."),
    start_date: str | None = typer.Option(None, "--start-date", help="Start date (ISO 8601)."),
    end_date: str | None = typer.Option(None, "--end-date", help="End date (ISO 8601)."),
    limit: int = typer.Option(25, "--limit", "-l", help="Max results to return."),
    after: str | None = typer.Option(None, "--after", help="Cursor for pagination."),
) -> None:
    """List audit log events."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.audit.list(
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            after=after,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json([e.model_dump(mode="json") for e in items])
    else:
        print_table(
            items,
            [
                ("id", "ID"),
                ("action", "Action"),
                ("actor_id", "Actor"),
                ("target_type", "Target Type"),
                ("target_id", "Target ID"),
                ("timestamp", "Timestamp"),
            ],
            ctx=ctx,
        )
