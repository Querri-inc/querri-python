"""querri library — interact with the Data Library (Phase 1)."""

from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import typer

from querri.cli._context import _resolve_workspace, get_client
from querri.cli._output import (
    handle_api_error,
    print_detail,
    print_error,
    print_id,
    print_json,
    print_success,
    print_table,
)
from querri.resources.library import _ChatDrain, choice_label
from querri.types.library import ChatResponse, NodeListItem

library_app = typer.Typer(
    name="library",
    help=(
        "Data Library — graph + semantic search backing the librarian agent.\n\n"
        "Phase 1 surface: create libraries / collections / questions, get a node "
        "by id, run vector-ANN search, seed demo fixtures, check health."
    ),
    no_args_is_help=True,
)


# ── Active library state ─────────────────────────────────────────────────
#
# Default library_id for subsequent commands. Resolution order:
#   1. --library-id flag (when present on the command)
#   2. QUERRI_LIBRARY_ID env var
#   3. ~/.querri/library_context.json, under this host + organization
#      (set via `querri library use <id>`)
#   4. error with guidance
#
# A library id and the chats in it belong to ONE organization, so the context
# file is keyed by host + org. It used to be one global slot: after
# `querri auth switch-org` every library command quietly aimed at the previous
# org's library. A pre-2.3 file is kept under "legacy" and offered in the
# no-library error, never adopted silently — we cannot know which org it was for.


_LIBRARY_CONTEXT_FILE = Path.home() / ".querri" / "library_context.json"


def _short(text: str, n: int = 60) -> str:
    return (text[:n] + "…") if len(text) > n else text


def _scope_key(client: Any) -> str:
    """``host|org_id`` for the client's credentials."""
    cfg = getattr(client, "_config", None)
    host = getattr(cfg, "host", "")
    org = getattr(cfg, "org_id", "")
    host = host.rstrip("/") if isinstance(host, str) else ""
    org = org if isinstance(org, str) else ""
    return f"{host}|{org}"


def _load_context_file() -> dict[str, Any]:
    empty: dict[str, Any] = {"scopes": {}}
    if not _LIBRARY_CONTEXT_FILE.exists():
        return empty
    try:
        data = json.loads(_LIBRARY_CONTEXT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    if not isinstance(data, dict):
        return empty
    if "scopes" not in data:
        # Pre-2.3 global file: keep it aside, adopt nothing.
        return {"scopes": {}, "legacy": data} if data else empty
    if not isinstance(data["scopes"], dict):
        data["scopes"] = {}
    return data


def _read_library_context(client: Any) -> dict[str, str]:
    scoped = _load_context_file()["scopes"].get(_scope_key(client), {})
    return dict(scoped) if isinstance(scoped, dict) else {}


def _write_library_context(client: Any, data: dict[str, str]) -> None:
    file = _load_context_file()
    file["scopes"][_scope_key(client)] = data
    _LIBRARY_CONTEXT_FILE.parent.mkdir(mode=0o700, exist_ok=True)
    _LIBRARY_CONTEXT_FILE.write_text(json.dumps(file, indent=2), encoding="utf-8")
    with contextlib.suppress(OSError):
        os.chmod(_LIBRARY_CONTEXT_FILE, 0o600)


def _resolve_library_id(explicit: str | None, client: Any) -> str:
    if explicit:
        return explicit
    env = os.environ.get("QUERRI_LIBRARY_ID")
    if env:
        return env
    ctx_data = _read_library_context(client)
    if ctx_data.get("library_id"):
        return ctx_data["library_id"]
    message = (
        "No active library for this organization. Pass --library-id, set "
        "QUERRI_LIBRARY_ID, or run 'querri library use <library-id>' "
        "('querri library list-libraries' shows them)."
    )
    legacy = _load_context_file().get("legacy") or {}
    old_id = legacy.get("library_id") if isinstance(legacy, dict) else None
    if old_id:
        message += (
            f"\n  The active library used to be global: {old_id}. If it belongs "
            f"to this organization: querri library use {old_id}"
        )
    print_error(message)
    raise typer.Exit(code=1)


def _workspace(client: Any) -> str | None:
    """The workspace this invocation stands in (``--workspace`` or the stored
    one), sent as the body's ``workspace_id`` on every Library create so it is
    honoured for API keys too, not only through the header."""
    ws = getattr(client, "workspace_id", None)
    return ws if isinstance(ws, str) and ws else None


# ── Health ─────────────────────────────────────────────────────────────────


@library_app.command("health")
def health(ctx: typer.Context) -> None:
    """Tenant-scoped Data Library health probe."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.library.health()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
    else:
        print_detail(
            result.model_dump(),
            [
                ("status", "Status"),
                ("tenant_id", "Tenant"),
                ("library_graph_doc_count", "library_graph docs"),
                ("embedding_model", "Embedding model"),
            ],
        )


# ── Create ─────────────────────────────────────────────────────────────────


@library_app.command("create-library")
def create_library(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Display name for the library."),
    summary: str = typer.Option("", "--summary", "-s", help="Optional summary."),
) -> None:
    """Create a new Library node."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        lib = client.library.create_library(name=name, summary=summary)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(lib.model_dump())
    elif obj.get("quiet"):
        print_id(lib.id)
    else:
        print_success(f"Library created: {lib.id}")
        print_detail(
            lib.model_dump(),
            [("name", "Name"), ("node_kind", "Kind"), ("id", "ID")],
        )


@library_app.command("create-collection")
def create_collection(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Display name for the collection."),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Parent Library _id (defaults to active)."
    ),
    summary: str = typer.Option("", "--summary", "-s"),
    anchor: str = typer.Option(
        None,
        "--anchor",
        "-a",
        help=(
            "Anchor question text — creates AnchorQuestion + ANCHOR_OF edge "
            "in the same call."
        ),
    ),
) -> None:
    """Create a Collection inside a Library, optionally seeded with an anchor
    question."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        coll = client.library.create_collection(
            library_id=lib_id,
            name=name,
            summary=summary,
            anchor_question_text=anchor,
            workspace_id=_workspace(client),
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(coll)
        return
    if obj.get("quiet"):
        print_id(coll["id"])
        return

    print_success(f"Collection created: {coll['id']}")
    print_detail(
        coll,
        [("name", "Name"), ("library_id", "Library"), ("id", "ID")],
    )
    if "anchor_question" in coll:
        aq = coll["anchor_question"]
        print_success(f"  + anchor question linked: {aq['id']}")
        print_detail(aq, [("question_text", "Question"), ("id", "ID")])


@library_app.command("create-question")
def create_question(
    ctx: typer.Context,
    question_text: str = typer.Argument(..., help="The actual question text."),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Parent Library _id (defaults to active)."
    ),
    name: str = typer.Option(
        None,
        "--name",
        "-n",
        help="Display name (default: first 50 chars of the question).",
    ),
    refining: bool = typer.Option(
        False,
        "--refining",
        help="Create a RefiningQuestion (default: AnchorQuestion).",
    ),
) -> None:
    """Create an AnchorQuestion or RefiningQuestion."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    display_name = name or question_text[:50]
    try:
        if refining:
            q = client.library.create_refining_question(
                library_id=lib_id,
                name=display_name,
                question_text=question_text,
                workspace_id=_workspace(client),
            )
        else:
            q = client.library.create_anchor_question(
                library_id=lib_id,
                name=display_name,
                question_text=question_text,
                workspace_id=_workspace(client),
            )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(q.model_dump())
    elif obj.get("quiet"):
        print_id(q.id)
    else:
        kind_label = "Refining" if refining else "Anchor"
        print_success(f"{kind_label}Question created: {q.id}")
        payload = q.model_dump()
        payload["question_text"] = question_text
        print_detail(
            payload,
            [
                ("question_text", "Question"),
                ("library_id", "Library"),
                ("id", "ID"),
            ],
        )


# ── Read ────────────────────────────────────────────────────────────────────


