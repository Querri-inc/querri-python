"""Paired sync/async tests for the Library SDK resource — WS-D6.

Closes the 🔴 cross-phase commitment gap from server-api's PROJECT.md:
"Sync + async parity in the SDK ... tested with respx." The
`querri.resources.library.Library` + `AsyncLibrary` classes had ZERO test
coverage before this file — a 270-line client-facing surface that ships
untested. R11 audit's largest cross-repo gap.

## Design

Each method is tested in both classes. The test signatures + assertions
are deliberately structured as `(method_name, sync_call, async_call,
expected_url, expected_body_partial)` parametric data so:

1. Parity is enforced structurally — adding a sync method without its
   async sibling means a test rows below has no awaitable to call.
2. Wire contract is asserted (URL + method + body shape).
3. Response unwrapping is asserted (envelope handling for /status;
   pass-through for other routes).

## What this does NOT cover

- `chat_stream` / `chat` streaming methods — those need a separate
  pytest-asyncio + respx streaming fixture. Folded into WS-D6.1 as a
  later commit if scope requires; for now the chat methods are pinned
  via integration tests in server-api/tests/integration/test_library_chat_abort.py
  (the route-side guarantee that's harder to reach from SDK-side mocks).
"""

from __future__ import annotations

import httpx
import pytest
import respx

from querri._base_client import AsyncHTTPClient, SyncHTTPClient
from querri._config import ClientConfig
from querri.resources.library import AsyncLibrary, Library

BASE = "https://test.querri.com/api/v1"


def _make_config() -> ClientConfig:
    return ClientConfig(
        api_key="qk_test",
        org_id="org_test",
        base_url=BASE,
        timeout=10.0,
        max_retries=0,
    )


def _sync_lib() -> Library:
    return Library(SyncHTTPClient(_make_config()))


def _async_lib() -> AsyncLibrary:
    return AsyncLibrary(AsyncHTTPClient(_make_config()))


# ── create_library ────────────────────────────────────────────────────────


@respx.mock
def test_sync_create_library():
    respx.post(f"{BASE}/library/libraries").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "lib_org_test_aaa",
                "name": "Primary",
                "summary": "Primary library",
                "node_kind": "Library",
                "library_id": "lib_org_test_aaa",
            },
        )
    )
    lib = _sync_lib()
    result = lib.create_library(name="Primary")
    assert result.id == "lib_org_test_aaa"
    assert result.node_kind == "Library"


@respx.mock
@pytest.mark.asyncio
async def test_async_create_library():
    respx.post(f"{BASE}/library/libraries").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "lib_org_test_aaa",
                "name": "Primary",
                "summary": "Primary library",
                "node_kind": "Library",
                "library_id": "lib_org_test_aaa",
            },
        )
    )
    lib = _async_lib()
    result = await lib.create_library(name="Primary")
    assert result.id == "lib_org_test_aaa"


# ── create_collection (incl. one-shot anchor) ─────────────────────────────


@respx.mock
def test_sync_create_collection_one_shot_anchor():
    route = respx.post(f"{BASE}/library/collections").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "coll_org_test_xyz",
                "name": "Revenue",
                "summary": "Revenue analytics",
                "node_kind": "Collection",
                "library_id": "lib_org_test_aaa",
                "anchor_question": {
                    "id": "q_anchor_org_test_001",
                    "name": "WBR revenue",
                    "question_text": "What drove last quarter's revenue?",
                    "node_kind": "AnchorQuestion",
                },
            },
        )
    )
    lib = _sync_lib()
    body = lib.create_collection(
        library_id="lib_org_test_aaa",
        name="Revenue",
        summary="Revenue analytics",
        anchor_question_text="What drove last quarter's revenue?",
    )
    assert body["anchor_question"]["id"] == "q_anchor_org_test_001"
    sent = route.calls[0].request.read()
    assert b"anchor_question_text" in sent


