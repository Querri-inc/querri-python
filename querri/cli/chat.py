"""querri chat — top-level conversational command.

Sends a prompt to the active project's chat, auto-creating the chat
if one doesn't exist yet. Designed for quick, stateful interaction:

    querri project select "Sales Analysis"
    querri chat -p "what trends do you see?"
    querri chat -p "break it down by region"
"""

from __future__ import annotations

import os
import re
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

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Strip HTML tags from a string."""
    return _HTML_TAG_RE.sub("", text).strip()


chat_app = typer.Typer(
    name="chat",
    help="Send a prompt or manage chats on the active project.",
    invoke_without_command=True,
    rich_markup_mode="rich",
)


@chat_app.callback(invoke_without_command=True)
def chat_command(
    ctx: typer.Context,
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Message to send."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model selection."),
    new: bool = typer.Option(False, "--new", help="Force a new chat session."),
    reasoning: bool = typer.Option(False, "--reasoning", "-r", help="Show reasoning traces."),
) -> None:
    """Send a prompt to the active project's chat.

    Auto-creates a chat if none is active. Use --new to start a fresh
    conversation.

    Examples:
        querri chat -p "summarize the data"
        querri chat --prompt "show me Q4 revenue" --model gpt-4o
        querri chat -p "start over" --new
    """
    if ctx.invoked_subcommand is not None:
        return
    if prompt is None:
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


# ---------------------------------------------------------------------------
# Streaming renderers (shared with chats.py)
# ---------------------------------------------------------------------------


def _stream_plain(stream: object, *, show_reasoning: bool = False) -> None:
    from querri._streaming import ChatStream
    assert isinstance(stream, ChatStream)

    # Debug: dump raw lines first to diagnose parsing
    if os.environ.get("QUERRI_DEBUG_STREAM"):
        for line in stream._response.iter_lines():
            print(f"[RAW] {line!r}", file=sys.stderr)
        stream._response.close()
        return

    for event in stream.events():
        if event.event_type == "reasoning-start":
            if show_reasoning:
                print("\n--- Reasoning ---", file=sys.stderr)
        elif event.event_type == "reasoning-delta" and event.reasoning_text:
            if show_reasoning:
                print(event.reasoning_text, end="", flush=True, file=sys.stderr)
        elif event.event_type == "reasoning-end":
            if show_reasoning:
                print("\n-----------------\n", file=sys.stderr)
        elif event.event_type == "text-delta" and event.text:
            print(event.text, end="", flush=True)
        elif event.event_type == "tool-output-available":
            name = event.tool_name or "unknown"
            print(f"\n[Step: {name}]", file=sys.stderr)
            if event.tool_data and isinstance(event.tool_data, dict):
                _print_tool_preview_plain(event.tool_data)
        elif event.event_type == "file":
            url = event.file_url or ""
            media = event.media_type or ""
            if "image" in media:
                from querri.cli._image import download_image
                path = download_image(url)
                if path:
                    print(f"\n  Chart saved: {path}", file=sys.stderr)
                print(f"  Open chart: {url}", file=sys.stderr)
            else:
                print(f"\n  Open file: {url}", file=sys.stderr)
        elif event.event_type == "terminate":
            reason = event.terminate_reason or "unknown"
            msg = event.terminate_message or ""
            print(f"\nStream closed: {reason}. {msg}", file=sys.stderr)
        elif event.event_type == "error":
            print(f"\nError: {event.error}", file=sys.stderr)
    print()


def _print_tool_preview_plain(data: dict) -> None:
    """Print a compact table preview for tool output in plain mode."""
    rows = data.get("rows") or data.get("data") or data.get("results")
    title = data.get("title") or data.get("name") or ""
    if not isinstance(rows, list) or not rows:
        return
    cols = list(rows[0].keys()) if isinstance(rows[0], dict) else []
    n_rows = len(rows)
    n_cols = len(cols)
    if title:
        print(f"  {title}", file=sys.stderr)
    print(f"  {n_cols} columns, {n_rows} rows", file=sys.stderr)
    preview = rows[:3]
    if cols:
        header = " | ".join(f"{c:>12}" for c in cols[:5])
        print(f"  {header}", file=sys.stderr)
        for row in preview:
            vals = [str(row.get(c, ""))[:12] for c in cols[:5]]
            print(f"  {' | '.join(f'{v:>12}' for v in vals)}", file=sys.stderr)
        if n_rows > 3:
            print(f"  ... and {n_rows - 3} more rows", file=sys.stderr)


def _stream_rich(stream: object, *, show_reasoning: bool = False) -> None:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    from querri._streaming import ChatStream
    assert isinstance(stream, ChatStream)

    console = Console()
    reasoning_text = ""
    response_text = ""
    tool_panels: list[Panel | Table] = []
    file_links: list[str] = []

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
        for panel in tool_panels:
            parts.append(panel)
        for link in file_links:
            parts.append(link)
        if response_text:
            parts.append(Markdown(response_text))
        return Group(*parts) if parts else Group(Text(""))

    with Live(Text(""), console=console, refresh_per_second=10) as live:
        for event in stream.events():
            if event.event_type == "reasoning-start":
                pass
            elif event.event_type == "reasoning-delta" and event.reasoning_text:
                reasoning_text += event.reasoning_text
                live.update(_build_display())
            elif event.event_type == "reasoning-end":
                live.update(_build_display())
            elif event.event_type == "text-delta" and event.text:
                response_text += event.text
                live.update(_build_display())
            elif event.event_type == "tool-output-available":
                panel = _build_tool_panel(event.tool_name, event.tool_data)
                if panel is not None:
                    tool_panels.append(panel)
                    live.update(_build_display())
            elif event.event_type == "file":
                url = event.file_url or ""
                media = event.media_type or ""
                if "image" in media:
                    from querri.cli._image import render_image_rich
                    img_width = min(console.width - 4, 70)
                    renderable = render_image_rich(url, caption=event.raw_data or "", max_width=img_width, max_height=24)
                    file_links.append(renderable)
                else:
                    file_links.append(Text.from_markup(
                        f"  [link={url}][bold #f15a24]📎 Open file[/bold #f15a24][/link]  [dim]{url}[/dim]"
                    ))
                live.update(_build_display())
            elif event.event_type == "terminate":
                reason = event.terminate_reason or "unknown"
                msg = event.terminate_message or "Start a new chat to continue."
                console.print(f"\n[#f15a24]Stream closed: {reason}. {msg}[/#f15a24]")
            elif event.event_type == "error":
                console.print(f"\n[red]Error: {event.error}[/red]")


def _build_tool_panel(tool_name: str | None, tool_data: object | None) -> object | None:
    """Build a Rich Panel with a compact table preview for a tool result."""
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    name = tool_name or "Result"
    if not isinstance(tool_data, dict):
        return Panel(Text("Step completed", style="dim"), title=f"[bold #f15a24]{name}[/bold #f15a24]", title_align="left", border_style="dim", padding=(0, 1))

    rows = tool_data.get("rows") or tool_data.get("data") or tool_data.get("results")
    title = tool_data.get("title") or tool_data.get("name") or name
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        summary = tool_data.get("summary") or tool_data.get("message") or ""
        return Panel(Text(str(summary)) if summary else Text("Step completed", style="dim"), title=f"[bold #f15a24]{title}[/bold #f15a24]", title_align="left", border_style="dim", padding=(0, 1))

    cols = list(rows[0].keys())
    show_cols = cols[:6]
    table = Table(title=f"[bold #f15a24]{title}[/bold #f15a24]", caption=f"{len(rows)} rows × {len(cols)} columns", caption_style="dim", show_header=True, header_style="bold", border_style="dim", padding=(0, 1), expand=False)
    for col in show_cols:
        table.add_column(col)
    if len(cols) > 6:
        table.add_column("…", style="dim")
    for row in rows[:5]:
        vals = [str(row.get(c, ""))[:20] for c in show_cols]
        if len(cols) > 6:
            vals.append("…")
        table.add_row(*vals)
    if len(rows) > 5:
        table.add_row(*["…"] * len(show_cols) + ([""] if len(cols) > 6 else []), style="dim")
    return table


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
# querri chat show — renders from message parts[] with inline step results
# ---------------------------------------------------------------------------


@chat_app.command("show")
def chat_show(
    ctx: typer.Context,
    top: Optional[int] = typer.Option(None, "--top", help="Show only the first N messages."),
    bottom: Optional[int] = typer.Option(None, "--bottom", help="Show only the last N messages."),
) -> None:
    """Show the conversation with inline step results (tables, charts).

    Loads the project's chat and renders each message's parts inline —
    text, reasoning, and tool results with data previews and ASCII art
    charts. Use --top or --bottom to slice.

    Examples:
        querri chat show
        querri chat show --bottom 2
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
        print_error("No conversation history. Send a message with: querri chat -p \"hello\"")
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
    except Exception:
        pass
    return None


def _resolve_internal_url(client: object) -> tuple[str, dict[str, str]]:
    """Extract internal API base URL and auth headers from the SDK client."""
    try:
        http = client._http  # type: ignore[attr-defined]
        base_url = str(http._client.base_url).replace("/api/v1", "").rstrip("/")
        auth_headers = {k: v for k, v in http._client.headers.items() if k.lower() == "authorization"}
        return base_url, auth_headers
    except Exception:
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
    except Exception:
        pass
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
    from rich.console import Console, Group
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    from querri.cli._image import render_image_rich
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
                    border_style="blue", padding=(0, 1),
                    width=min(console.width - 10, 80),
                ), justify="right")

        elif role == "assistant":
            for part in parts:
                ptype = part.get("type", "")

                if ptype == "text":
                    text = part.get("text", "").strip()
                    if text:
                        console.print(Panel(
                            Markdown(text),
                            title=f"[bold {QUERRI_ORANGE}]Querri[/bold {QUERRI_ORANGE}]",
                            title_align="left", border_style=QUERRI_ORANGE,
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
