"""querri library — interact with the Data Library (Phase 1)."""

from __future__ import annotations

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
        "by id, run vector-ANN search, check health."
    ),
    no_args_is_help=True,
)


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
    library_id: str = typer.Option(..., "--library-id", "-l", help="Parent Library _id."),
    summary: str = typer.Option("", "--summary", "-s"),
) -> None:
    """Create a Collection inside a Library."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        coll = client.library.create_collection(
            library_id=library_id, name=name, summary=summary
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(coll.model_dump())
    elif obj.get("quiet"):
        print_id(coll.id)
    else:
        print_success(f"Collection created: {coll.id}")
        print_detail(
            coll.model_dump(),
            [("name", "Name"), ("library_id", "Library"), ("id", "ID")],
        )


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


# ── Backfill ───────────────────────────────────────────────────────────────


@library_app.command("backfill")
def backfill(
    ctx: typer.Context,
    library_id: str = typer.Option(..., "--library-id", "-l", help="Target Library _id."),
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
    try:
        result = client.library.backfill(
            library_id=library_id, include_series=include_series
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
    library_id: str = typer.Option(..., "--library-id", "-l", help="Library scope."),
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
    try:
        result = client.library.search(
            query=query,
            library_id=library_id,
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
