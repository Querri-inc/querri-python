"""querri project chat — conversational command.

Sends a message to the active project's chat, auto-creating the chat
if one doesn't exist yet. Designed for quick, stateful interaction:

    querri project select "Sales Analysis"
    querri project chat -m "what trends do you see?"
    querri project chat -m "break it down by region"
"""

from __future__ import annotations

import logging
import os
import re
import signal
import sys

logger = logging.getLogger("querri.cli")

import typer

from querri.cli._context import (
    _get_profile,
    _save_profile,
    get_client,
    resolve_project_id,
    resolve_user_id,
)
from querri.cli._output import (
    EXIT_SUCCESS,
    handle_api_error,
    print_error,
    print_json,
    print_success,
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")

_STATUS_ICONS = {
    "thinking": "💭",
    "analyzing": "📊",
    "executing": "⚙",
}


def _strip_html(text: str) -> str:
    """Strip HTML tags from a string."""
    return _HTML_TAG_RE.sub("", text).strip()


def _setup_debug_log() -> object:
    """Set up debug logging to ``~/.querri/debug.log``. Returns the file handle."""
    from datetime import datetime
    from pathlib import Path

    log_dir = Path.home() / ".querri"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "debug.log"
    fh = open(log_path, "a")  # noqa: SIM115
    fh.write(f"\n{'='*60}\n")
    fh.write(f"Debug session started: {datetime.now().isoformat()}\n")
    fh.write(f"{'='*60}\n")
    fh.flush()
    print(f"  Debug log: {log_path}", file=sys.stderr)
    return fh


def _debug(log: object | None, msg: str) -> None:
    """Write a timestamped line to the debug log."""
    if log is None:
        return
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    log.write(f"[{ts}] {msg}\n")  # type: ignore[union-attr]
    log.flush()  # type: ignore[union-attr]


project_chat_app = typer.Typer(
    name="chat",
    help="Chat with the active project — send messages and manage conversation.",
    invoke_without_command=True,
    rich_markup_mode="rich",
)


@project_chat_app.callback(invoke_without_command=True)
def chat_command(
    ctx: typer.Context,
    prompt: str | None = typer.Option(None, "--message", "-m", help="Message to send."),
    model: str | None = typer.Option(None, "--model", help="Model selection."),
    new: bool = typer.Option(False, "--new", help="Force a new chat session."),
    reasoning: bool = typer.Option(False, "--reasoning", help="Show reasoning traces."),
    experimental_v2: bool = typer.Option(False, "--experimental-v2", "--v2", help="Use experimental v2 agent (faster, direct SQL execution)."),
    debug: bool = typer.Option(False, "--debug", help="Log all stream events to ~/.querri/debug.log"),
) -> None:
    """Send a message to the active project's chat.

    Auto-creates a chat if none is active. Use --new to start a fresh
    conversation.

    Examples:
        querri project chat -m "summarize the data"
        querri project chat --message "show me Q4 revenue" --model gpt-4o
        querri project chat -m "start over" --new
    """
    if ctx.invoked_subcommand is not None:
        return
    if prompt is None:
        ctx.get_help()
        return

    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)
    is_interactive = obj.get("interactive", False)

    # Set up debug logging
    debug_log = None
    if debug:
        debug_log = _setup_debug_log()

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

    if not chat_id and not new:
        # Try to find existing chat for this project
        existing = _fetch_project_chat(client, project_id)
        if existing:
            chat_id = existing.get("uuid") or existing.get("id")

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

    # Echo the user prompt before streaming
    if not is_json and is_interactive:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        from querri.cli._output import QUERRI_ORANGE
        _console = Console()
        _console.print(Panel(
            Text(prompt),
            title="[bold]You[/bold]", title_align="right",
            border_style=QUERRI_ORANGE, padding=(0, 1),
            width=min(_console.width - 10, 80),
        ), justify="right")
    elif not is_json:
        from querri.cli._output import QUERRI_ORANGE
        print(f"\n> {prompt}\n", file=sys.stderr)

    # Stream the response
    try:
        stream = client.projects.chats.stream(
            project_id,
            chat_id,
            prompt=prompt,
            user_id=user_id,
            model=model,
            experimental_v2=experimental_v2,
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
            _stream_rich(stream, show_reasoning=reasoning, project_id=project_id, client=client, debug_log=debug_log)
        else:
            _stream_plain(stream, show_reasoning=reasoning, project_id=project_id, client=client, debug_log=debug_log)
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


def _stream_plain(
    stream: object,
    *,
    show_reasoning: bool = False,
    project_id: str | None = None,
    client: object | None = None,
    debug_log: object | None = None,
) -> None:
    from querri._streaming import ChatStream
    assert isinstance(stream, ChatStream)

    # Debug: dump raw lines first to diagnose parsing
    if os.environ.get("QUERRI_DEBUG_STREAM"):
        for line in stream._response.iter_lines():
            print(f"[RAW] {line!r}", file=sys.stderr)
        stream._response.close()
        return

    final_steps: dict[str, dict] = {}
    step_results_rendered = False
    _rendered_step_ids.clear()
    last_status = ""

    _debug(debug_log, f"Stream started (project={project_id})")

    for event in stream.events():
        _debug(debug_log, f"Event: {event.event_type} text={bool(event.text)} raw={str(event.raw_data or '')[:120]}")

        if event.event_type == "status-update":
            import json as _json
            parsed_su = _json.loads(event.raw_data) if event.raw_data else {}
            level = parsed_su.get("level", "thinking")
            icon = _STATUS_ICONS.get(level, "💭")
            msg = event.text or ""
            if msg and msg != last_status:
                # Overwrite previous status line with \r
                print(f"\r\033[K  {icon} {msg}", end="", flush=True, file=sys.stderr)
                last_status = msg

        elif event.event_type == "reasoning-start":
            if show_reasoning:
                print("\n--- Reasoning ---", file=sys.stderr)
        elif event.event_type == "reasoning-delta" and event.reasoning_text:
            if show_reasoning:
                print(event.reasoning_text, end="", flush=True, file=sys.stderr)
        elif event.event_type == "reasoning-end":
            if show_reasoning:
                print("\n-----------------\n", file=sys.stderr)
        elif event.event_type == "text-delta" and event.text:
            if last_status:
                # Clear the status line before printing text
                print("\r\033[K", end="", file=sys.stderr)
                last_status = ""
            print(event.text, end="", flush=True)
        elif event.event_type == "step-result":
            # Immediate step result — render inline now
            if last_status:
                print("\r\033[K", end="", file=sys.stderr)
                last_status = ""
            if project_id and client:
                from rich.console import Console
                _render_step_result_event(Console(), event, project_id, client)
                step_results_rendered = True
                final_steps.clear()  # Prevent fallback from re-rendering
        elif event.event_type == "tool-output-available":
            if event.tool_name != "usage":
                if not step_results_rendered:
                    _accumulate_tool_output(event, final_steps)
                status = _get_step_status_short(event.tool_data)
                if status and status != last_status:
                    print(f"\r\033[K  ⚙ {status}", end="", flush=True, file=sys.stderr)
                    last_status = status
        elif event.event_type == "terminate":
            reason = event.terminate_reason or "unknown"
            msg = event.terminate_message or ""
            print(f"\nStream closed: {reason}. {msg}", file=sys.stderr)
        elif event.event_type == "error":
            print(f"\nError: {event.error}", file=sys.stderr)

    # Clear any remaining status line
    if last_status:
        print("\r\033[K", end="", file=sys.stderr)
    print()

    _debug(debug_log, "Stream ended")

    # Fall back to accumulated steps if no step-result events were received
    # (older server versions that don't emit step-result)
    if not step_results_rendered and final_steps and project_id:
        from rich.console import Console
        _render_accumulated_steps(Console(), final_steps, project_id, client)



def _stream_rich(
    stream: object,
    *,
    show_reasoning: bool = False,
    project_id: str | None = None,
    client: object | None = None,
    debug_log: object | None = None,
) -> None:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text

    from querri._streaming import ChatStream
    assert isinstance(stream, ChatStream)

    console = Console()
    reasoning_text = ""
    response_text = ""
    status_line = ""  # Transient status (from server status-update or step progress)
    # Accumulate the latest tool output per step UUID from the stream
    final_steps: dict[str, dict] = {}
    step_results_rendered = False
    _rendered_step_ids.clear()

    def _build_display() -> Group:
        parts: list[object] = []
        if reasoning_text and show_reasoning:
            parts.append(Panel(
                Text(reasoning_text, style="dim italic"),
                title="[dim]Reasoning[/dim]", title_align="left",
                border_style="dim", padding=(0, 1),
            ))
        elif reasoning_text and not show_reasoning:
            lines = reasoning_text.strip().count("\n") + 1
            parts.append(Text(f"  Reasoning ({lines} lines) — rerun with --reasoning to expand", style="dim"))
        if response_text:
            parts.append(Markdown(response_text))
        # Transient status at the very bottom (replaces each time)
        if status_line:
            parts.append(Text(f"  {status_line}", style="dim"))
        return Group(*parts) if parts else Group(Text(""))

    _debug(debug_log, f"Stream started (project={project_id})")

    with Live(Text(""), console=console, refresh_per_second=10) as live:
        for event in stream.events():
            _debug(debug_log, f"Event: {event.event_type} text={bool(event.text)} raw={str(event.raw_data or '')[:120]}")

            if event.event_type == "status-update":
                import json as _json
                parsed_su = _json.loads(event.raw_data) if event.raw_data else {}
                level = parsed_su.get("level", "thinking")
                icon = _STATUS_ICONS.get(level, "💭")
                status_line = f"{icon} {event.text}" if event.text else ""
                live.update(_build_display())

            elif event.event_type == "reasoning-start":
                pass
            elif event.event_type == "reasoning-delta" and event.reasoning_text:
                reasoning_text += event.reasoning_text
                live.update(_build_display())
            elif event.event_type == "reasoning-end":
                live.update(_build_display())
            elif event.event_type == "text-delta" and event.text:
                status_line = ""  # Clear status when text starts arriving
                response_text += event.text
                live.update(_build_display())
            elif event.event_type == "step-result":
                # Step completed with full result — render immediately
                step_results_rendered = True
                final_steps.clear()
                # Exit Live context temporarily to render the step panel
                live.stop()
                if project_id and client:
                    _render_step_result_event(console, event, project_id, client)
                live.start()
            elif event.event_type == "tool-output-available":
                if event.tool_name != "usage":
                    if not step_results_rendered:
                        _accumulate_tool_output(event, final_steps)
                    new_status = _get_step_status_short(event.tool_data)
                    if new_status:
                        status_line = f"⚙ {new_status}"
                    live.update(_build_display())
            elif event.event_type == "terminate":
                reason = event.terminate_reason or "unknown"
                msg = event.terminate_message or "Start a new chat to continue."
                console.print(f"\n[dim]Stream closed: {reason}. {msg}[/dim]")
            elif event.event_type == "error":
                console.print(f"\n[red]Error: {event.error}[/red]")

    _debug(debug_log, "Stream ended")

    # Fall back to accumulated steps if no step-result events were received
    if not step_results_rendered and final_steps and project_id:
        _render_accumulated_steps(console, final_steps, project_id, client)


def _stream_json(stream: object) -> None:
    from querri._streaming import ChatStream
    assert isinstance(stream, ChatStream)

    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls: list[dict] = []
    files: list[dict] = []
    usage: dict | None = None

    for event in stream.events():
        if event.event_type == "text-delta" and event.text:
            text_parts.append(event.text)
        elif event.event_type == "reasoning-delta" and event.reasoning_text:
            reasoning_parts.append(event.reasoning_text)
        elif event.event_type == "tool-output-available":
            tool_calls.append({"tool_name": event.tool_name, "output": event.tool_data})
        elif event.event_type == "file":
            files.append({"url": event.file_url, "media_type": event.media_type})
        elif event.event_type == "finish":
            usage = event.usage
        elif event.event_type == "terminate":
            text_parts.append(f"\n[Stream closed: {event.terminate_reason}]")

    result: dict = {
        "message_id": stream.message_id,
        "text": "".join(text_parts),
        "tool_calls": tool_calls,
        "files": files,
    }
    if reasoning_parts:
        result["reasoning"] = "".join(reasoning_parts)
    if usage:
        result["usage"] = usage

    print_json(result)


# ---------------------------------------------------------------------------
# Streaming step accumulation + post-stream rendering
# ---------------------------------------------------------------------------


def _accumulate_tool_output(event: object, final_steps: dict[str, dict]) -> None:
    """Accumulate the latest step data from a ``tool-output-available`` stream event.

    The server sends multiple progress updates per step. We keep the latest
    data for each step UUID, keyed by UUID. The final event with
    ``status: "success"`` has the complete ``result`` data.
    """
    tool_data = getattr(event, "tool_data", None)
    if not isinstance(tool_data, dict):
        return
    steps = tool_data.get("steps")
    if not isinstance(steps, dict):
        return
    for sid, sdata in steps.items():
        if isinstance(sdata, dict):
            final_steps[sid] = sdata


def _get_step_status(tool_data: object) -> str:
    """Extract a human-readable status string from a tool-output-available event."""
    if not isinstance(tool_data, dict):
        return ""
    msg = tool_data.get("message", "")
    if msg:
        return msg
    steps = tool_data.get("steps", {})
    if isinstance(steps, dict):
        for sdata in steps.values():
            if isinstance(sdata, dict):
                name = sdata.get("name", "")
                status = sdata.get("status", "")
                if name:
                    return f"{name} — {status}" if status else name
    return ""


def _get_step_status_short(tool_data: object) -> str:
    """Extract a concise status — only shows step name when running or completing."""
    if not isinstance(tool_data, dict):
        return ""
    status_msg = tool_data.get("status", "")
    # Only show the final "success" / completion, not intermediate repeats
    if status_msg == "success":
        return ""  # suppress — we'll render the full step result below
    steps = tool_data.get("steps", {})
    if not isinstance(steps, dict):
        return ""
    for sdata in steps.values():
        if isinstance(sdata, dict):
            name = sdata.get("name", "")
            status = sdata.get("status", "")
            sm = sdata.get("status_message", "")
            if name and status in ("running", "starting"):
                return f"{name}{'  ' + sm if sm else ''}…"
            if name and status == "complete":
                return f"{name} ✓"
    return ""


def _render_step_result_event(
    console: object,
    event: object,
    project_id: str,
    client: object,
) -> None:
    """Render a step-result event inline during streaming."""
    result = getattr(event, "step_result", None) or {}
    tool_name = getattr(event, "tool_name", "") or ""

    base_url, auth_headers = _resolve_internal_url(client)

    _ICONS = {
        "duckdb_query": "🔍", "draw_figure": "📊", "source": "📂",
        "add_source": "📂", "load": "📂", "python": "🐍", "coder": "🐍",
    }

    qdf = result.get("qdf") or {}
    if isinstance(qdf, str):
        qdf = {}
    step = {
        "name": result.get("name") or tool_name,
        "type": tool_name,
        "status": "complete",
        "has_data": bool(isinstance(qdf, dict) and (qdf.get("uuid") or qdf.get("num_rows"))),
        "has_figure": bool(result.get("figure_url") or result.get("svg_url")),
        "figure_url": result.get("figure_url"),
        "message": result.get("message"),
        "num_rows": qdf.get("num_rows") if isinstance(qdf, dict) else None,
        "num_cols": qdf.get("num_cols") if isinstance(qdf, dict) else None,
        "headers": qdf.get("headers") if isinstance(qdf, dict) else None,
    }

    step_id = (qdf.get("uuid") if isinstance(qdf, dict) else None) or result.get("qdf_uuid") or "step"
    if step_id not in _rendered_step_ids:
        _render_inline_step(console, step_id, step, project_id, base_url, auth_headers, _ICONS)
        _rendered_step_ids.add(step_id)


_rendered_step_ids: set[str] = set()
"""Module-level set to prevent rendering the same step more than once per session."""


def _render_accumulated_steps(
    console: object,
    final_steps: dict[str, dict],
    project_id: str,
    client: object | None = None,
) -> None:
    """Render step results accumulated from the SSE stream. Each step renders only once."""
    base_url = ""
    auth_headers: dict[str, str] = {}
    if client:
        base_url, auth_headers = _resolve_internal_url(client)

    _ICONS = {
        "duckdb_query": "🔍", "draw_figure": "📊", "source": "📂",
        "add_source": "📂", "load": "📂", "python": "🐍", "coder": "🐍",
    }

    rendered = False
    for sid, sdata in final_steps.items():
        if sid in _rendered_step_ids:
            continue
        status = sdata.get("status", "")
        if status not in ("complete", "success"):
            continue
        step = _merge_step_data(sdata, {})
        if not step.get("name"):
            continue
        _render_inline_step(console, sid, step, project_id, base_url, auth_headers, _ICONS)
        _rendered_step_ids.add(sid)
        rendered = True

    if rendered:
        console.print()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# querri chat cancel — cancel active chat stream on the current project
# ---------------------------------------------------------------------------


@project_chat_app.command("cancel")
def chat_cancel(ctx: typer.Context) -> None:
    """Cancel the active chat stream on the current project.

    Sends a cancel signal to the server to stop any running execution.

    Example:
        querri project chat cancel
    """
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)
    project_id = resolve_project_id(ctx)
    client = get_client(ctx)

    # Find the active chat
    profile = _get_profile(ctx)
    chat_id = (profile.active_chat_id if profile else None) or None
    if not chat_id:
        existing = _fetch_project_chat(client, project_id)
        if existing:
            chat_id = existing.get("uuid") or existing.get("id")

    if not chat_id:
        print_error("No active chat to cancel.")
        raise typer.Exit(code=1)

    try:
        result = client.projects.chats.cancel(project_id, chat_id)
        if is_json:
            print_json({"cancelled": result.cancelled, "chat_id": chat_id})
        else:
            print_success(f"Cancelled chat {chat_id}")
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json))


