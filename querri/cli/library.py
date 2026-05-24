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