@library_app.command("get")
def get_node(
    ctx: typer.Context,
    node_id: str = typer.Argument(..., help="Node _id."),
) -> None:
    """Fetch a node by _id."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        node = client.library.get_node(node_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(node.model_dump())
        return
    truncated = node.summary[:120] + ("..." if len(node.summary) > 120 else "")
    extra = node.extra or {}
    data: dict[str, Any] = {
        "id": node.id,
        "name": node.name,
        "node_kind": node.node_kind,
        "library_id": node.library_id,
        "workspace_id": extra.get("workspace_id") or "—",
        "summary": truncated,
    }
    fields = [
        ("id", "ID"),
        ("name", "Name"),
        ("node_kind", "Kind"),
        ("library_id", "Library"),
        ("workspace_id", "Workspace"),
        ("summary", "Summary"),
    ]
    build = extra.get("build")
    if isinstance(build, dict):
        data["build_status"] = build.get("status") or "—"
        rows = build.get("row_count")
        data["row_count"] = "—" if rows is None else rows
        fields += [("build_status", "Build status"), ("row_count", "Rows")]
    if "shared_to" in extra:
        data["shared_to"] = _format_shares(extra.get("shared_to"))
        fields.append(("shared_to", "Shared to"))
    print_detail(data, fields)


def _format_shares(shares: Any) -> str:
    """``[{workspace_id, relation}]`` → ``ws_a (viewer), ws_b (editor)``."""
    if not isinstance(shares, list) or not shares:
        return "not shared"
    return ", ".join(
        f"{s.get('workspace_id', '?')} ({s.get('relation', '?')})"
        if isinstance(s, dict) else str(s)
        for s in shares
    )


# ── Workspace ──────────────────────────────────────────────────────────────


@library_app.command("use")
def use_library(
    ctx: typer.Context,
    library_id: str = typer.Argument(..., help="Library _id to set as active."),
) -> None:
    """Set the active library for subsequent commands.

    Stored in ``~/.querri/library_context.json`` per host and organization, and
    used as the default --library-id when commands don't pass one explicitly.
    """
    client = get_client(ctx)
    ctx_data = _read_library_context(client)
    ctx_data["library_id"] = library_id
    _write_library_context(client, ctx_data)
    print_success(f"Active library set: {library_id}")


# ── Status + list ──────────────────────────────────────────────────────────


@library_app.command("status")
def status(
    ctx: typer.Context,
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library _id (defaults to active)."
    ),
) -> None:
    """Show per-kind node counts for a library."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        result = client.library.status(library_id=lib_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    print_detail(
        {"library_id": result.library_id, "tenant_id": result.tenant_id,
         "total_nodes": result.total_nodes},
        [("library_id", "Library"), ("tenant_id", "Tenant"),
         ("total_nodes", "Total nodes")],
    )
    print_table(
        [{"kind": k, "count": v}
         for k, v in sorted(result.counts_by_kind.items())],
        [("kind", "Kind"), ("count", "Count")],
    )


@library_app.command("list")
def list_nodes(
    ctx: typer.Context,
    node_kind: str = typer.Argument(
        ...,
        help="Node kind to list (e.g. Collection, AnchorQuestion, SourceStub).",
    ),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library _id (defaults to active)."
    ),
    limit: int = typer.Option(100, "--limit", "-n", min=1, max=1000),
) -> None:
    """List nodes of a given kind within a library."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        result = client.library.list_nodes(
            library_id=lib_id, node_kind=node_kind, limit=limit
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    if not result.results:
        print_error(f"No {node_kind} nodes in library {lib_id}.")
        return

    print_table(
        [
            {
                "name": item.name,
                "summary": _short(item.summary),
                "id": item.id,
            }
            for item in result.results
        ],
        [("name", "Name"), ("summary", "Summary"), ("id", "ID")],
    )


@library_app.command("list-libraries")
def list_libraries(
    ctx: typer.Context,
    limit: int = typer.Option(100, "--limit", "-n", min=1, max=1000),
) -> None:
    """Enumerate every Library node in the active tenant."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.library.list_libraries(limit=limit)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    if not result.results:
        print_error(
            "No Library nodes in tenant. "
            "Run `querri library create-library <name>` first."
        )
        return

    print_table(
        [
            {
                "name": item.name,
                "summary": _short(item.summary),
                "id": item.id,
            }
            for item in result.results
        ],
        [("name", "Name"), ("summary", "Summary"), ("id", "ID")],
    )


@library_app.command("list-collections")
def list_collections(
    ctx: typer.Context,
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library _id (defaults to active)."
    ),
    limit: int = typer.Option(100, "--limit", "-n", min=1, max=1000),
) -> None:
    """Enumerate every Collection in the active (or given) Library."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        result = client.library.list_collections(library_id=lib_id, limit=limit)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    if not result.results:
        print_error(f"No Collections in library {lib_id}.")
        return

    print_table(
        [
            {
                "name": item.name,
                "summary": _short(item.summary),
                "id": item.id,
            }
            for item in result.results
        ],
        [("name", "Name"), ("summary", "Summary"), ("id", "ID")],
    )


# ── Refining + edges ───────────────────────────────────────────────────────


@library_app.command("add-refining")
def add_refining(
    ctx: typer.Context,
    anchor_id: str = typer.Argument(..., help="AnchorQuestion _id to refine."),
    question_text: str = typer.Argument(..., help="Refining question text."),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library _id (defaults to active)."
    ),
    name: str = typer.Option(
        None, "--name", help="Display name (default: first 50 chars)."
    ),
) -> None:
    """Create a RefiningQuestion and link it (REFINES) to an AnchorQuestion."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        q = client.library.create_refining_question(
            library_id=lib_id,
            name=name or question_text[:50],
            question_text=question_text,
            anchor_question_id=anchor_id,
            workspace_id=_workspace(client),
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(q.model_dump())
        return
    if obj.get("quiet"):
        print_id(q.id)
        return
    print_success(f"RefiningQuestion linked to {anchor_id}: {q.id}")
    payload = q.model_dump()
    payload["question_text"] = question_text
    print_detail(
        payload,
        [("question_text", "Question"), ("id", "ID")],
    )


