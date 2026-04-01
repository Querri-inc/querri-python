"""querri chats — chat commands including streaming."""

from __future__ import annotations

import json
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
    project_id: str = typer.Argument(help="Project UUID."),
    limit: int = typer.Option(25, "--limit", "-l", help="Max chats to return."),
) -> None:
    """List chats on a project."""
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
    project_id: str = typer.Argument(help="Project UUID."),
    chat_id: str = typer.Argument(help="Chat UUID."),
) -> None:
    """Get chat details with message history."""
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
    project_id: str = typer.Argument(help="Project UUID."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Chat display name."),
) -> None:
    """Create a new chat on a project."""
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
    project_id: str = typer.Argument(help="Project UUID."),
    chat_id: str = typer.Argument(help="Chat UUID."),
) -> None:
    """Delete a chat from a project."""
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
    project_id: str = typer.Argument(help="Project UUID."),
    chat_id: str = typer.Argument(help="Chat UUID."),
) -> None:
    """Cancel an active chat stream."""
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
    project_id: str = typer.Argument(help="Project UUID."),
    chat_id: str = typer.Argument(help="Chat UUID."),
    prompt: str = typer.Option(..., "--prompt", "-p", help="User message to send."),
    user_id: Optional[str] = typer.Option(
        None, "--user-id", "-u",
        help="User ID (or set QUERRI_USER_ID env var).",
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model selection."),
) -> None:
    """Send a message and stream the AI response.

    In interactive mode, renders markdown with Rich Live display.
    In --json mode, accumulates the full response and outputs structured JSON.
    In non-TTY mode, outputs plain text.
    """
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
            _stream_rich(stream)
        else:
            _stream_plain(stream)
    except Exception as exc:
        if not cancelled:
            raise typer.Exit(code=handle_api_error(exc, is_json=is_json))
    finally:
        signal.signal(signal.SIGINT, old_handler)

    if cancelled:
        print_error("Stream cancelled.")
        raise typer.Exit(code=EXIT_SUCCESS)


def _stream_plain(stream: object) -> None:
    """Stream text to stdout without formatting."""
    from querri._streaming import ChatStream
    assert isinstance(stream, ChatStream)

    for event in stream.events():
        if event.event_type == "text-delta" and event.text:
            print(event.text, end="", flush=True)
        elif event.event_type == "terminate":
            reason = event.terminate_reason or "unknown"
            msg = event.terminate_message or ""
            print(f"\nStream closed: {reason}. {msg}", file=sys.stderr)
        elif event.event_type == "error":
            print(f"\nError: {event.error}", file=sys.stderr)
    print()  # trailing newline


def _stream_rich(stream: object) -> None:
    """Stream with Rich Live markdown rendering."""
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown

    from querri._streaming import ChatStream
    assert isinstance(stream, ChatStream)

    console = Console()
    accumulated_text = ""

    with Live(Markdown(""), console=console, refresh_per_second=10) as live:
        for event in stream.events():
            if event.event_type == "text-delta" and event.text:
                accumulated_text += event.text
                live.update(Markdown(accumulated_text))
            elif event.event_type == "tool-output-available":
                tool_info = f"\n\n**Tool: {event.tool_name}**\n"
                accumulated_text += tool_info
                live.update(Markdown(accumulated_text))
            elif event.event_type == "file":
                file_info = f"\n\n📎 [{event.file_url}]({event.file_url})\n"
                accumulated_text += file_info
                live.update(Markdown(accumulated_text))
            elif event.event_type == "terminate":
                reason = event.terminate_reason or "unknown"
                msg = event.terminate_message or "Start a new chat to continue."
                console.print(f"\n[yellow]Stream closed: {reason}. {msg}[/yellow]")
            elif event.event_type == "error":
                console.print(f"\n[red]Error: {event.error}[/red]")


def _stream_json(stream: object) -> None:
    """Accumulate full response and output structured JSON."""
    from querri._streaming import ChatStream
    assert isinstance(stream, ChatStream)

    text_parts: list[str] = []
    tool_calls: list[dict] = []
    files: list[dict] = []
    usage: dict | None = None

    for event in stream.events():
        if event.event_type == "text-delta" and event.text:
            text_parts.append(event.text)
        elif event.event_type == "tool-output-available":
            tool_calls.append({
                "tool_name": event.tool_name,
                "output": event.tool_data,
            })
        elif event.event_type == "file":
            files.append({
                "url": event.file_url,
                "media_type": event.media_type,
            })
        elif event.event_type == "finish":
            usage = event.usage
        elif event.event_type == "terminate":
            text_parts.append(
                f"\n[Stream closed: {event.terminate_reason}]"
            )

    result = {
        "message_id": stream.message_id,
        "text": "".join(text_parts),
        "tool_calls": tool_calls,
        "files": files,
    }
    if usage:
        result["usage"] = usage

    print_json(result)