@respx.mock
@pytest.mark.asyncio
async def test_async_create_collection_one_shot_anchor():
    route = respx.post(f"{BASE}/library/collections").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "coll_org_test_xyz",
                "name": "Revenue",
                "summary": "Revenue analytics",
                "node_kind": "Collection",
                "library_id": "lib_org_test_aaa",
                "anchor_question": {
                    "id": "q_anchor_org_test_001",
                    "name": "WBR",
                    "question_text": "What?",
                    "node_kind": "AnchorQuestion",
                },
            },
        )
    )
    lib = _async_lib()
    body = await lib.create_collection(
        library_id="lib_org_test_aaa",
        name="Revenue",
        summary="Revenue analytics",
        anchor_question_text="What?",
    )
    assert body["anchor_question"]["id"] == "q_anchor_org_test_001"
    sent = route.calls[0].request.read()
    assert b"anchor_question_text" in sent


# ── questions/anchor + questions/refining ─────────────────────────────────


@respx.mock
def test_sync_create_anchor_question():
    respx.post(f"{BASE}/library/questions/anchor").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "q_anchor_org_test_a",
                "name": "Q",
                "question_text": "Q?",
                "node_kind": "AnchorQuestion",
                "library_id": "lib_org_test_aaa",
            },
        )
    )
    lib = _sync_lib()
    result = lib.create_anchor_question(
        library_id="lib_org_test_aaa", name="Q", question_text="Q?",
    )
    assert result.id == "q_anchor_org_test_a"


@respx.mock
@pytest.mark.asyncio
async def test_async_create_refining_question():
    respx.post(f"{BASE}/library/questions/refining").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "q_refining_org_test_r",
                "name": "RQ",
                "question_text": "RQ?",
                "node_kind": "RefiningQuestion",
                "library_id": "lib_org_test_aaa",
            },
        )
    )
    lib = _async_lib()
    result = await lib.create_refining_question(
        library_id="lib_org_test_aaa",
        name="RQ",
        question_text="RQ?",
        anchor_question_id="q_anchor_org_test_a",
    )
    assert result.id == "q_refining_org_test_r"


# ── link (edges) ───────────────────────────────────────────────────────────


@respx.mock
def test_sync_link():
    route = respx.post(f"{BASE}/library/edges").mock(
        return_value=httpx.Response(
            200,
            json={
                "a_id": "coll_a", "b_id": "coll_b",
                "relation": "semantic_neighbor", "tenant_id": "org_test",
            },
        )
    )
    lib = _sync_lib()
    result = lib.link(a_id="coll_a", b_id="coll_b", relation="semantic_neighbor")
    assert result.relation == "semantic_neighbor"
    sent = route.calls[0].request.read()
    assert b'"weight":1.0' in sent
    assert b'"confidence":1.0' in sent


@respx.mock
@pytest.mark.asyncio
async def test_async_link():
    respx.post(f"{BASE}/library/edges").mock(
        return_value=httpx.Response(
            200,
            json={
                "a_id": "coll_a", "b_id": "coll_b",
                "relation": "semantic_neighbor", "tenant_id": "org_test",
            },
        )
    )
    lib = _async_lib()
    result = await lib.link(
        a_id="coll_a", b_id="coll_b", relation="semantic_neighbor",
    )
    assert result.relation == "semantic_neighbor"


# ── status (envelope unwrap) ──────────────────────────────────────────────


_STATUS_ENVELOPE = {
    "data": {
        "tenant_id": "org_test",
        "counts_by_kind": {"Library": 1, "Collection": 3},
        "total_nodes": 4,
    },
    "library_id": "lib_org_test_aaa",
    "telemetry": {"latency_ms": 12},
}


@respx.mock
def test_sync_status_unwraps_envelope():
    """The C2.1 pilot route returns SPEC §5.1 envelope; SDK unwraps to a
    flat StatusResponse. Pins the unwrap contract pinned by
    `_unwrap_envelope` at resources/library.py:49-74."""
    respx.get(f"{BASE}/library/status?library_id=lib_org_test_aaa").mock(
        return_value=httpx.Response(200, json=_STATUS_ENVELOPE)
    )
    lib = _sync_lib()
    result = lib.status(library_id="lib_org_test_aaa")
    assert result.library_id == "lib_org_test_aaa"
    assert result.tenant_id == "org_test"
    assert result.counts_by_kind == {"Library": 1, "Collection": 3}
    assert result.total_nodes == 4