@library_app.command("link")
def link_nodes(
    ctx: typer.Context,
    a_id: str = typer.Argument(..., help="First node _id."),
    b_id: str = typer.Argument(..., help="Second node _id."),
    relation: str = typer.Argument(
        ...,
        help="Edge relation (e.g. contains, anchor_of, refines, uses_source).",
    ),
    weight: float = typer.Option(1.0, "--weight", min=0.0, max=1.0),
    confidence: float = typer.Option(1.0, "--confidence", min=0.0, max=1.0),
) -> None:
    """Create a bidirectional edge between two nodes. Idempotent."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.library.link(
            a_id=a_id, b_id=b_id, relation=relation,
            weight=weight, confidence=confidence,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return
    print_success(f"Linked: {a_id} ←{result.relation}→ {b_id}")


# ── Chat (LibrarianAgent — Phase 2) ────────────────────────────────────────


@library_app.command("chat")
def chat_cmd(
    ctx: typer.Context,
    message: str = typer.Argument(..., help="Message to send to the Librarian."),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library (defaults to active)."
    ),
    chat_id: str = typer.Option(
        None,
        "--chat-id",
        "-c",
        help="Continue a specific chat. Defaults to the last chat for this library.",
    ),
    new: bool = typer.Option(
        False,
        "--new",
        "-n",
        help="Start a fresh chat, ignoring the active chat_id.",
    ),
    show_tools: bool = typer.Option(
        False,
        "--show-tools",
        help="Show the agent's tool-call trace alongside the assistant message.",
    ),
    answer: str = typer.Option(
        None,
        "--answer",
        help=(
            "Answer the choice card the agent ends on: an option number or its "
            "label. Sent as the next message in the same chat. For scripts; in "
            "a terminal you are prompted instead."
        ),
    ),
) -> None:
    """Chat with the Librarian agent — search, record facts, commission views.

    When the agent asks you to choose (a choice card, e.g. "Build this view?"),
    the question and numbered options are printed. In a terminal you are
    prompted; otherwise pass ``--answer <number|label>`` (or re-run with the
    label as the message). Approving a plan needs the option's exact label —
    a free-text "yes" is read as a revision, not an approval. ``--json`` emits
    the card as ``choices``; with ``--answer`` it emits ``{"turns": [...]}``.
    """
    obj = ctx.ensure_object(dict)
    is_json = bool(obj.get("json"))
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)

    ctx_data = _read_library_context(client)
    resolved_chat: str | None = chat_id
    if not resolved_chat and not new:
        last = ctx_data.get(f"chat_id::{lib_id}")
        if last:
            resolved_chat = str(last)

    turns: list[ChatResponse] = []
    pending_answer: str | None = answer
    next_message = message
    while True:
        result = _chat_turn(
            client, lib_id, next_message, resolved_chat,
            show_tools=show_tools and not is_json, is_json=is_json,
        )
        turns.append(result)
        resolved_chat = result.chat_id or resolved_chat
        if resolved_chat:
            # Persist so the next invocation (or an --answer) continues it.
            ctx_data[f"chat_id::{lib_id}"] = resolved_chat
            _write_library_context(client, ctx_data)
        if not is_json:
            _print_chat_turn(result, show_tools=show_tools)

        card = result.choices
        if not card:
            break
        if not is_json:
            _print_choice_card(card)
        if pending_answer is not None:
            label = _answer_label(card, pending_answer, is_json=is_json)
            pending_answer = None
        elif not is_json and _is_interactive():
            picked = _prompt_choice(card)
            if picked is None:
                break
            label = picked
        else:
            if not is_json:
                print(
                    "\nAnswer with: querri library chat --answer <number|label> "
                    "\"<same message>\"  (or send the label as the message)",
                    file=sys.stderr,
                )
            break
        if not is_json:
            print(f"\nyou › {label}", flush=True)
        next_message = label

    if is_json:
        if len(turns) == 1:
            print_json(turns[0].model_dump())
        else:
            print_json({"turns": [t.model_dump() for t in turns]})


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _chat_turn(
    client: Any,
    lib_id: str,
    message: str,
    chat_id: str | None,
    *,
    show_tools: bool,
    is_json: bool,
) -> ChatResponse:
    """Stream one Librarian turn, printing the tool trace if asked."""
    drain = _ChatDrain()
    try:
        for ev in client.library.chat_stream(
            library_id=lib_id, message=message, chat_id=chat_id
        ):
            drain.feed(ev)
            if show_tools:
                _print_tool_event(ev, drain)
    except typer.Exit:
        raise
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json)) from None
    return drain.response(library_id=lib_id, chat_id=chat_id)


def _print_tool_event(ev: dict[str, Any], drain: _ChatDrain) -> None:
    etype = ev.get("type", "")
    if etype == "tool-input-available":
        preview = json.dumps(ev.get("input", {}), default=str)[:140]
        print(f"  • {ev.get('toolName', '?')}({preview})", flush=True)
    elif etype == "tool-output-available":
        name = drain.tool_inputs.get(ev.get("toolCallId", ""), {}).get("name", "?")
        output = ev.get("output", {})
        if isinstance(output, dict) and "error" in output:
            print(f"    ✗ {name} errored: {str(output['error'])[:120]}", flush=True)
        else:
            keys = list(output.keys())[:5] if isinstance(output, dict) else []
            print(f"    ✓ {name} → {keys}", flush=True)


def _print_chat_turn(result: ChatResponse, *, show_tools: bool) -> None:
    # The narrative, not `assistant_message`: the server's assistant_message is
    # the LAST turn's text only, so a run that wrote its findings, called a
    # tool, and closed with one sentence printed just that sentence (often a
    # fragment like "Let me check that.") and dropped the answer.
    text = result.narrative or result.assistant_message
    print()
    if text:
        print(text)
        print()
    print_detail(
        {
            "chat_id": result.chat_id,
            "turns_used": result.turns_used,
            "total_ms": result.total_ms,
            "stop_reason": result.stop_reason,
            "tokens": f"in={result.input_tokens} out={result.output_tokens}",
        },
        [
            ("chat_id", "Chat"),
            ("turns_used", "Turns"),
            ("total_ms", "ms"),
            ("stop_reason", "Stop"),
            ("tokens", "Tokens"),
        ],
    )


def _print_choice_card(card: dict[str, Any]) -> None:
    print()
    print(f"? {card.get('question', '')}")
    for row in card.get("review") or []:
        if isinstance(row, dict):
            label = row.get("label") or row.get("title") or ""
            value = row.get("value") or row.get("text") or row.get("detail") or ""
            print(f"    {label}: {value}" if label else f"    {value}")
        else:
            print(f"    {row}")
    for i, opt in enumerate(card.get("options") or [], 1):
        if isinstance(opt, dict):
            desc = opt.get("description")
            line = f"  {i}. {opt.get('label', '')}"
            print(f"{line} — {desc}" if desc else line)
        else:
            print(f"  {i}. {opt}")
    if card.get("multi_select"):
        print("  (pick several: 1,3)")
    if card.get("allow_other"):
        print("  (or type your own reply)")


def _answer_label(card: dict[str, Any], answer: str, *, is_json: bool) -> str:
    """The message to send for ``--answer``: an option's label, or free text
    when the card allows it. A number that names no option is an error."""
    label = choice_label(card, answer)
    if label is not None:
        return label
    looks_numeric = answer.replace(",", "").replace(" ", "").isdigit()
    if card.get("allow_other") and not looks_numeric:
        return answer
    options = ", ".join(
        f"{i}={o.get('label') if isinstance(o, dict) else o}"
        for i, o in enumerate(card.get("options") or [], 1)
    )
    message = f"--answer {answer!r} matches no option. Options: {options}"
    if is_json:
        from querri.cli._output import print_json_error

        print_json_error("invalid_answer", message, 1)
    else:
        print_error(message)
    raise typer.Exit(code=1)


def _prompt_choice(card: dict[str, Any]) -> str | None:
    """Ask in the terminal. Empty input or EOF leaves the card unanswered."""
    while True:
        try:
            raw = input("choose › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not raw:
            return None
        label = choice_label(card, raw)
        if label is not None:
            return label
        if card.get("allow_other") and not raw.replace(",", "").isdigit():
            return raw
        print_error("Pick an option number or type its label.")


# ── Onboarding (Phase 3 / W01) ──────────────────────────────────────────────


@library_app.command("onboard")
def onboard(
    ctx: typer.Context,
    library_id: str = typer.Option(
        None, "--library-id", "-l",
        help="Library to onboard into (defaults to active or creates new).",
    ),
    library_name: str = typer.Option(
        None, "--name",
        help="Name for the new Library when one is created. "
             "Defaults to 'My Library'.",
    ),
    new: bool = typer.Option(
        False, "--new", "-n",
        help="Force a fresh onboarding chat (ignore the last chat for "
             "this library).",
    ),
) -> None:
    """Run the W01 onboarding interview — question-first, KPI-grounded.

    Interactive: the Librarian asks about your business, you reply, and
    Collections + Questions + KPIs land in your Library as you go. Type
    `:done`, `:quit`, or `:exit` (or just press Enter on an empty prompt
    a second time) to stop. The recap prints at the end.

    The agent runs in onboarding mode — same VercelStream SSE wire format
    as `querri library chat` and `querri views`, with the W01 system prompt
    and the four W01 creation tools (create_collection, add_refining_question,
    propose_kpi, confirm_kpi) plus search/list/record_fact. View
    commissioning is gated off (no data is connected yet).
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    ctx_data = _read_library_context(client)

    # Resolve / create the Library.
    lib_id = library_id or ctx_data.get("library_id")
    if not lib_id:
        # No active library — offer to create one. In headless / non-tty
        # mode, just create it with the default name.
        proposed_name = library_name or "My Library"
        print(f"No active Library found — creating '{proposed_name}'.")
        try:
            created = client.library.create_library(
                name=proposed_name, summary="Created via querri library onboard"
            )
        except Exception as exc:
            raise typer.Exit(code=handle_api_error(exc, is_json=False)) from None
        lib_id = created.id
        ctx_data["library_id"] = lib_id
        _write_library_context(client, ctx_data)
        print(f"Library created: {lib_id}")
        print()

    # Resume an in-progress onboarding chat unless --new.
    chat_id: str | None = None
    if not new:
        last = ctx_data.get(f"onboard_chat_id::{lib_id}")
        if last:
            chat_id = str(last)
            print(f"Resuming onboarding chat: {chat_id}")
            print("(Use --new to start fresh.)")
            print()

    print("─" * 60)
    print("Welcome to Querri onboarding.")
    print(
        "Tell the Librarian what's on your mind about your business —"
    )
    print("we'll shape the questions and metrics together.")
    print()
    print("Type :done (or :quit / :exit) when you're ready to wrap up.")
    print("─" * 60)
    print()

    # Seed the first turn from the user — the agent's system prompt asks
    # the opening question, so we kick off with an empty-ish first message
    # that triggers the greeting. Use a sentinel that the agent will
    # interpret as "start the interview." Per the W01 system prompt, the
    # agent will greet and ask the first question on receiving any opening.
    first_message = "Let's begin the onboarding interview."
    user_message = first_message
    final_lib_recap_chat: str | None = None

    def _print_assistant_block(meta: dict[str, Any], text_chunks: list[str]) -> None:
        # The streamed text first: `assistant_message` is the last turn only.
        assistant_text = (
            "".join(text_chunks) or meta.get("assistant_message") or ""
        ).strip()
        if assistant_text:
            print()
            print(f"Librarian › {assistant_text}")
            print()

    exit_verbs = {":done", ":quit", ":exit", "/done", "/quit", "/exit"}

    while True:
        if user_message in exit_verbs or not user_message:
            break

        # Stream one agent turn.
        assistant_chunks: list[str] = []
        tool_inputs: dict[str, dict[str, Any]] = {}
        turn_meta: dict[str, Any] = {}
        try:
            for ev in client.library.chat_stream(
                library_id=lib_id,
                message=user_message,
                chat_id=chat_id,
                mode="onboarding",
            ):
                etype = ev.get("type", "")
                if etype == "tool-input-available":
                    name = ev.get("toolName", "?")
                    inp = ev.get("input", {})
                    tool_inputs[ev.get("toolCallId", "")] = {
                        "name": name, "input": inp,
                    }
                    # Light progress chip per tool — visible but unobtrusive.
                    label = _onboard_tool_label(name, inp)
                    if label:
                        print(f"  → {label}", flush=True)
                elif etype == "tool-output-available":
                    tcid = ev.get("toolCallId", "")
                    name = tool_inputs.get(tcid, {}).get("name", "?")
                    output = ev.get("output", {})
                    summary = _onboard_tool_result(name, output)
                    if summary:
                        print(f"    {summary}", flush=True)
                elif etype == "data-node-created":
                    node = ev.get("data", {}) or {}
                    kind = node.get("node_kind", "node")
                    n_name = node.get("name", node.get("node_id", "?"))
                    print(
                        f"      • {kind}: {n_name} ({node.get('node_id', '?')})",
                        flush=True,
                    )
                elif etype == "text-delta":
                    assistant_chunks.append(ev.get("delta", ""))
                elif etype == "data-librarian":
                    turn_meta = ev.get("data", {})
                    chat_id = turn_meta.get("chat_id", chat_id)
                elif etype == "finish":
                    pass
        except typer.Exit:
            raise
        except Exception as exc:
            raise typer.Exit(code=handle_api_error(exc, is_json=False)) from None

        _print_assistant_block(turn_meta, assistant_chunks)
        if chat_id:
            ctx_data[f"onboard_chat_id::{lib_id}"] = chat_id
            _write_library_context(client, ctx_data)
            final_lib_recap_chat = chat_id

        # Prompt for the next user input.
        try:
            user_input = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        user_message = user_input

    # Recap.
    print()
    print("═" * 60)
    print("Library Built — Recap")
    print("═" * 60)
    try:
        recap = client.library.get_onboarding_summary(
            library_id=lib_id, chat_id=final_lib_recap_chat
        )
    except Exception as exc:
        # Recap is non-fatal — the onboarding itself succeeded. Surface
        # the error and exit.
        print(f"(Could not fetch recap: {exc})")
        return

    totals = recap.get("totals", {})
    complete = recap.get("complete", False)
    print(
        f"Collections: {totals.get('collections', 0)}   "
        f"Anchor questions: {totals.get('anchor_questions', 0)}   "
        f"Follow-ups: {totals.get('refining_questions', 0)}"
    )
    print(
        f"Metrics: {totals.get('kpis', 0)}   "
        f"Business rules: {totals.get('facts', 0)}"
    )
    print()
    for c in recap.get("collections", []):
        print(f"  • {c.get('name', '?')} ({c.get('id', '?')})")
    for k in recap.get("kpis", []):
        state = k.get("state", "?")
        cats = ", ".join(k.get("categories", []))
        print(f"    [{state}] {k.get('name', '?')} ({cats}) — {k.get('id', '?')}")
    print()
    if complete:
        print("✓ Your library is populated. Next: connect a data source.")
    else:
        print(
            "Your library has a foundation. Add more topics or metrics anytime "
            "with `querri library onboard --library-id "
            f"{lib_id}`."
        )
    print()
    if obj.get("json"):
        print_json(recap)


