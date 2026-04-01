"""querri audit — view audit log events."""

from __future__ import annotations

from typing import Optional

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
    actor_id: Optional[str] = typer.Option(None, "--actor-id", help="Filter by actor ID."),
    target_id: Optional[str] = typer.Option(None, "--target-id", help="Filter by target ID."),
    action: Optional[str] = typer.Option(None, "--action", help="Filter by action type."),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="Start date (ISO 8601)."),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="End date (ISO 8601)."),
    page: int = typer.Option(1, "--page", "-p", help="Page number."),
    page_size: int = typer.Option(50, "--page-size", help="Results per page."),
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
            page=page,
            page_size=page_size,
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