# ---------------------------------------------------------------------------
# querri chat show — renders from message parts[] with inline step results
# ---------------------------------------------------------------------------


@project_chat_app.command("show")
def chat_show(
    ctx: typer.Context,
    top: int | None = typer.Option(None, "--top", help="Show only the first N messages."),
    bottom: int | None = typer.Option(None, "--bottom", help="Show only the last N messages."),
) -> None:
    """Show the conversation with inline step results (tables, charts).

    Loads the project's chat and renders each message's parts inline —
    text, reasoning, and tool results with data previews and ASCII art
    charts. Use --top or --bottom to slice.

    Examples:
        querri project chat show
        querri project chat show --bottom 2
    """
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)
    project_id = resolve_project_id(ctx)
    client = get_client(ctx)

    # Fetch full project (stepStore) and chat (messages with parts[])
    from querri.cli.projects import _get_full_project
    full_project = _get_full_project(client, project_id)
    if full_project is None:
        print_error("Could not load project data.")
        raise typer.Exit(code=1)

    chat_data = _fetch_project_chat(client, project_id)
    if not chat_data:
        print_error("No conversation history. Send a message with: querri project chat -m \"hello\"")
        raise typer.Exit(code=EXIT_SUCCESS)

    messages = chat_data.get("messages", [])

    if is_json:
        print_json(chat_data)
        return

    total = len(messages)
    if top is not None:
        messages = messages[:top]
    elif bottom is not None:
        messages = messages[-bottom:]

    step_store = _build_step_store(full_project)
    base_url, auth_headers = _resolve_internal_url(client)

    _render_messages_with_parts(messages, step_store, project_id, base_url, auth_headers, total=total)


