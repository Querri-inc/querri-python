"""querri chats — chat commands including streaming."""

from __future__ import annotations

import os
import signal
import sys
from typing import Optional

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    EXIT_SUCCESS,
    handle_api_error,
    print_error,
    print_id,
    print_json,
    print_success,
    print_table,
)

chats_app = typer.Typer(
    name="chats",
    help="Manage project chats and stream AI responses.",
    no_args_is_help=True,
)


def _resolve_user_id(
    user_id_flag: str | None,
    *,
    ctx: typer.Context,
) -> str:
    """Resolve user ID from flag → env var → error.

    Resolution order (per SPEC):
    1. JWT auth → sub claim (v0.2.1)
    2. API key → bound_user_id (v0.2.1)
    3. QUERRI_USER_ID env var
    4. --user-id flag
    """
    # For v0.2.0, we only support env var and flag
    if user_id_flag:
        return user_id_flag

    env_user = os.environ.get("QUERRI_USER_ID")
    if env_user:
        return env_user

    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)
    msg = (
        "User ID required. Set QUERRI_USER_ID env var or pass --user-id.\n"
        "Example: querri chats stream PROJECT CHAT --prompt '...' --user-id USER"
    )
    if is_json:
        from querri.cli._output import print_json_error
        print_json_error("validation_error", msg, 1)
    else:
        print_error(msg)
    raise typer.Exit(code=1)


@chats_app.command("list")
def list_chats(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project UUID."),
    limit: int = typer.Option(25, "--limit", "-l", help="Max chats to return."),
) -> None:
    """List chats on a project."""
    if not project_id:
        if sys.stdin.isatty():
            project_id = input("Project ID: ").strip()
            if not project_id:
                print_error("Project ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument PROJECT_ID. Usage: querri chats list PROJECT_ID")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    try:
        client = get_client(ctx)
        chats = client.projects.chats.list(project_id, limit=limit)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json))

    if is_json:
        print_json([c.model_dump(mode="json") for c in chats])
    elif obj.get("quiet"):
        for c in chats:
            print_id(c.id)
    else:
        print_table(chats, [
            ("id", "ID"),
            ("name", "Name"),
            ("created_at", "Created"),
        ], ctx=ctx)


@chats_app.command("get")
def get_chat(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project UUID."),
    chat_id: Optional[str] = typer.Argument(None, help="Chat UUID."),
) -> None:
    """Get chat details with message history."""
    if not project_id:
        if sys.stdin.isatty():
            project_id = input("Project ID: ").strip()
            if not project_id:
                print_error("Project ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument PROJECT_ID. Usage: querri chats get PROJECT_ID CHAT_ID")
            raise typer.Exit(code=1)
    if not chat_id:
        if sys.stdin.isatty():
            chat_id = input("Chat ID: ").strip()
            if not chat_id:
                print_error("Chat ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument CHAT_ID. Usage: querri chats get PROJECT_ID CHAT_ID")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    try:
        client = get_client(ctx)
        chat = client.projects.chats.get(project_id, chat_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json))

    if is_json:
        print_json(chat)
    elif obj.get("quiet"):
        print_id(chat.id)
    else:
        from querri.cli._output import print_detail
        print_detail(chat, [
            ("id", "ID"),
            ("name", "Name"),
            ("created_at", "Created"),
        ])


@chats_app.command("create")
def create_chat(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project UUID."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Chat display name."),
) -> None:
    """Create a new chat on a project."""
    if not project_id:
        if sys.stdin.isatty():
            project_id = input("Project ID: ").strip()
            if not project_id:
                print_error("Project ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument PROJECT_ID. Usage: querri chats create PROJECT_ID [--name NAME]")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    try:
        client = get_client(ctx)
        chat = client.projects.chats.create(project_id, name=name)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json))

    if is_json:
        print_json(chat)
    elif obj.get("quiet"):
        print_id(chat.id)
    else:
        print_success(f"Chat created: {chat.id}")


@chats_app.command("delete")
def delete_chat(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project UUID."),
    chat_id: Optional[str] = typer.Argument(None, help="Chat UUID."),
) -> None:
    """Delete a chat from a project."""
    if not project_id:
        if sys.stdin.isatty():
            project_id = input("Project ID: ").strip()
            if not project_id:
                print_error("Project ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument PROJECT_ID. Usage: querri chats delete PROJECT_ID CHAT_ID")
            raise typer.Exit(code=1)
    if not chat_id:
        if sys.stdin.isatty():
            chat_id = input("Chat ID: ").strip()
            if not chat_id:
                print_error("Chat ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument CHAT_ID. Usage: querri chats delete PROJECT_ID CHAT_ID")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    try:
        client = get_client(ctx)
        client.projects.chats.delete(project_id, chat_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json))

    if is_json:
        print_json({"id": chat_id, "deleted": True})
    elif not obj.get("quiet"):
        print_success(f"Chat {chat_id} deleted.")


