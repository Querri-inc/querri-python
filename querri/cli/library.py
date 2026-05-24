"""querri library — interact with the Data Library (Phase 1)."""

from __future__ import annotations

import json
import os
from pathlib import Path

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

library_app = typer.Typer(
    name="library",
    help=(
        "Data Library — graph + semantic search backing the librarian agent.\n\n"
        "Phase 1 surface: create libraries / collections / questions, get a node "
        "by id, run vector-ANN search, seed demo fixtures, check health."
    ),
    no_args_is_help=True,
)


# ── Workspace state ────────────────────────────────────────────────────────
#
# Default library_id for subsequent commands. Resolution order:
#   1. --library-id flag (when present on the command)
#   2. QUERRI_LIBRARY_ID env var
#   3. ~/.querri/library_context.json (set via `querri library use <id>`)
#   4. error with guidance


_LIBRARY_CONTEXT_FILE = Path.home() / ".querri" / "library_context.json"


def _read_library_context() -> dict[str, str]:
    if not _LIBRARY_CONTEXT_FILE.exists():
        return {}
    try:
        return json.loads(_LIBRARY_CONTEXT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_library_context(data: dict[str, str]) -> None:
    _LIBRARY_CONTEXT_FILE.parent.mkdir(mode=0o700, exist_ok=True)
    _LIBRARY_CONTEXT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(_LIBRARY_CONTEXT_FILE, 0o600)
    except OSError:
        pass


def _resolve_library_id(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("QUERRI_LIBRARY_ID")
    if env:
        return env
    ctx_data = _read_library_context()
    if ctx_data.get("library_id"):
        return ctx_data["library_id"]
    print_error(
        "No active library. Pass --library-id, set QUERRI_LIBRARY_ID, "
        "or run 'querri library use <library-id>'."
    )
    raise typer.Exit(code=1)


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
        help="Anchor question text — creates AnchorQuestion + ANCHOR_OF edge in the same call.",
    ),
) -> None:
    """Create a Collection inside a Library, optionally seeded with an anchor question."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id)
    try:
        coll = client.library.create_collection(
            library_id=lib_id,
            name=name,
            summary=summary,
            anchor_question_text=anchor,
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
    library_id: str = typer.Option(..., "--library-id", "-l", help="Parent Library _id."),
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
    display_name = name or question_text[:50]
    try:
        if refining:
            q = client.library.create_refining_question(
                library_id=library_id,
                name=display_name,
                question_text=question_text,
            )
        else:
            q = client.library.create_anchor_question(
                library_id=library_id,
                name=display_name,
                question_text=question_text,
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
    else:
        truncated = node.summary[:120] + ("..." if len(node.summary) > 120 else "")
        print_detail(
            {
                "id": node.id,
                "name": node.name,
                "node_kind": node.node_kind,
                "library_id": node.library_id,
                "summary": truncated,
            },
            [
                ("id", "ID"),
                ("name", "Name"),
                ("node_kind", "Kind"),
                ("library_id", "Library"),
                ("summary", "Summary"),
            ],
        )


# ── Workspace ──────────────────────────────────────────────────────────────


@library_app.command("use")
def use_library(
    ctx: typer.Context,
    library_id: str = typer.Argument(..., help="Library _id to set as active."),
) -> None:
    """Set the active library for subsequent commands.

    Stored in ``~/.querri/library_context.json`` and used as the default
    --library-id when commands don't pass one explicitly.
    """
    _write_library_context({"library_id": library_id})
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
    lib_id = _resolve_library_id(library_id)
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
    lib_id = _resolve_library_id(library_id)
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
                "summary": (item.summary[:60] + "…") if len(item.summary) > 60 else item.summary,
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
        print_error("No Library nodes in tenant. Run `querri library create-library <name>` first.")
        return

    print_table(
        [
            {
                "name": item.name,
                "summary": (item.summary[:60] + "…") if len(item.summary) > 60 else item.summary,
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
    lib_id = _resolve_library_id(library_id)
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
                "summary": (item.summary[:60] + "…") if len(item.summary) > 60 else item.summary,
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
    lib_id = _resolve_library_id(library_id)
    try:
        q = client.library.create_refining_question(
            library_id=lib_id,
            name=name or question_text[:50],
            question_text=question_text,
            anchor_question_id=anchor_id,
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
) -> None:
    """Chat with the Librarian agent — search, record facts, commission views."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id)

    ctx_data = _read_library_context()
    resolved_chat = chat_id
    if not resolved_chat and not new:
        # Re-use last chat for THIS library if one exists in workspace state.
        last = ctx_data.get(f"chat_id::{lib_id}")
        if last:
            resolved_chat = str(last)

    if obj.get("json"):
        # JSON mode: drain everything into one ChatResponse.
        try:
            result = client.library.chat(
                library_id=lib_id, message=message, chat_id=resolved_chat
            )
        except Exception as exc:
            raise typer.Exit(
                code=handle_api_error(exc, is_json=True)
            ) from None
        ctx_data[f"chat_id::{lib_id}"] = result.chat_id
        _write_library_context(ctx_data)
        print_json(result.model_dump())
        return

    # Interactive: stream events to the terminal as they arrive.
    import json as _json
    final_chat_id = resolved_chat or ""
    assistant_text = ""
    try:
        for ev in client.library.chat_stream(
            library_id=lib_id, message=message, chat_id=resolved_chat
        ):
            etype = ev.get("type")
            if etype == "tool_use" and show_tools:
                inp_preview = _json.dumps(ev.get("input", {}), default=str)[:140]
                print(f"  • {ev.get('name', '?')}({inp_preview})", flush=True)
            elif etype == "tool_result" and show_tools:
                dur = ev.get("duration_ms", 0)
                res = ev.get("result", {})
                if isinstance(res, dict) and "error" in res:
                    print(f"    ✗ {ev.get('name', '?')} errored in {dur}ms: {res['error'][:120]}", flush=True)
                else:
                    keys = list(res.keys())[:5] if isinstance(res, dict) else []
                    print(f"    ✓ {ev.get('name', '?')} → {keys} ({dur}ms)", flush=True)
            elif etype == "tool_progress" and show_tools:
                # Pass-through Views-agent chunk — terse marker only.
                print(".", end="", flush=True)
            elif etype == "assistant_text":
                assistant_text = ev.get("text", "")
            elif etype == "done":
                final_chat_id = ev.get("chat_id", final_chat_id)
                if show_tools:
                    print()  # newline after progress dots
                if not assistant_text:
                    assistant_text = ev.get("assistant_message", "")
                print()
                print(assistant_text)
                print()
                print_detail(
                    {
                        "chat_id": final_chat_id,
                        "turns_used": ev.get("turns_used", 0),
                        "total_ms": ev.get("total_ms", 0),
                        "stop_reason": ev.get("stop_reason", ""),
                        "tokens": f"in={ev.get('input_tokens', 0)} out={ev.get('output_tokens', 0)}",
                    },
                    [
                        ("chat_id", "Chat"),
                        ("turns_used", "Turns"),
                        ("total_ms", "ms"),
                        ("stop_reason", "Stop"),
                        ("tokens", "Tokens"),
                    ],
                )
            elif etype == "error":
                print_error(ev.get("message", "stream error"))
                raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=False)) from None

    # Persist active chat_id so the next CLI invocation continues this chat.
    ctx_data[f"chat_id::{lib_id}"] = final_chat_id
    _write_library_context(ctx_data)


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
        help="contextual_note | data_quality | timing | scope_constraint",
    ),
    evidence: list[str] = typer.Option(
        None, "--evidence", "-e",
        help="Evidence URL or doc reference (repeatable).",
    ),
    confidence: float = typer.Option(1.0, "--confidence", min=0.0, max=1.0),
    name: str = typer.Option(None, "--name", help="Display name (default: first 80 chars)."),
) -> None:
    """Record a Fact and attach it (via ABOUT edges) to one or more nodes.

    Phase 2 supports the four non-hypothesis fact kinds per Workflow 03.
    The fact lands as a first-class searchable node in the graph, so the
    Librarian agent surfaces it on future related queries.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id)
    try:
        fact = client.library.record_fact(
            library_id=lib_id,
            statement=statement,
            fact_kind=fact_kind,
            source_node_ids=attach or [],
            evidence_refs=evidence or [],
            confidence=confidence,
            name=name,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(fact.model_dump())
        return
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
        print_success(f"  attached to {len(fact.source_node_ids)} node(s) via ABOUT edges")


# ── Seed demo ──────────────────────────────────────────────────────────────


@library_app.command("seed-demo")
def seed_demo(
    ctx: typer.Context,
    fixture: str = typer.Option(
        "demo-acme",
        "--fixture",
        "-f",
        help="Fixture name (currently: demo-acme).",
    ),
    library_id: str = typer.Option(
        None, "--library-id", "-l", help="Library _id (defaults to active)."
    ),
) -> None:
    """Seed a library with a substantial demo dataset.

    Idempotent: re-running on the same library produces the same node IDs,
    so the second invocation refreshes timestamps without creating dupes.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id)
    try:
        result = client.library.seed_fixture(library_id=lib_id, fixture=fixture)
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
    lib_id = _resolve_library_id(library_id)
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
        {**result.counts, "library_id": result.library_id, "tenant_id": result.tenant_id},
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
    lib_id = _resolve_library_id(library_id)
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
        help="Filter by node_kind (repeatable). E.g. --kind Collection --kind SourceStub.",
    ),
) -> None:
    """Vector-ANN semantic search over the Data Library."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    lib_id = _resolve_library_id(library_id)
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
