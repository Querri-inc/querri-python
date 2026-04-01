"""querri usage — view organization and user usage reports."""

from __future__ import annotations

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    handle_api_error,
    print_detail,
    print_json,
)

usage_app = typer.Typer(
    name="usage",
    help="View usage reports for the organization.",
    no_args_is_help=True,
)


@usage_app.command("org")
def org_usage(
    ctx: typer.Context,
    period: str = typer.Option("current_month", "--period", "-p", help="Usage period."),
) -> None:
    """View organization-wide usage."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        report = client.usage.org_usage(period=period)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(report)
    else:
        print_detail(
            report,
            [
                ("period_start", "Period Start"),
                ("period_end", "Period End"),
                ("total_queries", "Queries"),
                ("total_tokens", "Tokens"),
                ("total_projects", "Projects"),
                ("total_users", "Users"),
            ],
        )


@usage_app.command("user")
def user_usage(
    ctx: typer.Context,
    user_id: str = typer.Argument(help="User ID."),
    period: str = typer.Option("current_month", "--period", "-p", help="Usage period."),
) -> None:
    """View usage for a specific user."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        report = client.usage.user_usage(user_id, period=period)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(report)
    else:
        print_detail(
            report,
            [
                ("period_start", "Period Start"),
                ("period_end", "Period End"),
                ("total_queries", "Queries"),
                ("total_tokens", "Tokens"),
                ("total_projects", "Projects"),
            ],
        )
