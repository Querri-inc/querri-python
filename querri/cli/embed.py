"""querri embed — manage embedded analytics sessions."""

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

embed_app = typer.Typer(
    name="embed",
    help="Manage embedded analytics sessions.",
    no_args_is_help=True,
)


@embed_app.command("create-session")
def create_session(
    ctx: typer.Context,
    user_id: Optional[str] = typer.Option(None, "--user-id", help="User ID for the session."),
    origin: Optional[str] = typer.Option(None, "--origin", help="Allowed origin URL."),
    ttl: int = typer.Option(3600, "--ttl", help="Session TTL in seconds."),
) -> None:
    """Create an embedded analytics session."""
    if not user_id:
        if sys.stdin.isatty():
            user_id = input("User ID: ").strip()
            if not user_id:
                print_error("User ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument --user-id. Usage: querri embed create-session --user-id USER_ID")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        session = client.embed.create_session(user_id=user_id, origin=origin, ttl=ttl)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(session)
    elif obj.get("quiet"):
        print(session.session_token)
    else:
        print_success("Created embed session")
        print_detail(
            session,
            [("session_token", "Token"), ("expires_in", "Expires In (s)"), ("user_id", "User ID")],
        )


@embed_app.command("refresh-session")
def refresh_session(
    ctx: typer.Context,
    session_token: Optional[str] = typer.Option(None, "--token", help="Session token to refresh."),
) -> None:
    """Refresh an embedded analytics session."""
    if not session_token:
        if sys.stdin.isatty():
            session_token = input("Session token: ").strip()
            if not session_token:
                print_error("Session token is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument --token. Usage: querri embed refresh-session --token TOKEN")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        session = client.embed.refresh_session(session_token=session_token)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(session)
    elif obj.get("quiet"):
        print(session.session_token)
    else:
        print_success("Refreshed embed session")
        print_detail(
            session,
            [("session_token", "Token"), ("expires_in", "Expires In (s)")],
        )


@embed_app.command("list-sessions")
def list_sessions(
    ctx: typer.Context,
    limit: int = typer.Option(100, "--limit", "-n", help="Max results."),
) -> None:
    """List active embed sessions."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.embed.list_sessions(limit=limit)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_table(
            result.data,
            [
                ("session_token", "Token"),
                ("user_id", "User ID"),
                ("origin", "Origin"),
                ("created_at", "Created"),
                ("auth_method", "Auth"),
            ],
            ctx=ctx,
        )


@embed_app.command("revoke-session")
def revoke_session(
    ctx: typer.Context,
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Session ID."),
    session_token: Optional[str] = typer.Option(None, "--token", help="Session token."),
) -> None:
    """Revoke an embed session (by ID or token)."""
    obj = ctx.ensure_object(dict)

    if not session_id and not session_token:
        print_error("Provide --session-id or --token.")
        raise typer.Exit(code=1)

    client = get_client(ctx)
    try:
        result = client.embed.revoke_session(session_id, session_token=session_token)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Revoked session {session_id or session_token}")


@embed_app.command("get-session")
def get_session(
    ctx: typer.Context,
    user: Optional[str] = typer.Option(None, "--user", help="User ID or JSON user object."),
    origin: Optional[str] = typer.Option(None, "--origin", help="Allowed origin."),
    ttl: int = typer.Option(3600, "--ttl", help="Session TTL in seconds."),
    access: Optional[str] = typer.Option(None, "--access", help="JSON access config."),
) -> None:
    """Get or create a session using the convenience method."""
    if not user:
        if sys.stdin.isatty():
            user = input("User (ID or JSON): ").strip()
            if not user:
                print_error("User is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument --user. Usage: querri embed get-session --user USER")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    # Parse user — could be a bare ID or JSON object
    try:
        user_obj = json.loads(user)
    except json.JSONDecodeError:
        user_obj = user  # Treat as bare user ID

    access_obj = None
    if access:
        try:
            access_obj = json.loads(access)
        except json.JSONDecodeError as exc:
            print_error(f"Invalid JSON for --access: {exc}")
            raise typer.Exit(code=1)

    try:
        result = client.embed.get_session(user=user_obj, access=access_obj, origin=origin, ttl=ttl)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    elif obj.get("quiet"):
        print(result.get("session_token", result.get("token", "")))
    else:
        print_json(result)