def _onboard_tool_label(name: str, inp: dict[str, Any]) -> str | None:
    """Compact, user-readable progress chip per tool invocation."""
    if name == "create_collection":
        n = inp.get("name", "?")
        return f"creating topic: {n!r}"
    if name == "add_refining_question":
        q = inp.get("question_text", "?")
        return f"attaching follow-up: {q[:60]!r}"
    if name == "propose_kpi":
        n = inp.get("name", "?")
        cats = inp.get("categories", [])
        return f"proposing metric: {n!r} ({', '.join(cats)})"
    if name == "confirm_kpi":
        n = inp.get("name", "?")
        return f"confirming metric: {n!r}"
    if name == "record_fact":
        s = inp.get("statement", "?")
        return f"recording rule: {s[:60]!r}"
    if name == "search_graph":
        q = inp.get("query", "?")
        return f"searching: {q[:60]!r}"
    if name == "list_by_kind":
        k = inp.get("node_kind", "?")
        return f"listing all {k}s"
    return None


def _onboard_tool_result(name: str, output: dict[str, Any]) -> str | None:
    """Compact result line for tool calls — confirms what landed."""
    if isinstance(output, dict) and "error" in output:
        return f"✗ {name} errored: {str(output['error'])[:120]}"
    if name == "create_collection":
        return f"✓ topic created ({output.get('collection_id', '?')})"
    if name == "add_refining_question":
        return f"✓ follow-up attached ({output.get('refining_question_id', '?')})"
    if name == "propose_kpi":
        m = output.get("measurability_hint", "?")
        return f"✓ metric staged ({output.get('name', '?')}, measurability={m})"
    if name == "confirm_kpi":
        state = output.get("state", "?")
        return f"✓ metric saved [{state}] ({output.get('kpi_id', '?')})"
    if name == "record_fact":
        return f"✓ rule recorded ({output.get('fact_id', '?')})"
    if name == "search_graph":
        focal = output.get("focal_nodes") or []
        return f"  → {len(focal)} match(es)"
    if name == "list_by_kind":
        return f"  → {output.get('count', 0)} found"
    return None


# ── Facts (Phase 2) ────────────────────────────────────────────────────────