@respx.mock
@pytest.mark.asyncio
async def test_async_status_unwraps_envelope():
    respx.get(f"{BASE}/library/status?library_id=lib_org_test_aaa").mock(
        return_value=httpx.Response(200, json=_STATUS_ENVELOPE)
    )
    lib = _async_lib()
    result = await lib.status(library_id="lib_org_test_aaa")
    assert result.library_id == "lib_org_test_aaa"
    assert result.total_nodes == 4


# ── list_nodes ────────────────────────────────────────────────────────────


@respx.mock
def test_sync_list_nodes_passes_query_params():
    route = respx.get(
        f"{BASE}/library/nodes?library_id=lib_org_test_aaa"
        f"&node_kind=Collection&limit=10"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "library_id": "lib_org_test_aaa",
                "node_kind": "Collection",
                "results": [
                    {"id": "coll_1", "name": "A", "node_kind": "Collection",
                     "summary": ""},
                ],
            },
        )
    )
    lib = _sync_lib()
    result = lib.list_nodes(
        library_id="lib_org_test_aaa", node_kind="Collection", limit=10
    )
    assert route.called
    assert len(result.results) == 1
    assert result.results[0].id == "coll_1"


@respx.mock
@pytest.mark.asyncio
async def test_async_list_nodes_passes_query_params():
    respx.get(
        f"{BASE}/library/nodes?library_id=lib_org_test_aaa"
        f"&node_kind=Collection&limit=10"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "library_id": "lib_org_test_aaa",
                "node_kind": "Collection",
                "results": [],
            },
        )
    )
    lib = _async_lib()
    result = await lib.list_nodes(
        library_id="lib_org_test_aaa", node_kind="Collection", limit=10
    )
    assert result.node_kind == "Collection"
    assert result.results == []


# ── get_node ──────────────────────────────────────────────────────────────


@respx.mock
def test_sync_get_node():
    respx.get(f"{BASE}/library/nodes/coll_org_test_xyz").mock(
        return_value=httpx.Response(
            200,
            json={
                "_id": "coll_org_test_xyz",
                "name": "Revenue",
                "node_kind": "Collection",
                "library_id": "lib_org_test_aaa",
                "tenant_id": "org_test",
                "summary": "Revenue analytics",
                "extra_field": "should be carried in extra",
            },
        )
    )
    lib = _sync_lib()
    node = lib.get_node("coll_org_test_xyz")
    assert node.id == "coll_org_test_xyz"
    assert node.summary == "Revenue analytics"
    assert node.extra["extra_field"] == "should be carried in extra"


@respx.mock
@pytest.mark.asyncio
async def test_async_get_node():
    respx.get(f"{BASE}/library/nodes/coll_org_test_xyz").mock(
        return_value=httpx.Response(
            200,
            json={
                "_id": "coll_org_test_xyz",
                "name": "Revenue",
                "node_kind": "Collection",
                "library_id": "lib_org_test_aaa",
                "tenant_id": "org_test",
                "summary": "Revenue analytics",
            },
        )
    )
    lib = _async_lib()
    node = await lib.get_node("coll_org_test_xyz")
    assert node.id == "coll_org_test_xyz"


# ── zoom (with query) ─────────────────────────────────────────────────────


_ZOOM_RESPONSE = {
    "query": "marketing attribution",
    "library_id": "lib_org_test_aaa",
    "tenant_id": "org_test",
    "embedding_model": "bge-small-en-v1.5@2026-05",
    "focal_nodes": [],
    "subgraph_nodes": [],
    "subgraph_edges": [],
    "stats": {
        "embed_ms": 1, "qdrant_ann_ms": 2, "mongo_traverse_ms": 3,
        "total_ms": 6, "focal_count": 0, "subgraph_node_count": 0,
        "candidates_considered": 0, "budget_used_chars": 0,
        "budget_used_pct": 0, "kind_diversity_rebalance_applied": False,
        "confidence_floor": 0.55, "zoom": 50,
    },
}