# ---------------------------------------------------------------------------
# Helpers for chat show
# ---------------------------------------------------------------------------


def _fetch_project_chat(client: object, project_id: str) -> dict | None:
    """Fetch the project's chat via ``GET /api/projects/{pid}/chat``."""
    try:
        import httpx as _httpx
        base_url, auth_headers = _resolve_internal_url(client)
        resp = _httpx.get(
            f"{base_url}/api/projects/{project_id}/chat",
            headers=auth_headers,
            follow_redirects=True,
            timeout=30.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0]
            elif isinstance(data, dict):
                return data
    except Exception as exc:
        logger.debug("Failed to fetch project chat: %s", exc)
    return None


def _resolve_internal_url(client: object) -> tuple[str, dict[str, str]]:
    """Extract internal API base URL and auth headers from the SDK client.

    If the client's token came from the token store, refresh it if needed
    so that post-stream operations (image downloads) use a valid token.
    """
    try:
        http = client._http  # type: ignore[attr-defined]
        base_url = str(http._client.base_url).replace("/api/v1", "").rstrip("/")
        auth_headers = {k: v for k, v in http._client.headers.items() if k.lower() == "authorization"}

        # Try to refresh token if it may have expired during a long stream
        try:
            from querri._auth import TokenStore, needs_refresh, refresh_tokens
            store = TokenStore.load()
            profile = store.profiles.get("default")
            if profile and profile.access_token and needs_refresh(profile):
                profile = refresh_tokens(profile, base_url)
                store.save_profile("default", profile)
                auth_headers["authorization"] = f"Bearer {profile.access_token}"
        except Exception as exc:
            logger.debug("Token refresh failed (best effort): %s", exc)

        return base_url, auth_headers
    except Exception as exc:
        logger.debug("Failed to resolve internal URL: %s", exc)
        return "", {}


