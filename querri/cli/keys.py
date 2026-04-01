"""querri keys — manage API keys."""

from __future__ import annotations

import json
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

keys_app = typer.Typer(
    name="keys",
    help="Manage API keys for the organization.",
    no_args_is_help=True,
)


@keys_app.command("list")
def list_keys(
    ctx: typer.Context,
) -> None:
    """List API keys."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.keys.list()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json([k.model_dump(mode="json") for k in items])
    elif obj.get("quiet"):
        for k in items:
            print_id(k.id)
    else:
        print_table(
            items,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("key_prefix", "Prefix"),
                ("status", "Status"),
                ("last_used_at", "Last Used"),
                ("expires_at", "Expires"),
            ],
            ctx=ctx,
        )


@keys_app.command("get")
def get_key(
    ctx: typer.Context,
    key_id: str = typer.Argument(help="API key ID."),
) -> None:
    """Get API key details."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        key = client.keys.get(key_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(key)
    elif obj.get("quiet"):
        print_id(key.id)
    else:
        print_detail(
            key,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("key_prefix", "Key Prefix"),
                ("scopes", "Scopes"),
                ("status", "Status"),
                ("rate_limit_per_minute", "Rate Limit"),
                ("created_by", "Created By"),
                ("created_at", "Created"),
                ("last_used_at", "Last Used"),
                ("expires_at", "Expires"),
            ],
        )


@keys_app.command("create")
def create_key(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", "-n", help="Key name."),
    scopes: str = typer.Option(..., "--scopes", "-s", help="Comma-separated scopes."),
    expires_in_days: Optional[int] = typer.Option(None, "--expires-in-days", help="Days until expiry."),
    bound_user_id: Optional[str] = typer.Option(None, "--bound-user-id", help="Bind key to a user ID."),
    rate_limit: Optional[int] = typer.Option(None, "--rate-limit", help="Requests per minute."),
    ip_allowlist: Optional[str] = typer.Option(None, "--ip-allowlist", help="Comma-separated IP allowlist."),
) -> None:
    """Create a new API key.

    The full key value is shown only once — save it immediately.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    scope_list = [s.strip() for s in scopes.split(",")]
    ip_list = [ip.strip() for ip in ip_allowlist.split(",")] if ip_allowlist else None

    try:
        key = client.keys.create(
            name=name,
            scopes=scope_list,
            expires_in_days=expires_in_days,
            bound_user_id=bound_user_id,
            rate_limit_per_minute=rate_limit,
            ip_allowlist=ip_list,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(key)
    elif obj.get("quiet"):
        # In quiet mode, output the bare secret for piping
        print(key.secret)
    else:
        from querri.cli._output import IS_INTERACTIVE

        print_success(f"Created API key: {key.name} ({key.id})")
        if IS_INTERACTIVE:
            from rich.console import Console
            from rich.panel import Panel

            console = Console(stderr=True)
            console.print(Panel(
                f"[bold]{key.secret}[/bold]",
                title="API Key Secret",
                subtitle="Save now — cannot be retrieved later",
                border_style="yellow",
                padding=(1, 2),
            ))
        else:
            import sys
            print(f"Secret: {key.secret}", file=sys.stderr)
            print("Save this key now — it cannot be retrieved later.", file=sys.stderr)


@keys_app.command("delete")
def delete_key(
    ctx: typer.Context,
    key_id: str = typer.Argument(help="API key ID."),
) -> None:
    """Delete an API key."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.keys.delete(key_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"id": key_id, "deleted": True})
    else:
        print_success(f"Deleted API key {key_id}")