@respx.mock
def test_sync_zoom_with_query():
    route = respx.post(f"{BASE}/library/zoom").mock(
        return_value=httpx.Response(200, json=_ZOOM_RESPONSE)
    )
    lib = _sync_lib()
    result = lib.zoom(
        library_id="lib_org_test_aaa", query="marketing attribution", zoom=50,
    )
    assert result.library_id == "lib_org_test_aaa"
    assert result.stats.zoom == 50
    sent = route.calls[0].request.read()
    assert b"marketing attribution" in sent


@respx.mock
@pytest.mark.asyncio
async def test_async_zoom_with_focal_ids():
    """focal_ids variant: zoom skips ANN, goes straight to graph traversal."""
    respx.post(f"{BASE}/library/zoom").mock(
        return_value=httpx.Response(200, json=_ZOOM_RESPONSE)
    )
    lib = _async_lib()
    result = await lib.zoom(
        library_id="lib_org_test_aaa",
        focal_ids=["coll_a", "coll_b"],
        zoom=50,
    )
    assert result.stats.zoom == 50


def test_sync_zoom_requires_query_or_focal_ids():
    lib = _sync_lib()
    with pytest.raises(ValueError, match="query.*focal_ids"):
        lib.zoom(library_id="lib_org_test_aaa")


@pytest.mark.asyncio
async def test_async_zoom_requires_query_or_focal_ids():
    lib = _async_lib()
    with pytest.raises(ValueError, match="query.*focal_ids"):
        await lib.zoom(library_id="lib_org_test_aaa")


# ── record_fact ───────────────────────────────────────────────────────────


@respx.mock
def test_sync_record_fact():
    route = respx.post(f"{BASE}/library/facts").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "fact_org_test_001",
                "name": "Email quality",
                "statement": "email has 12% nulls",
                "fact_kind": "data_quality",
                "source_node_ids": ["src_a"],
                "evidence_refs": [],
                "confidence": 0.95,
                "node_kind": "Fact",
                "library_id": "lib_org_test_aaa",
            },
        )
    )
    lib = _sync_lib()
    result = lib.record_fact(
        library_id="lib_org_test_aaa",
        statement="email has 12% nulls",
        fact_kind="data_quality",
        source_node_ids=["src_a"],
        confidence=0.95,
    )
    assert result.fact_kind == "data_quality"
    assert result.confidence == 0.95
    sent = route.calls[0].request.read()
    assert b'"fact_kind":"data_quality"' in sent


@respx.mock
@pytest.mark.asyncio
async def test_async_record_fact_minimal_inputs():
    """Defaults: fact_kind=contextual_note, no source_node_ids, etc."""
    route = respx.post(f"{BASE}/library/facts").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "fact_org_test_002",
                "name": "note",
                "statement": "just a note",
                "fact_kind": "contextual_note",
                "source_node_ids": [],
                "evidence_refs": [],
                "confidence": 1.0,
                "node_kind": "Fact",
                "library_id": "lib_org_test_aaa",
            },
        )
    )
    lib = _async_lib()
    result = await lib.record_fact(
        library_id="lib_org_test_aaa", statement="just a note"
    )
    assert result.fact_kind == "contextual_note"
    sent = route.calls[0].request.read()
    assert b'"fact_kind":"contextual_note"' in sent


# ── search ────────────────────────────────────────────────────────────────


@respx.mock
def test_sync_search():
    respx.post(f"{BASE}/library/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "query": "revenue",
                "embedding_model": "bge-small-en-v1.5@2026-05",
                "surface": "node_summaries",
                "results": [
                    {"node_id": "coll_1", "score": 0.92,
                     "name": "Revenue", "node_kind": "Collection"},
                ],
            },
        )
    )
    lib = _sync_lib()
    result = lib.search(query="revenue", library_id="lib_org_test_aaa", limit=5)
    assert result.surface == "node_summaries"
    assert len(result.results) == 1
    assert result.results[0].score == 0.92


@respx.mock
@pytest.mark.asyncio
async def test_async_search_with_node_kinds_filter():
    route = respx.post(f"{BASE}/library/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "query": "revenue", "embedding_model": "x",
                "surface": "node_summaries", "results": [],
            },
        )
    )
    lib = _async_lib()
    await lib.search(
        query="revenue",
        library_id="lib_org_test_aaa",
        node_kinds=["Collection", "SourceStub"],
    )
    sent = route.calls[0].request.read()
    assert b"Collection" in sent
    assert b"SourceStub" in sent