@library_app.command("record-fact")
def record_fact(
    ctx: typer.Context,
    statement: str = typer.Argument(..., help="The fact statement itself."),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library (defaults to active)."
    ),
    attach: list[str] = typer.Option(
        None,
        "--attach",
        "-a",
        help="Node ID this fact is about (repeatable). Creates an ABOUT edge.",
    ),
    fact_kind: str = typer.Option(
        "contextual_note",
        "--kind",
        "-k",
        help=(
            "Fact kind, e.g. rule, definition, target, code_list, obligation, "
            "contextual_note, data_quality, timing, scope_constraint. "
            "`querri library fact-kinds` lists what the server accepts."
        ),
    ),
    evidence: list[str] = typer.Option(
        None, "--evidence", "-e",
        help="Evidence URL or doc reference (repeatable).",
    ),
    confidence: float = typer.Option(1.0, "--confidence", min=0.0, max=1.0),
    name: str = typer.Option(
        None, "--name", help="Display name (default: first 80 chars)."
    ),
) -> None:
    """Record a Fact and attach it (via ABOUT edges) to one or more nodes.

    The fact lands as a first-class searchable node, homed in the active
    workspace, so the Librarian surfaces it on related questions. If an
    attached node cannot be seen from that workspace the fact is still
    recorded and a warning says which.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    fact_kind = _check_fact_kind(client, fact_kind, is_json=bool(obj.get("json")))
    try:
        fact = client.library.record_fact(
            library_id=lib_id,
            statement=statement,
            fact_kind=fact_kind,
            source_node_ids=attach or [],
            evidence_refs=evidence or [],
            confidence=confidence,
            name=name,
            workspace_id=_workspace(client),
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(fact.model_dump())
        return
    _print_warnings(fact.warnings)
    if obj.get("quiet"):
        print_id(fact.id)
        return
    print_success(f"Fact recorded: {fact.id}")
    print_detail(
        fact.model_dump(),
        [
            ("statement", "Statement"),
            ("fact_kind", "Kind"),
            ("confidence", "Confidence"),
            ("id", "ID"),
        ],
    )
    if fact.source_node_ids:
        n_attached = len(fact.source_node_ids)
        print_success(f"  attached to {n_attached} node(s) via ABOUT edges")


def _print_warnings(warnings: list[dict[str, Any]]) -> None:
    """Server warnings go to stderr: the write succeeded, but not cleanly."""
    for w in warnings or []:
        ids = ", ".join(str(i) for i in w.get("node_ids") or [])
        msg = w.get("message") or w.get("code") or "warning"
        print(f"warning: {msg}" + (f" [{ids}]" if ids else ""), file=sys.stderr)


def _check_fact_kind(client: Any, kind: str, *, is_json: bool) -> str:
    """Validate ``--kind`` against the server's list (any case).

    A server without ``/library/fact-kinds`` (older deploy) skips the check and
    lets the create route reject a bad kind itself.
    """
    try:
        kinds = client.library.fact_kinds()
    except Exception:  # noqa: BLE001 — no list, no local check
        return kind
    if not isinstance(kinds, list) or not kinds:
        return kind
    for k in kinds:
        if str(k).casefold() == kind.casefold():
            return str(k)
    message = f"Unknown fact kind {kind!r}. Valid kinds: {', '.join(map(str, kinds))}"
    if is_json:
        from querri.cli._output import print_json_error

        print_json_error("invalid_fact_kind", message, 1)
    else:
        print_error(message)
    raise typer.Exit(code=1)


@library_app.command("fact-kinds")
def fact_kinds_cmd(ctx: typer.Context) -> None:
    """List the fact kinds `record-fact --kind` accepts."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        kinds = client.library.fact_kinds()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    if obj.get("json"):
        print_json(kinds)
        return
    for k in kinds:
        print(k)


@library_app.command("facts")
def list_facts(
    ctx: typer.Context,
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library (defaults to active)."
    ),
    in_workspace: str = typer.Option(
        None,
        "--in",
        help="Only Facts homed in this workspace (id, slug or name).",
    ),
    limit: int = typer.Option(100, "--limit", "-n", min=1, max=1000),
    cursor: str = typer.Option(None, "--cursor", help="Cursor from a previous page."),
) -> None:
    """List Facts (business rules, definitions, notes) in a library."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    ws_filter = _resolve_workspace(client, in_workspace, obj) if in_workspace else None
    try:
        result = client.library.list_facts(
            library_id=lib_id, workspace_id=ws_filter, limit=limit, cursor=cursor
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    if obj.get("json"):
        print_json(result.model_dump())
        return
    if obj.get("quiet"):
        for item in result.results:
            print_id(item.id)
        return
    if not result.results:
        print_error(f"No Facts in library {lib_id}.")
        return
    print_table(
        [
            {"name": item.name, "summary": _short(item.summary), "id": item.id}
            for item in result.results
        ],
        [("name", "Name"), ("summary", "Statement"), ("id", "ID")],
    )


@library_app.command("move")
def move_node(
    ctx: typer.Context,
    node_ids: list[str] = typer.Argument(..., help="Library node id(s) to re-home."),
    to: str = typer.Option(
        ..., "--to", help="Destination workspace (id, slug or name)."
    ),
) -> None:
    """Re-home Library nodes (Facts, KPIs, Collections, questions) into another
    workspace. Edges are kept.

    For uploaded files and sources use `querri workspace move`.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    dest = _resolve_workspace(client, to, obj)
    results: list[dict[str, Any]] = []
    failures = 0
    for node_id in node_ids:
        try:
            moved = client.library.move_node(node_id, dest)
            results.append({"id": node_id, **moved})
        except Exception as exc:  # noqa: BLE001 — report each, keep going
            failures += 1
            results.append({"id": node_id, "error": str(exc)})
    if obj.get("json"):
        print_json(results)
    else:
        for r in results:
            if "error" in r:
                print_error(f"{r['id']}: {r['error']}")
            elif obj.get("quiet"):
                print_id(str(r["id"]))
            else:
                print_success(f"{r['id']} → {r.get('workspace_id') or dest}")
    if failures:
        raise typer.Exit(code=1)


