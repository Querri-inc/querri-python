"""querri chat — top-level conversational command.

Sends a prompt to the active project's chat, auto-creating the chat
if one doesn't exist yet. Designed for quick, stateful interaction:

    querri project select "Sales Analysis"
    querri chat "what trends do you see?"
    querri chat "break it down by region"
"""

from __future__ import annotations

import os
import signal
import sys
from typing import Optional

import typer

from querri.cli._context import (
    get_client,
    resolve_project_id,
    resolve_user_id,
    _get_profile,
    _save_profile,
)
from querri.cli._output import (
    EXIT_SUCCESS,
    handle_api_error,
    print_error,
    print_json,
    print_success,
)

chat_app = typer.Typer(
    name="chat",
    help="Send a prompt to the active project's chat.",
    invoke_without_command=True,
    rich_markup_mode="rich",
)


@chat_app.callback(invoke_without_command=True)
def chat_command(
    ctx: typer.Context,
    prompt: Optional[str] = typer.Argument(None, help="Message to send."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model selection."),
    new: bool = typer.Option(False, "--new", help="Force a new chat session."),
) -> None:
    """Send a prompt to the active project's chat.

    Auto-creates a chat if none is active. Use --new to start a fresh
    conversation.

    Examples:
        querri chat "summarize the data"
        querri chat "show me Q4 revenue" --model gpt-4o
        querri chat "start over with a new analysis" --new
    """
    if ctx.invoked_subcommand is not None:
        return
    if prompt is None:
        # No prompt given — show help
        ctx.get_help()
        return

    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)
    is_interactive = obj.get("interactive", False)

    project_id = resolve_project_id(ctx)
    user_id = resolve_user_id(ctx)
    client = get_client(ctx)

    # Resolve or create chat
    chat_id = obj.get("chat")  # explicit --chat flag

    if not chat_id and not new:
        # Check stored active chat
        profile = _get_profile(ctx)
        if profile and profile.active_chat_id and profile.active_project_id == project_id:
            chat_id = profile.active_chat_id

    if not chat_id or new:
        # Create a new chat
        try:
            chat = client.projects.chats.create(project_id)
            chat_id = chat.id
        except Exception as exc:
            raise typer.Exit(code=handle_api_error(exc, is_json=is_json))

        if not is_json and not obj.get("quiet"):
            print(f"  New chat: {chat_id}", file=sys.stderr)

    # Save active chat
    profile = _get_profile(ctx)
    if profile:
        profile.active_chat_id = chat_id
        _save_profile(ctx, profile)

    # Stream the response
    try:
        stream = client.projects.chats.stream(
            project_id,
            chat_id,
            prompt=prompt,
            user_id=user_id,
            model=model,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json))

    # Set up Ctrl+C handler
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


# ---------------------------------------------------------------------------
# Streaming renderers (shared with chats.py)
# ---------------------------------------------------------------------------


def _stream_plain(stream: object) -> None:
    from querri._streaming import ChatStream
    assert isinstance(stream, ChatStream)

    # Debug: dump raw lines first to diagnose parsing
    if os.environ.get("QUERRI_DEBUG_STREAM"):
        for line in stream._response.iter_lines():
            print(f"[RAW] {line!r}", file=sys.stderr)
        stream._response.close()
        return

    for event in stream.events():
        if event.event_type == "text-delta" and event.text:
            print(event.text, end="", flush=True)
        elif event.event_type == "terminate":
            reason = event.terminate_reason or "unknown"
            msg = event.terminate_message or ""
            print(f"\nStream closed: {reason}. {msg}", file=sys.stderr)
        elif event.event_type == "error":
            print(f"\nError: {event.error}", file=sys.stderr)
    print()


def _stream_rich(stream: object) -> None:
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
                accumulated_text += f"\n\n**Tool: {event.tool_name}**\n"
                live.update(Markdown(accumulated_text))
            elif event.event_type == "file":
                accumulated_text += f"\n\n[{event.file_url}]({event.file_url})\n"
                live.update(Markdown(accumulated_text))
            elif event.event_type == "terminate":
                reason = event.terminate_reason or "unknown"
                msg = event.terminate_message or "Start a new chat to continue."
                console.print(f"\n[#f15a24]Stream closed: {reason}. {msg}[/#f15a24]")
            elif event.event_type == "error":
                console.print(f"\n[red]Error: {event.error}[/red]")


def _stream_json(stream: object) -> None:
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
            tool_calls.append({"tool_name": event.tool_name, "output": event.tool_data})
        elif event.event_type == "file":
            files.append({"url": event.file_url, "media_type": event.media_type})
        elif event.event_type == "finish":
            usage = event.usage
        elif event.event_type == "terminate":
            text_parts.append(f"\n[Stream closed: {event.terminate_reason}]")

    result = {
        "message_id": stream.message_id,
        "text": "".join(text_parts),
        "tool_calls": tool_calls,
        "files": files,
    }
    if usage:
        result["usage"] = usage

    print_json(result)