# ── backfill ──────────────────────────────────────────────────────────────


@respx.mock
def test_sync_backfill():
    route = respx.post(f"{BASE}/library/backfill").mock(
        return_value=httpx.Response(
            200,
            json={
                "library_id": "lib_org_test_aaa",
                "tenant_id": "org_test",
                "counts": {"connectors": 2, "sources": 5, "views": 1,
                           "series": 15, "skipped": 0},
            },
        )
    )
    lib = _sync_lib()
    result = lib.backfill(library_id="lib_org_test_aaa", include_series=True)
    assert result.counts["sources"] == 5
    sent = route.calls[0].request.read()
    assert b'"include_series":true' in sent


@respx.mock
@pytest.mark.asyncio
async def test_async_backfill_without_series():
    route = respx.post(f"{BASE}/library/backfill").mock(
        return_value=httpx.Response(
            200,
            json={
                "library_id": "lib_org_test_aaa",
                "tenant_id": "org_test",
                "counts": {"connectors": 2, "sources": 5, "views": 1,
                           "series": 0, "skipped": 0},
            },
        )
    )
    lib = _async_lib()
    result = await lib.backfill(
        library_id="lib_org_test_aaa", include_series=False
    )
    assert result.counts["series"] == 0
    sent = route.calls[0].request.read()
    assert b'"include_series":false' in sent


# ── seed_fixture ──────────────────────────────────────────────────────────


@respx.mock
def test_sync_seed_fixture():
    respx.post(f"{BASE}/library/seed-fixture").mock(
        return_value=httpx.Response(
            200,
            json={
                "library_id": "lib_org_test_aaa",
                "tenant_id": "org_test",
                "fixture": "demo-acme",
                "counts": {"collections": 5, "anchor_questions": 15,
                           "refining_questions": 38, "connectors": 7,
                           "sources": 16, "views": 5, "edges": 60,
                           "legacy_connectors_written": 7,
                           "legacy_sources_written": 16},
            },
        )
    )
    lib = _sync_lib()
    result = lib.seed_fixture(
        library_id="lib_org_test_aaa", fixture="demo-acme",
    )
    assert result.fixture == "demo-acme"
    assert result.counts["collections"] == 5


# ── health ────────────────────────────────────────────────────────────────


@respx.mock
def test_sync_health():
    respx.get(f"{BASE}/library/health").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "ok",
                "tenant_id": "org_test",
                "library_graph_doc_count": 42,
                "embedding_model": "bge-small-en-v1.5@2026-05",
            },
        )
    )
    lib = _sync_lib()
    result = lib.health()
    assert result.status == "ok"
    assert result.library_graph_doc_count == 42


@respx.mock
@pytest.mark.asyncio
async def test_async_health():
    respx.get(f"{BASE}/library/health").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "ok",
                "tenant_id": "org_test",
                "library_graph_doc_count": 42,
                "embedding_model": "bge-small-en-v1.5@2026-05",
            },
        )
    )
    lib = _async_lib()
    result = await lib.health()
    assert result.status == "ok"


# ── Parity CI gate ────────────────────────────────────────────────────────


def test_library_async_surface_parity():
    """For every public method on Library, there's a matching async method
    on AsyncLibrary with the same name.

    Catches the regression where someone adds a new sync method without its
    async sibling (or vice versa). The SDK PROJECT.md mandate requires
    sync+async parity on every resource method.
    """
    sync_methods = {
        name for name in dir(Library)
        if not name.startswith("_") and callable(getattr(Library, name))
    }
    async_methods = {
        name for name in dir(AsyncLibrary)
        if not name.startswith("_") and callable(getattr(AsyncLibrary, name))
    }
    sync_only = sync_methods - async_methods
    async_only = async_methods - sync_methods
    assert not sync_only, (
        f"These Library methods have no AsyncLibrary sibling: "
        f"{sorted(sync_only)}. Add async variants to maintain parity."
    )
    assert not async_only, (
        f"These AsyncLibrary methods have no Library sibling: "
        f"{sorted(async_only)}. Add sync variants to maintain parity."
    )
