"""querri usage — view organization and user usage reports."""

from __future__ import annotations

import sys

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    handle_api_error,
    print_detail,
    print_error,
    print_json,
    print_table,
)

usage_app = typer.Typer(
    name="usage",
    help="View usage reports for the organization.",
    no_args_is_help=True,
)


@usage_app.command("org")
def org_usage(
    ctx: typer.Context,
    period: str = typer.Option("current_month", "--period", help="Usage period."),
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
                ("period", "Period"),
                ("period_start", "Period Start"),
                ("period_end", "Period End"),
                ("total_ai_messages", "AI Messages"),
                ("active_user_count", "Active Users"),
                ("project_count", "Projects"),
            ],
        )


@usage_app.command("user")
def user_usage(
    ctx: typer.Context,
    user_id: str | None = typer.Argument(None, help="User ID."),
    period: str = typer.Option("current_month", "--period", help="Usage period."),
) -> None:
    """View usage for a specific user."""
    if not user_id:
        if sys.stdin.isatty():
            user_id = input("User ID: ").strip()
            if not user_id:
                print_error("User ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument USER_ID. Usage: querri usage user USER_ID [--period PERIOD]")
            raise typer.Exit(code=1)
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
                ("period", "Period"),
                ("period_start", "Period Start"),
                ("period_end", "Period End"),
                ("ai_messages", "AI Messages"),
            ],
        )
        # Show daily breakdown if available
        if hasattr(report, "daily_breakdown") and report.daily_breakdown:
            print()
            print_table(
                report.daily_breakdown,
                [("date", "Date"), ("count", "Messages")],
            )
