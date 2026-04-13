"""querri chats — chat commands including streaming."""

from __future__ import annotations

import os
import signal
import sys

import typer

from querri.cli._context import _get_profile, get_client, resolve_project_id
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
    name="chat",
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
        "Example: querri chat stream PROJECT CHAT --message '...' --user-id USER"
    )
    if is_json:
        from querri.cli._output import print_json_error

        print_json_error("validation_error", msg, 1)
    else:
        print_error(msg)
    raise typer.Exit(code=1)


def _resolve_project(ctx: typer.Context, project_id: str | None) -> str:
    """Resolve project ID from argument → active project → interactive prompt."""
    if project_id:
        return project_id
    try:
        return resolve_project_id(ctx)
    except (typer.Exit, SystemExit):
        pass
    if sys.stdin.isatty():
        project_id = input("Project ID: ").strip()
        if project_id:
            return project_id
    print_error(
        "No active project. Select one with 'querri project select' or pass PROJECT_ID."
    )
    raise typer.Exit(code=1)


def _resolve_chat(ctx: typer.Context, chat_id: str | None) -> str:
    """Resolve chat ID from argument → active chat → interactive prompt."""
    if chat_id:
        return chat_id
    profile = _get_profile(ctx)
    if profile and profile.active_chat_id:
        return profile.active_chat_id
    if sys.stdin.isatty():
        chat_id = input("Chat ID: ").strip()
        if chat_id:
            return chat_id
    print_error("No active chat. Pass CHAT_ID or use 'querri project chat' instead.")
    raise typer.Exit(code=1)


@chats_app.command("list")
def list_chats(
    ctx: typer.Context,
    project_id: str | None = typer.Argument(
        None, help="Project ID (default: active project)."
    ),
    limit: int = typer.Option(25, "--limit", "-l", help="Max chats to return."),
) -> None:
    """List chats on a project."""
    project_id = _resolve_project(ctx, project_id)
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    try:
        client = get_client(ctx)
        chats = client.projects.chats.list(project_id, limit=limit)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json)) from None

    if is_json:
        print_json([c.model_dump(mode="json") for c in chats])
    elif obj.get("quiet"):
        for c in chats:
            print_id(c.id)
    else:
        print_table(
            chats,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("created_at", "Created"),
            ],
            ctx=ctx,
        )


@chats_app.command("get")
def get_chat(
    ctx: typer.Context,
    project_id: str | None = typer.Argument(
        None, help="Project ID (default: active project)."
    ),
    chat_id: str | None = typer.Argument(None, help="Chat ID (default: active chat)."),
) -> None:
    """Get chat details with message history."""
    project_id = _resolve_project(ctx, project_id)
    chat_id = _resolve_chat(ctx, chat_id)
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    try:
        client = get_client(ctx)
        chat = client.projects.chats.get(project_id, chat_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json)) from None

    if is_json:
        print_json(chat)
    elif obj.get("quiet"):
        print_id(chat.id)
    else:
        from querri.cli._output import print_detail

        print_detail(
            chat,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("created_at", "Created"),
            ],
        )


@chats_app.command("new")
def new_chat(
    ctx: typer.Context,
    project_id: str | None = typer.Argument(
        None, help="Project ID (default: active project)."
    ),
    name: str | None = typer.Option(None, "--name", "-n", help="Chat display name."),
) -> None:
    """Create a new chat on a project."""
    project_id = _resolve_project(ctx, project_id)
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    try:
        client = get_client(ctx)
        chat = client.projects.chats.create(project_id, name=name)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json)) from None

    if is_json:
        print_json(chat)
    elif obj.get("quiet"):
        print_id(chat.id)
    else:
        print_success(f"Created chat: {chat.id}")


@chats_app.command("delete")
def delete_chat(
    ctx: typer.Context,
    project_id: str | None = typer.Argument(
        None, help="Project ID (default: active project)."
    ),
    chat_id: str | None = typer.Argument(None, help="Chat ID (default: active chat)."),
) -> None:
    """Delete a chat from a project."""
    project_id = _resolve_project(ctx, project_id)
    chat_id = _resolve_chat(ctx, chat_id)
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    try:
        client = get_client(ctx)
        client.projects.chats.delete(project_id, chat_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json)) from None

    if is_json:
        print_json({"id": chat_id, "deleted": True})
    elif not obj.get("quiet"):
        print_success(f"Chat {chat_id} deleted.")


@chats_app.command("cancel")
def cancel_chat(
    ctx: typer.Context,
    project_id: str | None = typer.Argument(
        None, help="Project ID (default: active project)."
    ),
    chat_id: str | None = typer.Argument(None, help="Chat ID (default: active chat)."),
) -> None:
    """Cancel an active chat stream."""
    project_id = _resolve_project(ctx, project_id)
    chat_id = _resolve_chat(ctx, chat_id)
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    try:
        client = get_client(ctx)
        result = client.projects.chats.cancel(project_id, chat_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json)) from None

    if is_json:
        print_json(result)
    elif not obj.get("quiet"):
        print_success("Chat stream cancelled.")


@chats_app.command("stream")
def stream_chat(
    ctx: typer.Context,
    project_id: str | None = typer.Argument(
        None, help="Project ID (default: active project)."
    ),
    chat_id: str | None = typer.Argument(None, help="Chat ID (default: active chat)."),
    message: str | None = typer.Option(
        None, "--message", "-m", help="Message to send."
    ),
    user_id: str | None = typer.Option(
        None,
        "--user-id",
        "-u",
        help="User ID (or set QUERRI_USER_ID env var).",
    ),
    model: str | None = typer.Option(None, "--model", help="Model selection."),
    reasoning: bool = typer.Option(False, "--reasoning", help="Show reasoning traces."),
) -> None:
    """Send a message and stream the AI response.

    In interactive mode, renders markdown with Rich Live display.
    In --json mode, accumulates the full response and outputs structured JSON.
    In non-TTY mode, outputs plain text.
    """
    project_id = _resolve_project(ctx, project_id)
    chat_id = _resolve_chat(ctx, chat_id)
    prompt = message
    if not prompt:
        if sys.stdin.isatty():
            prompt = input("Message: ").strip()
            if not prompt:
                print_error("Message is required.")
                raise typer.Exit(code=1)
        else:
            print_error(
                "Missing required option --message. "
                "Usage: querri chat stream "
                "PROJECT_ID CHAT_ID "
                "--message MESSAGE --user-id USER_ID"
            )
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
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json)) from None

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
            raise typer.Exit(code=handle_api_error(exc, is_json=is_json)) from None
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
    """Accumulate full response and output structured
    JSON -- delegates to chat module."""
    from querri.cli.chat import _stream_json as _chat_stream_json

    _chat_stream_json(stream)