@library_app.command("delete")
def delete_node(
    ctx: typer.Context,
    node_id: str = typer.Argument(..., help="Library node id to delete."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation."),
) -> None:
    """Delete a Library node (and its edges)."""
    obj = ctx.ensure_object(dict)
    if not yes and not typer.confirm(f"Delete {node_id}?", default=False):
        raise typer.Exit(code=1)
    client = get_client(ctx)
    try:
        result = client.library.delete_node(node_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    if obj.get("json"):
        print_json(result)
    elif obj.get("quiet"):
        print_id(node_id)
    else:
        print_success(f"Deleted {node_id}")


# ── Collection contents + view build + KPI (P3c) ────────────────────────────


@library_app.command("collection-show")
def collection_show(
    ctx: typer.Context,
    collection_id: str = typer.Argument(..., help="Collection _id (coll_…)."),
) -> None:
    """Show a Collection's full contents — questions (with tri-state answer
    status), KPIs, facts, views, and sources.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        cc = client.library.collection_contents(collection_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(cc.model_dump())
        return

    print_detail(
        cc.collection.model_dump(),
        [("name", "Name"), ("summary", "Summary"), ("id", "ID")],
    )
    questions = ([cc.anchor] if cc.anchor else []) + list(cc.refining_questions)
    if questions:
        print_table(
            [
                {
                    "question": q.question_text,
                    "answer": q.answer_state,
                    "views": str(len(q.answering_views)),
                    "id": q.id,
                }
                for q in questions
            ],
            [("question", "Question"), ("answer", "Answer"),
             ("views", "Views"), ("id", "ID")],
        )
    if cc.views:
        print_table(
            [{"name": v.name, "status": v.status, "id": v.id} for v in cc.views],
            [("name", "View"), ("status", "Status"), ("id", "ID")],
        )
    if cc.kpis:
        print_table(
            [{"name": k.name, "state": k.state, "id": k.id} for k in cc.kpis],
            [("name", "Metric"), ("state", "State"), ("id", "ID")],
        )
    if cc.facts:
        print_success(f"  {len(cc.facts)} fact(s), {len(cc.sources)} source(s)")
    elif cc.sources:
        print_success(f"  {len(cc.sources)} source(s)")


@library_app.command("view-build")
def view_build(
    ctx: typer.Context,
    collection_id: str = typer.Argument(
        ..., help="Collection to build the view into: its id or its name."
    ),
    source: list[str] = typer.Option(
        ..., "--source", "-s",
        help=(
            "Source this view uses (repeatable): a Library node id or the "
            "source's name. A name that matches several sources is refused "
            "with the candidates."
        ),
    ),
    library_id: str = typer.Option(
        None, "--library-id", "-l",
        help="Library to resolve names in (defaults to active).",
    ),
    name: str = typer.Option(None, "--name", help="Short snake_case view name."),
    summary: str = typer.Option(
        None, "--summary", help="1-3 sentence description of what the view computes."
    ),
    answers: list[str] = typer.Option(
        None, "--answers", "-q",
        help="Question id this view answers (repeatable; defaults to the anchor).",
    ),
    instructions: str = typer.Option(
        None, "--instructions", help="Tailored brief for the Views agent."
    ),
) -> None:
    """Build a View into a Collection (headless — no chat). Streams the Views
    agent and prints the resulting view id + status. Can take 30-90s.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    is_json = bool(obj.get("json"))
    lib_id = _maybe_library_id(library_id, client)
    collection_id = _resolve_node_ref(
        client, lib_id, collection_id, ("Collection",), what="collection",
        is_json=is_json,
    )
    source_ids = [
        _resolve_node_ref(
            client, lib_id, ref, ("SourceStub", "ViewStub"), what="source",
            is_json=is_json,
        )
        for ref in source
    ]
    if not is_json:
        typer.echo("Building view (this can take 30-90s)…", err=True)
    result: dict[str, Any] = {}
    try:
        for ev in client.library.build_view_stream(
            collection_id=collection_id,
            source_node_ids=source_ids,
            answers_question_ids=answers or None,
            name=name,
            summary=summary,
            instructions=instructions,
        ):
            etype = ev.get("type", "")
            if etype == "data-view-built":
                result = ev.get("data", {}) or {}
            elif etype == "tool-input-available" and not obj.get("json"):
                typer.echo(f"  ⚡ {ev.get('toolName', '?')}", err=True)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result)
        return
    if result.get("error"):
        print_error(f"View build failed: {result['error']}")
        raise typer.Exit(code=1)
    if obj.get("quiet"):
        print_id(result.get("view_uuid", ""))
        return
    print_success(
        f"View built: {result.get('view_uuid', '?')} [{result.get('status', '?')}]"
    )
    answers_written = result.get("answers_written") or []
    if answers_written:
        print_success(f"  answers {len(answers_written)} question(s)")


def _maybe_library_id(explicit: str | None, client: Any) -> str | None:
    """Like :func:`_resolve_library_id`, but None instead of exiting."""
    if explicit:
        return explicit
    env = os.environ.get("QUERRI_LIBRARY_ID")
    if env:
        return env
    return _read_library_context(client).get("library_id") or None


def _resolve_node_ref(
    client: Any,
    lib_id: str | None,
    ref: str,
    kinds: tuple[str, ...],
    *,
    what: str,
    is_json: bool,
) -> str:
    """A node id, or the id of the one node of ``kinds`` named ``ref``.

    Exact names only (any case): a near-miss is reported with candidates, never
    guessed. A ref that is neither a listed id nor a name, and has no spaces, is
    passed through as an id — the list is capped and may not hold it; the
    server then says whether it exists.
    """
    if lib_id is None:
        return ref
    nodes: list[NodeListItem] = []
    for kind in kinds:
        try:
            listed = client.library.list_nodes(
                library_id=lib_id, node_kind=kind, limit=1000
            )
        except Exception:  # noqa: BLE001 — cannot resolve; let the server judge
            return ref
        nodes.extend(listed.results)
    if any(n.id == ref for n in nodes):
        return ref
    needle = ref.strip().casefold()
    exact = [n for n in nodes if n.name.casefold() == needle]
    if len(exact) == 1:
        return exact[0].id
    if len(exact) > 1:
        _refuse_ref(
            f"{what.capitalize()} name {ref!r} is ambiguous; pass an id",
            exact, is_json=is_json,
        )
    if not any(ch.isspace() for ch in ref):
        return ref
    near = [n for n in nodes if needle in n.name.casefold()]
    _refuse_ref(f"No {what} named {ref!r}", near, is_json=is_json)
    return ref  # unreachable: _refuse_ref exits


def _refuse_ref(message: str, candidates: list[NodeListItem], *, is_json: bool) -> None:
    listed = "; ".join(f"{n.name} ({n.id})" for n in candidates[:10])
    if listed:
        message += f". Candidates: {listed}"
    if is_json:
        from querri.cli._output import print_json_error

        print_json_error("unresolved_reference", message, 1)
    else:
        print_error(message)
    raise typer.Exit(code=1)


@library_app.command("view-rename")
def view_rename(
    ctx: typer.Context,
    view_stub_id: str = typer.Argument(
        ..., help="ViewStub node id (view_…) to rename."
    ),
    name: str = typer.Option(
        None, "--name", "-n",
        help="New view name (sentence case welcome, e.g. 'Revenue by channel').",
    ),
    display_name: str = typer.Option(
        None, "--display-name",
        help="Friendly display title (defaults to a sentence-cased --name).",
    ),
    summary: str = typer.Option(
        None, "--summary", "-s", help="New 1-3 sentence description."
    ),
) -> None:
    """Rename / re-describe a view across both its layers (graph stub +
    legacy source doc), keeping search/routing and the Sources tab in sync.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    if name is None and display_name is None and summary is None:
        print_error("Provide at least one of --name / --display-name / --summary.")
        raise typer.Exit(code=1)
    try:
        result = client.library.rename_view(
            view_stub_id, name=name, display_name=display_name, summary=summary
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    if obj.get("json"):
        print_json(result)
        return
    print_success(
        f"View renamed: {result.get('name', '?')} "
        f"({result.get('display_name') or 'no display name'}) "
        f"[{result.get('view_stub_id', '?')}]"
    )


@library_app.command("kpi-create")
def kpi_create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="KPI display name."),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library (defaults to active)."
    ),
    canonical: str = typer.Option("", "--canonical", help="Canonical name."),
    category: list[str] = typer.Option(
        None,
        "--category",
        "-c",
        help=(
            "KPI category (repeatable, any case). Must be one of the library's "
            "categories; an unknown one is refused with the list."
        ),
    ),
    summary: str = typer.Option("", "--summary", "-s"),
    state: str = typer.Option(
        "draft", "--state", help="draft | active | deprecated | aspirational"
    ),
) -> None:
    """Create a KPI node in the Data Library.

    A KPI is one measure, not a breakdown: it has no "by region" or "by
    channel" dimension. To see a measure split by something, build a View
    (`querri library view-build`) and link the KPI to the question it answers.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    categories = _match_categories(
        client, lib_id, category or [], is_json=bool(obj.get("json"))
    )
    try:
        kpi = client.library.create_kpi(
            library_id=lib_id,
            name=name,
            canonical_name=canonical,
            categories=categories,
            summary=summary,
            state=state,
            workspace_id=_workspace(client),
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    kpi_id = kpi.get("id") or kpi.get("_id") or kpi.get("kpi_id", "?")
    if obj.get("json"):
        print_json(kpi)
        return
    if obj.get("quiet"):
        print_id(kpi_id)
        return
    print_success(f"KPI created: {kpi_id}")
    print_detail(
        {**kpi, "id": kpi_id},
        [("name", "Name"), ("state", "State"), ("id", "ID")],
    )


def _match_categories(
    client: Any, lib_id: str, wanted: list[str], *, is_json: bool
) -> list[str]:
    """Map ``--category`` values onto the library's category names, any case.

    The server's names are canonical (``Efficiency``); ``efficiency`` used to
    be refused with a bare enum error. If the list cannot be read the values go
    through unchanged and the server decides.
    """
    if not wanted:
        return []
    try:
        payload = client.library.list_kpi_categories(library_id=lib_id)
    except Exception:  # noqa: BLE001 — no list, no local check
        return wanted
    rows = payload.get("results") if isinstance(payload, dict) else None
    names = [
        str(r.get("name")) for r in rows or [] if isinstance(r, dict) and r.get("name")
    ]
    if not names:
        return wanted
    out: list[str] = []
    unknown: list[str] = []
    for value in wanted:
        hit = next((n for n in names if n.casefold() == value.casefold()), None)
        if hit is None:
            unknown.append(value)
        else:
            out.append(hit)
    if unknown:
        message = (
            f"Unknown KPI categor{'y' if len(unknown) == 1 else 'ies'}: "
            f"{', '.join(unknown)}. Valid: {', '.join(names)}"
        )
        if is_json:
            from querri.cli._output import print_json_error

            print_json_error("invalid_category", message, 1)
        else:
            print_error(message)
        raise typer.Exit(code=1)
    return out


# ── Seed demo ──────────────────────────────────────────────────────────────


@library_app.command("seed-demo")
def seed_demo(
    ctx: typer.Context,
    fixture: str = typer.Option(
        "demo-acme",
        "--fixture",
        "-f",
        help=(
            "Fixture name: 'demo-acme' or 'curio' "
            "(the multi-system reference business)."
        ),
    ),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library _id (defaults to active)."
    ),
    scale: str = typer.Option(
        None, "--scale",
        help="Curio only: data volume tier — test | dev | full (default dev).",
    ),
    seed: int = typer.Option(
        None, "--seed", help="Curio only: RNG seed (default 42) for reproducible data.",
    ),
) -> None:
    """Seed a library with a substantial demo dataset.

    'demo-acme' is the lightweight column-shape fixture. 'curio' is the
    multi-system reference business (real parquet + knowledge graph + eval set)
    — pair it with `library intake` then `library eval`. Curio respects
    --scale (test/dev/full) and --seed.

    Idempotent: re-running on the same library produces the same node IDs,
    so the second invocation refreshes timestamps without creating dupes.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        result = client.library.seed_fixture(
            library_id=lib_id, fixture=fixture, seed=seed, scale=scale
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    print_success(f"Fixture '{result.fixture}' applied into {result.library_id}")
    print_table(
        [{"kind": k, "count": v} for k, v in result.counts.items()],
        [("kind", "Kind"), ("count", "Count")],
    )


# ── Backfill ───────────────────────────────────────────────────────────────


@library_app.command("backfill")
def backfill(
    ctx: typer.Context,
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Target Library _id (defaults to active)."
    ),
    include_series: bool = typer.Option(
        True,
        "--include-series/--no-series",
        help="Emit one SeriesStub per source column (capped per source).",
    ),
) -> None:
    """Backfill ConnectorStub/SourceStub/ViewStub/SeriesStub from the tenant's
    legacy connectors + sources collections into the Data Library graph.

    Idempotent. Safe to re-run after bulk imports until dual-write hooks ship.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        result = client.library.backfill(
            library_id=lib_id, include_series=include_series
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    print_success(f"Backfill complete into {result.library_id}")
    print_detail(
        {
            **result.counts,
            "library_id": result.library_id,
            "tenant_id": result.tenant_id,
        },
        [
            ("connectors", "Connectors"),
            ("sources", "Sources"),
            ("views", "Views"),
            ("series", "Series"),
            ("skipped", "Skipped (already present)"),
            ("library_id", "Library"),
            ("tenant_id", "Tenant"),
        ],
    )


@library_app.command("intake")
def intake(
    ctx: typer.Context,
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Target Library _id (defaults to active)."
    ),
    include_series: bool = typer.Option(
        True, "--include-series/--no-series",
        help="Emit + enrich one SeriesStub per source column (capped per source).",
    ),
) -> None:
    """Run real intake: connect the tenant's connectors/sources/views into the
    Data Library graph, enrich series with dtype + examples, and link questions
    and KPIs to the sources that answer them.

    Idempotent + incremental — safe to re-run; a re-run on unchanged data is a
    0-delta no-op.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        result = client.library.intake(
            library_id=lib_id, include_series=include_series
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    print_success(f"Intake complete into {result.library_id}")
    print_detail(
        {
            **{f"structure_{k}": v for k, v in result.structure.items()},
            **{f"link_{k}": v for k, v in result.link.items()},
            "library_id": result.library_id,
        },
        [
            ("structure_sources", "Sources connected"),
            ("structure_series", "Series created"),
            ("structure_enriched", "Series enriched"),
            ("structure_edges", "Structural edges"),
            ("link_questions_linked", "Questions linked"),
            ("link_kpis_linked", "KPIs linked"),
            ("link_answerable", "Answerable questions"),
            ("link_edges", "Relevance edges"),
            ("library_id", "Library"),
        ],
    )



def _print_scope(workspace_id: str | None) -> None:
    """Say which room the answer came out of.

    An answer from a wider scope than you set looks identical to a correctly
    scoped one, so it is printed rather than assumed. The difference is not
    cosmetic — asked "what is the total of the invoices?" over a 30-database
    tenant, the unscoped ask fanned out across five unrelated systems and
    opened with an airline booking total; scoped to one workspace it answered
    the question.
    """
    if workspace_id:
        print(f"\n  scope: workspace {workspace_id}", file=sys.stderr)
    else:
        print("\n  scope: whole organization", file=sys.stderr)


@library_app.command("ask")
def ask(
    ctx: typer.Context,
    question: str = typer.Argument(..., help="The question to ask the library."),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Target Library _id (defaults to active)."
    ),
) -> None:
    """Ask the library a question. Routes to the source that answers it, runs it
    under RLS, and returns a narrative answer with provenance. Read-only —
    declines honestly when no source clears the bar.

    Scoped to the active workspace (``querri workspace use``, or
    ``--workspace``): the answer comes only from data you can see from where you
    are standing. The scope the answer was actually produced under is printed
    with it, because the claim is a hint the server may refuse.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        result = client.library.ask(library_id=lib_id, question=question)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    if result.declined:
        print_detail(
            {"a": result.answer, "outcome": result.outcome or "—"},
            [("a", "Declined"), ("outcome", "Outcome")],
        )
        # A decline is exactly when the scope matters most: "I found nothing"
        # reads very differently if it only looked in one room.
        _print_scope(result.workspace_id)
        for att in result.attempted or []:
            print_detail(
                att,
                [
                    ("cluster", "Cluster"),
                    ("tables", "Tables"),
                    ("reason", "Reason"),
                    ("error", "Error"),
                    ("sql", "Attempted SQL"),
                ],
            )
        return
    print_success(result.answer)
    _print_scope(result.workspace_id)
    # Provenance is per-cluster: one block per contributing source cluster.
    for prov in result.provenance or []:
        print_detail(
            prov,
            [
                ("cluster", "Cluster"),
                ("tables", "Tables"),
                ("total_rows", "Rows"),
                ("generated_sql", "SQL"),
            ],
        )


@library_app.command("eval")
def eval_cmd(
    ctx: typer.Context,
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Target Library _id (defaults to active)."
    ),
    routing_only: bool = typer.Option(
        True, "--routing-only/--full",
        help="Routing hit-rate only (answer-correctness eval lands in Phase 6).",
    ),
) -> None:
    """Evaluate the Data Library against the seeded Curio eval set.

    Scores routing hit-rate: for each answerable question, does Search route to
    a correct source? Requires a Curio-seeded + intaken library.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        result = client.library.eval(library_id=lib_id, routing_only=routing_only)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    routing = result.routing or {}
    print_success(
        f"Routing hit-rate: {routing.get('hits', 0)}/{routing.get('total', 0)} "
        f"= {routing.get('hit_rate', 0.0)}"
    )
    for r in routing.get("results", []):
        mark = "✓" if r.get("hit") else "✗"
        print_detail(
            {"q": f"{mark} [{r['id']}] {r['question']}"},
            [("q", "Question")],
        )


@library_app.command("consolidate")
def consolidate_cmd(
    ctx: typer.Context,
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Target Library _id (defaults to active)."
    ),
    commit: bool = typer.Option(
        False, "--commit",
        help="Actually commission Views + record Facts. Default: dry-run.",
    ),
    question: str = typer.Option(
        None, "--question", "-q",
        help="Target a single metric (case-insensitive substring match).",
    ),
    limit: int = typer.Option(3, "--limit", help="Max candidates to process."),
    min_systems: int = typer.Option(
        2, "--min-systems", help="Min distinct systems for a candidate."
    ),
    unify: bool = typer.Option(
        False, "--unify",
        help="Also build the entity-resolved unified view (resolves the same "
             "product across channels; currencies kept separate, no blind FX).",
    ),
    replace: bool = typer.Option(
        False, "--replace",
        help="Re-commission even if a view already answers the question "
             "(supersedes it). Default: skip already-consolidated questions.",
    ),
) -> None:
    """Close the learning loop: mine the ask log for hard, cross-system metrics
    and commission unified per-channel Views so the next ask answers in one
    cheap pass.

    Dry-run by default — lists ranked candidates and what it WOULD build. Pass
    --commit to commission Views + record Facts (slow: ~1-2 min per View).
    --unify also builds the cross-channel entity-resolved view on top.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        result = client.library.consolidate(
            library_id=lib_id, commit=commit, question=question,
            limit=limit, min_systems=min_systems, unify=unify, replace=replace,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    if result.dry_run:
        skipped = getattr(result, "skipped_handled", 0)
        extra = (
            f"; {skipped} already consolidated (skipped — use --replace to rebuild)"
            if skipped else ""
        )
        print_success(
            f"{result.candidate_count} consolidation candidate(s) — dry run "
            f"(pass --commit to build){extra}"
        )
        print_table(
            [
                {
                    "score": c.get("score"),
                    "freq": c.get("frequency"),
                    "systems": ", ".join(c.get("systems", [])),
                    "question": c.get("question"),
                }
                for c in result.candidates
            ],
            [
                ("score", "Score"),
                ("freq", "Freq"),
                ("systems", "Systems"),
                ("question", "Question"),
            ],
            ctx=ctx,
        )
        return

    ok = [o for o in result.commissioned if o.get("status") == "commissioned"]
    print_success(f"Commissioned {len(ok)}/{len(result.commissioned)} view(s)")
    for o in result.commissioned:
        mark = "✓" if o.get("status") == "commissioned" else "✗"
        fields = {
            "q": f"{mark} {o.get('question')}",
            "view": o.get("name") or "—",
            "systems": ", ".join(o.get("systems", [])),
            "fact": o.get("fact_id") or "—",
            "err": o.get("error") or "—",
        }
        cols = [
            ("q", "Question"), ("view", "Per-channel view"),
            ("systems", "Systems"), ("fact", "Fact"), ("err", "Error"),
        ]
        # Surface the entity-resolved unified view (Part 2 / --unify) when present.
        if o.get("unified_view_uuid") or o.get("unified_error"):
            fields["uview"] = o.get("unified_name") or "—"
            fields["entities"] = str(o.get("entities_resolved") or "—")
            fields["uerr"] = o.get("unified_error") or "—"
            cols += [
                ("uview", "Unified view"),
                ("entities", "Entities resolved"),
                ("uerr", "Unified error"),
            ]
        print_detail(fields, cols)


# ── Zoom (vector-seeded multi-focal graph zoom) ───────────────────────────


@library_app.command("zoom")
def zoom_cmd(
    ctx: typer.Context,
    query: str = typer.Argument(
        None,
        help="Query to embed + resolve focals from. Omit if --focal is provided.",
    ),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library (defaults to active)."
    ),
    focal_ids: list[str] = typer.Option(
        None, "--focal", "-F",
        help="Skip ANN and zoom directly from these node IDs (repeatable).",
    ),
    zoom: int = typer.Option(
        25, "--zoom", "-z", min=1, max=100,
        help="Zoom level: 1=tight, 100=wide. distance_decay = (zoom/100)^hops.",
    ),
    budget_tokens: int = typer.Option(
        2000, "--budget", "-b", min=200, max=20000,
        help="Approximate token budget for the assembled subgraph.",
    ),
    top_k_focal: int = typer.Option(5, "--top-k", "-k", min=1, max=20),
    confidence_floor: float = typer.Option(
        0.55, "--threshold", "-t", min=0.0, max=1.0,
        help="Drop focal candidates below this cosine similarity.",
    ),
    kinds: list[str] = typer.Option(
        None, "--kind", help="Filter focal candidates by node_kind (repeatable)."
    ),
    explain: bool = typer.Option(
        False, "--explain", help="Show timing breakdown + algorithm decisions.",
    ),
) -> None:
    """Vector-seeded multi-focal graph zoom.

    Returns the focal nodes resolved from the query embedding plus the
    subgraph traversed outward (up to 2 hops), scored by edge_strength ×
    distance_decay. The patent-defensible retrieval primitive.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    if not query and not focal_ids:
        print_error("Pass a query argument or --focal <id> (repeatable).")
        raise typer.Exit(code=1)
    try:
        result = client.library.zoom(
            library_id=lib_id,
            query=query,
            focal_ids=focal_ids or None,
            zoom=zoom,
            budget_tokens=budget_tokens,
            top_k_focal=top_k_focal,
            confidence_floor=confidence_floor,
            node_kinds=kinds or None,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    if explain:
        s = result.stats
        print_detail(
            {
                "embedding_model": result.embedding_model,
                "embed_ms": s.embed_ms,
                "qdrant_ann_ms": s.qdrant_ann_ms,
                "mongo_traverse_ms": s.mongo_traverse_ms,
                "total_ms": s.total_ms,
                "focal_count": s.focal_count,
                "subgraph_node_count": s.subgraph_node_count,
                "candidates_considered": s.candidates_considered,
                "budget_used_chars": s.budget_used_chars,
                "budget_used_pct": s.budget_used_pct,
                "kind_diversity_rebalance_applied":
                    s.kind_diversity_rebalance_applied,
                "confidence_floor": s.confidence_floor,
                "zoom": s.zoom,
            },
            [
                ("embedding_model", "Embedding model"),
                ("embed_ms", "Embed (ms)"),
                ("qdrant_ann_ms", "ANN (ms)"),
                ("mongo_traverse_ms", "Traverse (ms)"),
                ("total_ms", "Total (ms)"),
                ("focal_count", "Focals"),
                ("subgraph_node_count", "Subgraph size"),
                ("candidates_considered", "Candidates"),
                ("budget_used_pct", "Budget used (%)"),
                ("budget_used_chars", "Budget used (chars)"),
                ("kind_diversity_rebalance_applied", "Kind-diversity rebalance"),
                ("confidence_floor", "Confidence floor"),
                ("zoom", "Zoom"),
            ],
        )
        print()

    if not result.focal_nodes:
        print_error(
            "No focal nodes cleared the confidence threshold. "
            f"Lower --threshold (current: {confidence_floor}) or refine the query."
        )
        raise typer.Exit(code=3)

    print_success(f"Focals ({len(result.focal_nodes)}):")
    print_table(
        [
            {
                "score": f"{f.score:.3f}",
                "tier": f.confidence_tier,
                "kind": f.node_kind,
                "name": f.name,
                "id": f.node_id,
            }
            for f in result.focal_nodes
        ],
        [
            ("score", "Score"), ("tier", "Tier"), ("kind", "Kind"),
            ("name", "Name"), ("id", "ID"),
        ],
    )
    print()
    print_success(
        f"Subgraph ({len(result.subgraph_nodes)} nodes, "
        f"{result.stats.subgraph_node_count} total, "
        f"{result.stats.budget_used_pct}% of budget):"
    )
    print_table(
        [
            {
                "strength": f"{n.edge_strength:.3f}",
                "hops": n.hops,
                "kind": n.node_kind,
                "name": n.name,
                "path": "/".join(n.edge_path) or "(focal)",
            }
            for n in result.subgraph_nodes
        ],
        [
            ("strength", "Strength"), ("hops", "Hops"),
            ("kind", "Kind"), ("name", "Name"), ("path", "Path"),
        ],
    )


# ── Search ─────────────────────────────────────────────────────────────────


@library_app.command("search")
def search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Query string to embed and search."),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library scope (defaults to active)."
    ),
    limit: int = typer.Option(10, "--limit", "-n", min=1, max=100),
    surface: str = typer.Option(
        "node_summaries",
        "--surface",
        help='"node_summaries" (default) or "questions"',
    ),
    kinds: list[str] = typer.Option(
        None,
        "--kind",
        "-k",
        help=(
            "Filter by node_kind (repeatable). "
            "E.g. --kind Collection --kind SourceStub."
        ),
    ),
) -> None:
    """Vector-ANN semantic search over the Data Library."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id, client)
    try:
        result = client.library.search(
            query=query,
            library_id=lib_id,
            limit=limit,
            surface=surface,
            node_kinds=kinds or None,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(result.model_dump())
        return

    if not result.results:
        print_error(f'No hits for "{query}".')
        return

    print_table(
        [
            {
                "score": f"{hit.score:.3f}",
                "kind": hit.node_kind or "?",
                "name": hit.name or "?",
                "id": hit.node_id,
            }
            for hit in result.results
        ],
        [("score", "Score"), ("kind", "Kind"), ("name", "Name"), ("id", "ID")],
    )
    print_detail(
        result.model_dump(),
        [("embedding_model", "Embedding model"), ("surface", "Surface")],
    )