@chats_app.command("cancel")
def cancel_chat(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project UUID."),
    chat_id: Optional[str] = typer.Argument(None, help="Chat UUID."),
) -> None:
    """Cancel an active chat stream."""
    if not project_id:
        if sys.stdin.isatty():
            project_id = input("Project ID: ").strip()
            if not project_id:
                print_error("Project ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument PROJECT_ID. Usage: querri chats cancel PROJECT_ID CHAT_ID")
            raise typer.Exit(code=1)
    if not chat_id:
        if sys.stdin.isatty():
            chat_id = input("Chat ID: ").strip()
            if not chat_id:
                print_error("Chat ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument CHAT_ID. Usage: querri chats cancel PROJECT_ID CHAT_ID")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    try:
        client = get_client(ctx)
        result = client.projects.chats.cancel(project_id, chat_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json))

    if is_json:
        print_json(result)
    elif not obj.get("quiet"):
        print_success("Chat stream cancelled.")


@chats_app.command("stream")
def stream_chat(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project UUID."),
    chat_id: Optional[str] = typer.Argument(None, help="Chat UUID."),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="User message to send."),
    user_id: Optional[str] = typer.Option(
        None, "--user-id", "-u",
        help="User ID (or set QUERRI_USER_ID env var).",
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model selection."),
    reasoning: bool = typer.Option(False, "--reasoning", "-r", help="Show reasoning traces."),
) -> None:
    """Send a message and stream the AI response.

    In interactive mode, renders markdown with Rich Live display.
    In --json mode, accumulates the full response and outputs structured JSON.
    In non-TTY mode, outputs plain text.
    """
    if not project_id:
        if sys.stdin.isatty():
            project_id = input("Project ID: ").strip()
            if not project_id:
                print_error("Project ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument PROJECT_ID. Usage: querri chats stream PROJECT_ID CHAT_ID --prompt PROMPT --user-id USER_ID")
            raise typer.Exit(code=1)
    if not chat_id:
        if sys.stdin.isatty():
            chat_id = input("Chat ID: ").strip()
            if not chat_id:
                print_error("Chat ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument CHAT_ID. Usage: querri chats stream PROJECT_ID CHAT_ID --prompt PROMPT --user-id USER_ID")
            raise typer.Exit(code=1)
    if not prompt:
        if sys.stdin.isatty():
            prompt = input("Prompt: ").strip()
            if not prompt:
                print_error("Prompt is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required option --prompt. Usage: querri chats stream PROJECT_ID CHAT_ID --prompt PROMPT --user-id USER_ID")
            raise typer.Exit(code=1)

    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)
    is_interactive = obj.get("interactive", False)

    resolved_user_id = _resolve_user_id(user_id, ctx=ctx)

    try:
        client = get_client(ctx)
        stream = client.projects.chats.stream(
            project_id,
            chat_id,
            prompt=prompt,
            user_id=resolved_user_id,
            model=model,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json))

    # Set up Ctrl+C handler for clean cancellation
    cancelled = False

    def _sigint_handler(signum: int, frame: object) -> None:
        nonlocal cancelled
        cancelled = True
        stream._signal_cancel()

    old_handler = signal.signal(signal.SIGINT, _sigint_handler)

    try:
        if is_json:
            _stream_json(stream)
        elif is_interactive:
            _stream_rich(stream, show_reasoning=reasoning)
        else:
            _stream_plain(stream, show_reasoning=reasoning)
    except Exception as exc:
        if not cancelled:
            raise typer.Exit(code=handle_api_error(exc, is_json=is_json))
    finally:
        signal.signal(signal.SIGINT, old_handler)

    if cancelled:
        print_error("Stream cancelled.")
        raise typer.Exit(code=EXIT_SUCCESS)


def _stream_plain(stream: object, *, show_reasoning: bool = False) -> None:
    """Stream text to stdout without formatting — delegates to chat module."""
    from querri.cli.chat import _stream_plain as _chat_stream_plain
    _chat_stream_plain(stream, show_reasoning=show_reasoning)


def _stream_rich(stream: object, *, show_reasoning: bool = False) -> None:
    """Stream with Rich Live markdown rendering — delegates to chat module."""
    from querri.cli.chat import _stream_rich as _chat_stream_rich
    _chat_stream_rich(stream, show_reasoning=show_reasoning)


def _stream_json(stream: object) -> None:
    """Accumulate full response and output structured JSON — delegates to chat module."""
    from querri.cli.chat import _stream_json as _chat_stream_json
    _chat_stream_json(stream)