def _build_step_store(project: object) -> dict[str, dict]:
    """Build a step UUID -> step data lookup from the project's steps list."""
    steps = getattr(project, "steps", None) or []
    store: dict[str, dict] = {}
    for s in steps:
        store[s.id] = {
            "name": s.name, "type": s.type, "status": s.status,
            "has_data": s.has_data, "has_figure": s.has_figure,
            "figure_url": getattr(s, "figure_url", None),
            "message": getattr(s, "message", None),
            "num_rows": getattr(s, "num_rows", None),
            "num_cols": getattr(s, "num_cols", None),
            "headers": getattr(s, "headers", None),
        }
    return store


def _fetch_step_data_preview(
    step_id: str, project_id: str, base_url: str, auth_headers: dict[str, str], limit: int = 5,
) -> list[dict] | None:
    """Fetch the first few rows of step data from the internal API."""
    try:
        import httpx as _httpx
        resp = _httpx.get(
            f"{base_url}/api/projects/{project_id}/steps/{step_id}/data",
            params={"page": 1, "page_size": limit},
            headers=auth_headers, follow_redirects=True, timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json().get("data", [])
    except Exception as exc:
        logger.debug("Failed to fetch step data preview for %s: %s", step_id, exc)
    return None


def _render_messages_with_parts(
    messages: list[dict],
    step_store: dict[str, dict],
    project_id: str,
    base_url: str,
    auth_headers: dict[str, str],
    *,
    total: int | None = None,
) -> None:
    """Render messages with inline step results from parts[]."""
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text

    from querri.cli._output import QUERRI_ORANGE

    console = Console()
    shown = len(messages)
    total_n = total if total is not None else shown
    count = f"{shown} of {total_n} messages" if shown != total_n else f"{total_n} messages"
    console.print(Text.from_markup(f"[bold {QUERRI_ORANGE}]Conversation[/bold {QUERRI_ORANGE}]  [dim]{count}[/dim]\n"))

    _ICONS = {
        "duckdb_query": "🔍", "draw_figure": "📊", "source": "📂",
        "add_source": "📂", "load": "📂", "python": "🐍", "coder": "🐍",
    }

    for msg in messages:
        role = msg.get("role", "")
        parts = msg.get("parts") or []

        if role == "user":
            user_text = ""
            for p in parts:
                if p.get("type") == "text":
                    user_text += p.get("text", "")
            if not user_text:
                user_text = msg.get("content", "")
            if user_text:
                console.print(Panel(
                    Text(user_text),
                    title="[bold]You[/bold]", title_align="right",
                    border_style=QUERRI_ORANGE, padding=(0, 1),
                    width=min(console.width - 10, 80),
                ), justify="right")

        elif role == "assistant":
            # Fallback: if parts[] is empty, reconstruct from stream_chunks
            if not parts:
                chunks = msg.get("stream_chunks") or []
                if chunks:
                    parts = _parse_stream_chunks(chunks, step_store)
                elif msg.get("content"):
                    # Plain content fallback (no parts, no chunks)
                    parts = [{"type": "text", "text": msg["content"]}]

            for part in parts:
                ptype = part.get("type", "")

                if ptype == "text":
                    text = part.get("text", "").strip()
                    if text:
                        console.print(Panel(
                            Markdown(text),
                            title="[bold dim]Querri[/bold dim]",
                            title_align="left", border_style="dim",
                            padding=(0, 1),
                        ))

                elif ptype == "reasoning":
                    reasoning = part.get("reasoning", "").strip()
                    if reasoning:
                        console.print(Panel(
                            Text(reasoning, style="dim italic"),
                            title="[dim]Reasoning[/dim]", title_align="left",
                            border_style="dim", padding=(0, 1),
                        ))

                elif ptype.startswith("tool-") and ptype != "tool-usage":
                    output = part.get("output", {}) or {}
                    raw_steps = output.get("steps", {})

                    # steps can be a dict {uuid: {step_data}} or a list
                    step_items: list[tuple[str, dict]] = []
                    if isinstance(raw_steps, dict):
                        for sid, sdata in raw_steps.items():
                            if isinstance(sdata, dict):
                                step_items.append((sid, sdata))
                    elif isinstance(raw_steps, list):
                        for sref in raw_steps:
                            if isinstance(sref, str):
                                step_items.append((sref, step_store.get(sref, {})))
                            elif isinstance(sref, dict):
                                sid = sref.get("uuid", "")
                                if sid:
                                    step_items.append((sid, sref))

                    for sid, embedded in step_items:
                        if not sid:
                            continue
                        # Merge embedded step data with stepStore (embedded takes priority)
                        step = _merge_step_data(embedded, step_store.get(sid, {}))
                        if not step:
                            continue
                        _render_inline_step(console, sid, step, project_id, base_url, auth_headers, _ICONS)

    console.print()


def _parse_stream_chunks(chunks: list[str], step_store: dict[str, dict]) -> list[dict]:
    """Reconstruct ``parts[]`` from raw SSE ``stream_chunks``.

    The server stores newer messages as raw SSE lines (e.g.
    ``data: {"type":"text-delta","delta":"..."}``).  The browser parses
    these client-side; the CLI needs to do the same.
    """
    import json

    text_buf: list[str] = []
    reasoning_buf: list[str] = []
    in_reasoning = False
    parts: list[dict] = []
    # Track the last tool-output-available per toolCallId (final has full data)
    tool_outputs: dict[str, dict] = {}

    for raw in chunks:
        line = raw.strip()
        if not line or line.startswith(":"):
            continue
        # Extract data payload
        if line.startswith("data: "):
            payload = line[6:]
        elif len(line) >= 2 and line[1] == ":":
            payload = line[2:]
        else:
            continue

        try:
            obj = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue

        etype = obj.get("type", "")

        if etype == "text-delta":
            delta = obj.get("textDelta") or obj.get("delta", "")
            if delta:
                # Flush reasoning if we were in a reasoning block
                if in_reasoning and reasoning_buf:
                    parts.append({"type": "reasoning", "reasoning": "".join(reasoning_buf)})
                    reasoning_buf.clear()
                    in_reasoning = False
                text_buf.append(delta)

        elif etype == "reasoning-start":
            # Flush any text before reasoning
            if text_buf:
                parts.append({"type": "text", "text": "".join(text_buf)})
                text_buf.clear()
            in_reasoning = True

        elif etype == "reasoning-delta":
            delta = obj.get("textDelta") or obj.get("delta", "")
            if delta:
                reasoning_buf.append(delta)

        elif etype == "reasoning-end":
            if reasoning_buf:
                parts.append({"type": "reasoning", "reasoning": "".join(reasoning_buf)})
                reasoning_buf.clear()
            in_reasoning = False

        elif etype == "tool-output-available":
            output = obj.get("output", {})
            tcid = obj.get("toolCallId", "")
            tool_name = obj.get("toolName", "")
            if isinstance(output, dict) and tcid:
                tool_outputs[tcid] = output

        elif etype == "tool-input-available":
            tool_name = obj.get("toolName", "")

    # Flush remaining buffers
    if reasoning_buf:
        parts.append({"type": "reasoning", "reasoning": "".join(reasoning_buf)})
    if text_buf:
        parts.append({"type": "text", "text": "".join(text_buf)})

    # Add tool parts from accumulated outputs (final per toolCallId)
    for tcid, output in tool_outputs.items():
        if output.get("status") in ("success", "running"):
            steps = output.get("steps", {})
            if isinstance(steps, dict) and steps:
                parts.append({
                    "type": "tool-plan",
                    "output": output,
                })

    return parts


def _merge_step_data(embedded: dict, from_store: dict) -> dict:
    """Merge embedded step data (from chat parts) with stepStore data.

    The embedded data from ``output.steps`` contains the full step object
    including a nested ``result`` dict.  The stepStore-derived data has
    already been flattened by ``_build_step_store``.  Prefer embedded data.
    """
    result = embedded.get("result") or {}
    has_data = bool(result.get("qdf") or result.get("qdf_uuid"))
    has_figure = bool(result.get("figure_url") or result.get("svg_url"))
    qdf = result.get("qdf") or {}

    merged: dict = {
        "name": embedded.get("name") or from_store.get("name", ""),
        "type": embedded.get("tool") or embedded.get("type") or from_store.get("type", ""),
        "status": embedded.get("status") or from_store.get("status", ""),
        "has_data": has_data or from_store.get("has_data", False),
        "has_figure": has_figure or from_store.get("has_figure", False),
        "figure_url": result.get("figure_url") or from_store.get("figure_url"),
        "message": result.get("message") or from_store.get("message"),
        "num_rows": qdf.get("num_rows") or from_store.get("num_rows"),
        "num_cols": qdf.get("num_cols") or from_store.get("num_cols"),
        "headers": qdf.get("headers") or from_store.get("headers"),
    }
    return merged


def _render_inline_step(
    console: object,
    step_id: str,
    step: dict,
    project_id: str,
    base_url: str,
    auth_headers: dict[str, str],
    icons: dict[str, str],
) -> None:
    """Render a single step result inline in the conversation."""
    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    from querri.cli._image import render_image_rich
    from querri.cli._output import QUERRI_ORANGE

    name = step.get("name", step_id[:12])
    stype = step.get("type", "")
    icon = icons.get(stype, "⚙")
    msg = _strip_html(step.get("message") or "")
    fig_url = step.get("figure_url")
    has_data = step.get("has_data", False)

    content_parts: list[object] = []

    if msg:
        content_parts.append(Text(msg, style="italic"))

    # Table preview
    if has_data:
        num_rows = step.get("num_rows")
        num_cols = step.get("num_cols")
        if num_rows is not None:
            content_parts.append(Text(f"{num_rows} rows × {num_cols} columns", style="dim"))
        rows = _fetch_step_data_preview(step_id, project_id, base_url, auth_headers)
        if rows and isinstance(rows, list) and rows and isinstance(rows[0], dict):
            all_cols = list(rows[0].keys())
            cols = all_cols[:6]
            table = Table(show_header=True, header_style="bold", border_style="dim", padding=(0, 1), expand=False)
            for col in cols:
                table.add_column(col)
            if len(all_cols) > 6:
                table.add_column("…", style="dim")
            for row in rows[:5]:
                vals = [str(row.get(c, ""))[:20] for c in cols]
                if len(all_cols) > 6:
                    vals.append("…")
                table.add_row(*vals)
            if num_rows and num_rows > 5:
                filler = ["…"] * len(cols) + ([""] if len(all_cols) > 6 else [])
                table.add_row(*filler, style="dim")
            content_parts.append(table)
        content_parts.append(Text.from_markup(f"[dim]querri step data {step_id}[/dim]"))

    # Chart
    if fig_url:
        resolved = fig_url if fig_url.startswith("http") else f"{base_url}/api/files/stream/{fig_url.lstrip('/')}"
        img_width = min(console.width - 6, 70)
        content_parts.append(render_image_rich(resolved, max_width=img_width, max_height=24, headers=auth_headers))

    content = Group(*content_parts) if content_parts else Text("[dim]Step completed[/dim]")
    console.print(Panel(
        content,
        title=f"[bold {QUERRI_ORANGE}]{icon} {name}[/bold {QUERRI_ORANGE}]",
        title_align="left", border_style="dim", padding=(0, 1),
    ))
