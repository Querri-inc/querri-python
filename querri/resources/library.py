"""Data Library SDK resource — paired sync (Library) + async (AsyncLibrary).

Maps to /api/library/* endpoints in server-api. Phase-1 surface: create
Library / Collection / AnchorQuestion / RefiningQuestion, get node by id,
semantic search, health probe.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any, TypeVar

from pydantic import BaseModel

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from ..types.library import (
    AskResponse,
    CollectionContents,
    BackfillResponse,
    ChatResponse,
    ConsolidateResponse,
    EvalResponse,
    IntakeResponse,
    FactResponse,
    HealthResponse,
    LibraryNode,
    LibraryNodeSummary,
    LinkResponse,
    NodeListResponse,
    SearchHit,
    SearchResponse,
    SeedFixtureResponse,
    StatusResponse,
    ZoomResponse,
)


_LIBRARY_NODE_TYPED_FIELDS = frozenset({
    "_id", "id", "name", "node_kind", "library_id", "tenant_id",
    "summary", "edges",
})


def _node_from_get(payload: dict[str, Any]) -> LibraryNode:
    # `extra` carries ONLY the kind-specific + system fields that aren't
    # already first-class on LibraryNode. Pre-fix the SDK stuffed the
    # ENTIRE payload into `extra`, duplicating every typed field — caught
    # in the 2026-05-24 CLI sweep.
    extra = {k: v for k, v in payload.items() if k not in _LIBRARY_NODE_TYPED_FIELDS}
    return LibraryNode(
        id=payload.get("_id") or payload.get("id", ""),
        name=payload.get("name", ""),
        node_kind=payload.get("node_kind", ""),
        library_id=payload.get("library_id", ""),
        tenant_id=payload.get("tenant_id", ""),
        summary=payload.get("summary", ""),
        edges=payload.get("edges", []),
        extra=extra,
    )


_TModel = TypeVar("_TModel", bound=BaseModel)


def _unwrap_dict(envelope_json: dict[str, Any]) -> dict[str, Any]:
    """Dict-returning sibling of `_unwrap_envelope`. Returns the
    envelope's `data` dict with `library_id` splatted in for parity with
    the typed-model unwrap path. Used by methods that don't have a
    Pydantic response model yet (KPIs, chats).
    """
    data = envelope_json.get("data")
    if not isinstance(data, dict):
        # If it's not wrapped (older endpoint), return as-is — callers
        # using the same key set will still work.
        return envelope_json
    out = {"library_id": envelope_json.get("library_id"), **data}
    return out


def _unwrap_envelope(
    envelope_json: dict[str, Any], model: type[_TModel]
) -> _TModel:
    """Unwrap a SPEC §5.1 server envelope into a flat SDK model instance.

    The wire shape is `{data: {...}, library_id, telemetry, cursor?}`. The
    SDK keeps each response model flat (caller doesn't pay the envelope
    cost) so this helper splats `data` into the model and adds
    `library_id` from the envelope top-level so models like StatusResponse
    that carry a `library_id` field land correctly.

    `model_config = ConfigDict(extra="ignore")` on `_LibraryBase` lets
    telemetry/cursor fall away cleanly when the caller doesn't model them.
    Endpoints whose `data` is a list (paginated routes) get a different
    helper at C2.2 sweep time — pilot is single-object only.
    """
    data = envelope_json.get("data")
    if not isinstance(data, dict):
        raise TypeError(
            f"Envelope `data` is {type(data).__name__}, not dict. "
            "Use a list-aware unwrap for paginated endpoints."
        )
    return model.model_validate({
        "library_id": envelope_json.get("library_id"),
        **data,
    })


class Library:
    """Synchronous Data Library client.

    Usage::

        client = Querri(api_key="qk_...")
        lib = client.library.create_library(name="Primary")
        coll = client.library.create_collection(library_id=lib.id, name="Revenue")
        results = client.library.search(query="last quarter revenue", library_id=lib.id)
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    # ── Create ──────────────────────────────────────────────────────────────

    def create_library(self, *, name: str, summary: str = "") -> LibraryNodeSummary:
        resp = self._http.post(
            "/library/libraries",
            json={"name": name, "summary": summary},
        )
        return LibraryNodeSummary.model_validate(resp.json())

    def create_collection(
        self,
        *,
        library_id: str,
        name: str,
        summary: str = "",
        anchor_question_text: str | None = None,
        anchor_question_name: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "library_id": library_id, "name": name, "summary": summary,
        }
        if anchor_question_text:
            body["anchor_question_text"] = anchor_question_text
            if anchor_question_name:
                body["anchor_question_name"] = anchor_question_name
        resp = self._http.post("/library/collections", json=body)
        return resp.json()

    def create_anchor_question(
        self,
        *,
        library_id: str,
        name: str,
        question_text: str,
        summary: str = "",
        collection_id: str | None = None,
    ) -> LibraryNodeSummary:
        body: dict[str, Any] = {
            "library_id": library_id,
            "name": name,
            "question_text": question_text,
            "summary": summary,
        }
        if collection_id:
            body["collection_id"] = collection_id
        resp = self._http.post("/library/questions/anchor", json=body)
        return LibraryNodeSummary.model_validate(resp.json())

    def create_refining_question(
        self,
        *,
        library_id: str,
        name: str,
        question_text: str,
        summary: str = "",
        anchor_question_id: str | None = None,
        collection_id: str | None = None,
    ) -> LibraryNodeSummary:
        body: dict[str, Any] = {
            "library_id": library_id,
            "name": name,
            "question_text": question_text,
            "summary": summary,
        }
        if anchor_question_id:
            body["anchor_question_id"] = anchor_question_id
        if collection_id:
            body["collection_id"] = collection_id
        resp = self._http.post("/library/questions/refining", json=body)
        return LibraryNodeSummary.model_validate(resp.json())

    def link(
        self,
        *,
        a_id: str,
        b_id: str,
        relation: str,
        weight: float = 1.0,
        confidence: float = 1.0,
    ) -> LinkResponse:
        resp = self._http.post(
            "/library/edges",
            json={
                "a_id": a_id, "b_id": b_id, "relation": relation,
                "weight": weight, "confidence": confidence,
            },
        )
        return LinkResponse.model_validate(resp.json())

    def status(self, *, library_id: str) -> StatusResponse:
        # WS-C2.1 pilot: server returns SPEC §5.1 envelope `{data, library_id,
        # telemetry}`. Unwrap to keep the caller-facing StatusResponse flat
        # (`.counts_by_kind`, `.total_nodes`, `.tenant_id`, `.library_id`).
        resp = self._http.get(
            f"/library/status?library_id={library_id}"
        )
        return _unwrap_envelope(resp.json(), StatusResponse)

    def list_nodes(
        self, *, library_id: str, node_kind: str, limit: int = 100
    ) -> NodeListResponse:
        resp = self._http.get(
            f"/library/nodes?library_id={library_id}"
            f"&node_kind={node_kind}&limit={limit}"
        )
        return _unwrap_envelope(resp.json(), NodeListResponse)

    def list_libraries(self, *, limit: int = 100) -> NodeListResponse:
        resp = self._http.get(f"/library/libraries?limit={limit}")
        return _unwrap_envelope(resp.json(), NodeListResponse)

    def list_collections(
        self, *, library_id: str, limit: int = 100
    ) -> NodeListResponse:
        resp = self._http.get(
            f"/library/collections?library_id={library_id}&limit={limit}"
        )
        return _unwrap_envelope(resp.json(), NodeListResponse)

    def seed_fixture(
        self, *, library_id: str, fixture: str,
        seed: int | None = None, scale: str | None = None,
    ) -> SeedFixtureResponse:
        body: dict = {"library_id": library_id, "fixture": fixture}
        if seed is not None:
            body["seed"] = seed
        if scale is not None:
            body["scale"] = scale
        resp = self._http.post("/library/seed-fixture", json=body)
        return SeedFixtureResponse.model_validate(resp.json())

    def zoom(
        self,
        *,
        library_id: str,
        query: str | None = None,
        focal_ids: list[str] | None = None,
        zoom: int = 25,
        budget_tokens: int = 2000,
        top_k_focal: int = 5,
        confidence_floor: float = 0.55,
        node_kinds: list[str] | None = None,
    ) -> ZoomResponse:
        if query is None and not focal_ids:
            raise ValueError("Provide `query` or `focal_ids`.")
        body: dict[str, Any] = {
            "library_id": library_id,
            "zoom": zoom,
            "budget_tokens": budget_tokens,
            "top_k_focal": top_k_focal,
            "confidence_floor": confidence_floor,
        }
        if query is not None:
            body["query"] = query
        if focal_ids:
            body["focal_ids"] = focal_ids
        if node_kinds:
            body["node_kinds"] = node_kinds
        resp = self._http.post("/library/zoom", json=body)
        return _unwrap_envelope(resp.json(), ZoomResponse)

    def record_fact(
        self,
        *,
        library_id: str,
        statement: str,
        fact_kind: str = "contextual_note",
        source_node_ids: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        confidence: float = 1.0,
        name: str | None = None,
    ) -> FactResponse:
        body: dict[str, Any] = {
            "library_id": library_id,
            "statement": statement,
            "fact_kind": fact_kind,
            "source_node_ids": source_node_ids or [],
            "evidence_refs": evidence_refs or [],
            "confidence": confidence,
        }
        if name:
            body["name"] = name
        resp = self._http.post("/library/facts", json=body)
        return FactResponse.model_validate(resp.json())

    def chat_stream(
        self,
        *,
        library_id: str,
        message: str,
        chat_id: str | None = None,
        mode: str = "default",
    ) -> Iterator[dict[str, Any]]:
        """Stream LibrarianAgent events. Yields parsed event dicts as they
        arrive — typically `tool_use`, `tool_progress`, `tool_result`,
        `assistant_text`, and finally `done`.

        `mode="onboarding"` pins the W01 onboarding-mode system prompt +
        tool palette on the server side (Phase 3).
        """
        body: dict[str, Any] = {
            "library_id": library_id,
            "message": message,
            "mode": mode,
        }
        if chat_id:
            body["chat_id"] = chat_id
        # httpx.Client.stream is a context manager; yield from inside it.
        with self._http._client.stream(  # type: ignore[attr-defined]
            "POST", "/library/chat", json=body
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    break
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    continue

    def create_kpi(
        self,
        *,
        library_id: str,
        name: str,
        canonical_name: str = "",
        categories: list[str] | None = None,
        summary: str = "",
        state: str = "draft",
        parent_kpis: list[str] | None = None,
        measurement: dict | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "library_id": library_id,
            "name": name,
            "canonical_name": canonical_name,
            "categories": categories or [],
            "summary": summary,
            "state": state,
            "parent_kpis": parent_kpis or [],
        }
        if measurement is not None:
            body["measurement"] = measurement
        resp = self._http.post("/library/kpis", json=body)
        return resp.json()

    def list_kpis(self, *, library_id: str, limit: int = 100) -> dict[str, Any]:
        resp = self._http.get(f"/library/kpis?library_id={library_id}&limit={limit}")
        return _unwrap_dict(resp.json())

    def get_kpi(self, kpi_id: str) -> dict[str, Any]:
        # GET /kpis/{id} is the convenience alias for /nodes/{id} scoped to
        # KPI kind — it returns the model_dump shape, NOT envelope-wrapped.
        # Kept flat so callers see the same KPI fields as get_node().
        resp = self._http.get(f"/library/kpis/{kpi_id}")
        return resp.json()

    def list_kpi_categories(self, *, library_id: str) -> dict[str, Any]:
        resp = self._http.get(f"/library/kpi-categories?library_id={library_id}")
        return _unwrap_dict(resp.json())

    def list_chats(
        self, *, library_id: str, limit: int = 50
    ) -> dict[str, Any]:
        # Enumerate chats for a library — most-recent first. Each item
        # carries chat_id, message_count, last_user_message_preview,
        # timestamps. Full history via get_chat(chat_id).
        resp = self._http.get(
            f"/library/chats?library_id={library_id}&limit={limit}"
        )
        return _unwrap_dict(resp.json())

    def get_chat(self, chat_id: str) -> dict[str, Any]:
        # Full chat history (every message + tool call) for `chat_id`.
        resp = self._http.get(f"/library/chats/{chat_id}")
        return _unwrap_dict(resp.json())

    def get_onboarding_summary(
        self, *, library_id: str, chat_id: str | None = None
    ) -> dict[str, Any]:
        """Library Built Recap data — five lists (collections, anchor_questions,
        refining_questions, kpis, facts) plus `totals` + `complete`. When
        `chat_id` is provided, only nodes authored in that session are
        included; otherwise the full library view is returned. (Phase 3 W01)
        """
        path = f"/library/onboarding/summary?library_id={library_id}"
        if chat_id:
            path += f"&chat_id={chat_id}"
        resp = self._http.get(path)
        return _unwrap_dict(resp.json())

    def chat(
        self,
        *,
        library_id: str,
        message: str,
        chat_id: str | None = None,
        mode: str = "default",
    ) -> ChatResponse:
        # WS-B6: server now emits VercelStream v2 events. Drain them
        # into ChatResponse:
        #   tool-input-available  → captured by tool_use_id for matching
        #   tool-output-available → folded into tool_calls list with the
        #                           saved input + output
        #   text-delta            → accumulated into assistant_message
        #   data-librarian        → carries chat_id/library_id/turns/
        #                           tokens/total_ms (custom event for
        #                           per-chat metadata Vercel finish doesn't
        #                           model)
        #   finish                → terminal — no payload needed
        tool_inputs: dict[str, dict[str, Any]] = {}
        tool_call_t0: dict[str, float] = {}
        tool_calls: list[dict[str, Any]] = []
        text_chunks: list[str] = []
        meta: dict[str, Any] = {}
        for ev in self.chat_stream(
            library_id=library_id, message=message, chat_id=chat_id, mode=mode
        ):
            etype = ev.get("type", "")
            if etype == "tool-input-available":
                tool_inputs[ev.get("toolCallId", "")] = {
                    "name": ev.get("toolName", ""),
                    "input": ev.get("input", {}),
                }
                tool_call_t0[ev.get("toolCallId", "")] = time.monotonic()
            elif etype == "tool-output-available":
                tcid = ev.get("toolCallId", "")
                meta_in = tool_inputs.get(tcid, {})
                t0 = tool_call_t0.get(tcid, time.monotonic())
                tool_calls.append({
                    "name": meta_in.get("name", ""),
                    "input": meta_in.get("input", {}),
                    "result": ev.get("output", {}),
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                })
            elif etype == "text-delta":
                text_chunks.append(ev.get("delta", ""))
            elif etype == "data-librarian":
                meta = ev.get("data", {})
        return ChatResponse(
            chat_id=meta.get("chat_id", chat_id or ""),
            library_id=meta.get("library_id", library_id),
            assistant_message=meta.get("assistant_message") or "".join(text_chunks),
            tool_calls=tool_calls,  # type: ignore[arg-type]
            turns_used=meta.get("turns_used", 0),
            stop_reason=meta.get("stop_reason", ""),
            input_tokens=meta.get("input_tokens", 0),
            output_tokens=meta.get("output_tokens", 0),
            total_ms=meta.get("total_ms", 0),
        )

    # ── Collection contents + view build (P3c) ────────────────────────────────

    def collection_contents(self, collection_id: str) -> CollectionContents:
        """Batched, name-resolved contents of a Collection — anchor + refining
        questions (each with a tri-state ``answer_state`` + KPIs + answering
        views), the deduped KPI rollup, facts, views, and sources. Server-side
        FGA-filtered. Backs ``querri library collection show``.
        """
        resp = self._http.get(
            f"/library/collections/{collection_id}/contents"
        )
        return _unwrap_envelope(resp.json(), CollectionContents)

    def build_view_stream(
        self,
        *,
        collection_id: str,
        source_node_ids: list[str],
        answers_question_ids: list[str] | None = None,
        name: str | None = None,
        summary: str | None = None,
        instructions: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Stream a headless view build INTO ``collection_id``. Yields parsed
        SSE event dicts (inner Views-agent progress frames, then a terminal
        ``data-view-built`` carrying ``view_uuid`` / ``status`` /
        ``answers_written`` — or ``error`` / ``retryable`` on failure).
        """
        if not source_node_ids:
            raise ValueError("source_node_ids cannot be empty.")
        body: dict[str, Any] = {"source_node_ids": source_node_ids}
        if answers_question_ids:
            body["answers_question_ids"] = answers_question_ids
        if name is not None:
            body["name"] = name
        if summary is not None:
            body["summary"] = summary
        if instructions is not None:
            body["instructions"] = instructions
        with self._http._client.stream(  # type: ignore[attr-defined]
            "POST", f"/library/collections/{collection_id}/views", json=body
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    break
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    continue

    def build_view(
        self,
        *,
        collection_id: str,
        source_node_ids: list[str],
        answers_question_ids: list[str] | None = None,
        name: str | None = None,
        summary: str | None = None,
        instructions: str | None = None,
    ) -> dict[str, Any]:
        """Build a view and drain the stream to its terminal result. Returns the
        ``data-view-built`` payload (``view_uuid`` / ``status`` /
        ``answers_written`` on success, or ``error`` / ``retryable`` on
        failure). Use :meth:`build_view_stream` to surface live progress.
        """
        result: dict[str, Any] = {}
        for ev in self.build_view_stream(
            collection_id=collection_id,
            source_node_ids=source_node_ids,
            answers_question_ids=answers_question_ids,
            name=name,
            summary=summary,
            instructions=instructions,
        ):
            if ev.get("type") == "data-view-built":
                result = ev.get("data", {}) or {}
        return result

    # ── Read ────────────────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> LibraryNode:
        resp = self._http.get(f"/library/nodes/{node_id}")
        return _node_from_get(resp.json())

    def patch_node(
        self, node_id: str, *, name: str | None = None, summary: str | None = None
    ) -> LibraryNode:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if summary is not None:
            body["summary"] = summary
        resp = self._http.request("PATCH", f"/library/nodes/{node_id}", json=body)
        return _node_from_get(resp.json())

    def rename_view(
        self,
        view_stub_id: str,
        *,
        name: str | None = None,
        display_name: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Rename / re-describe a library view across BOTH its layers.

        Unlike :meth:`patch_node` (graph node only), this also syncs the
        legacy source document the Sources tab and preview modal render
        (name + display_name + description), so the two layers can't drift.
        ``display_name`` defaults server-side to a friendly sentence-cased
        form of ``name`` (e.g. ``revenue_by_channel`` → ``Revenue by
        channel``). At least one field is required.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if display_name is not None:
            body["display_name"] = display_name
        if summary is not None:
            body["summary"] = summary
        resp = self._http.request(
            "PATCH", f"/library/views/{view_stub_id}", json=body
        )
        return resp.json()

    def delete_node(self, node_id: str) -> dict[str, Any]:
        resp = self._http.request("DELETE", f"/library/nodes/{node_id}")
        return resp.json()

    # ── Search ──────────────────────────────────────────────────────────────

    def search(
        self,
        *,
        query: str,
        library_id: str,
        limit: int = 20,
        node_kinds: list[str] | None = None,
        surface: str = "node_summaries",
    ) -> SearchResponse:
        body: dict[str, Any] = {
            "query": query,
            "library_id": library_id,
            "limit": limit,
            "surface": surface,
        }
        if node_kinds is not None:
            body["node_kinds"] = node_kinds
        resp = self._http.post("/library/search", json=body)
        return _unwrap_envelope(resp.json(), SearchResponse)

    # ── Backfill ────────────────────────────────────────────────────────────

    def backfill(
        self, *, library_id: str, include_series: bool = True
    ) -> BackfillResponse:
        resp = self._http.post(
            "/library/backfill",
            json={"library_id": library_id, "include_series": include_series},
        )
        return BackfillResponse.model_validate(resp.json())

    def intake(
        self, *, library_id: str, include_series: bool = True,
        stages: list[str] | None = None,
    ) -> IntakeResponse:
        body: dict = {"library_id": library_id, "include_series": include_series}
        if stages is not None:
            body["stages"] = stages
        resp = self._http.post("/library/intake", json=body)
        return IntakeResponse.model_validate(resp.json())

    def eval(
        self, *, library_id: str, routing_only: bool = True
    ) -> EvalResponse:
        resp = self._http.post(
            "/library/eval",
            json={"library_id": library_id, "routing_only": routing_only},
        )
        return EvalResponse.model_validate(resp.json())

    def ask(self, *, library_id: str, question: str) -> AskResponse:
        resp = self._http.post(
            "/library/ask",
            json={"library_id": library_id, "question": question},
        )
        return AskResponse.model_validate(resp.json())

    def consolidate(
        self,
        *,
        library_id: str,
        commit: bool = False,
        question: str | None = None,
        limit: int = 3,
        min_systems: int = 2,
        unify: bool = False,
        replace: bool = False,
    ) -> ConsolidateResponse:
        """Mine the ask log for hard, cross-system metrics. Dry-run by default
        (returns ranked candidates); `commit=True` commissions a unified
        per-channel View + a definition Fact for the top-N. `unify=True` also
        builds the entity-resolved view (one row per resolved product ×
        currency, currencies kept separate)."""
        resp = self._http.post(
            "/library/consolidate",
            json={
                "library_id": library_id, "commit": commit,
                "question": question, "limit": limit, "min_systems": min_systems,
                "unify": unify, "replace": replace,
            },
        )
        return ConsolidateResponse.model_validate(resp.json())

    # ── Health ──────────────────────────────────────────────────────────────

    def health(self) -> HealthResponse:
        resp = self._http.get("/library/health")
        return HealthResponse.model_validate(resp.json())


class AsyncLibrary:
    """Async parallel of :class:`Library`. Identical surface, awaitable methods."""

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create_library(self, *, name: str, summary: str = "") -> LibraryNodeSummary:
        resp = await self._http.post(
            "/library/libraries",
            json={"name": name, "summary": summary},
        )
        return LibraryNodeSummary.model_validate(resp.json())

    async def create_collection(
        self,
        *,
        library_id: str,
        name: str,
        summary: str = "",
        anchor_question_text: str | None = None,
        anchor_question_name: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "library_id": library_id, "name": name, "summary": summary,
        }
        if anchor_question_text:
            body["anchor_question_text"] = anchor_question_text
            if anchor_question_name:
                body["anchor_question_name"] = anchor_question_name
        resp = await self._http.post("/library/collections", json=body)
        return resp.json()

    async def create_anchor_question(
        self,
        *,
        library_id: str,
        name: str,
        question_text: str,
        summary: str = "",
        collection_id: str | None = None,
    ) -> LibraryNodeSummary:
        body: dict[str, Any] = {
            "library_id": library_id,
            "name": name,
            "question_text": question_text,
            "summary": summary,
        }
        if collection_id:
            body["collection_id"] = collection_id
        resp = await self._http.post("/library/questions/anchor", json=body)
        return LibraryNodeSummary.model_validate(resp.json())

    async def create_refining_question(
        self,
        *,
        library_id: str,
        name: str,
        question_text: str,
        summary: str = "",
        anchor_question_id: str | None = None,
        collection_id: str | None = None,
    ) -> LibraryNodeSummary:
        body: dict[str, Any] = {
            "library_id": library_id,
            "name": name,
            "question_text": question_text,
            "summary": summary,
        }
        if anchor_question_id:
            body["anchor_question_id"] = anchor_question_id
        if collection_id:
            body["collection_id"] = collection_id
        resp = await self._http.post("/library/questions/refining", json=body)
        return LibraryNodeSummary.model_validate(resp.json())

    async def link(
        self,
        *,
        a_id: str,
        b_id: str,
        relation: str,
        weight: float = 1.0,
        confidence: float = 1.0,
    ) -> LinkResponse:
        resp = await self._http.post(
            "/library/edges",
            json={
                "a_id": a_id, "b_id": b_id, "relation": relation,
                "weight": weight, "confidence": confidence,
            },
        )
        return LinkResponse.model_validate(resp.json())

    async def status(self, *, library_id: str) -> StatusResponse:
        # WS-C2.1 pilot: see Library.status() for the unwrap rationale.
        resp = await self._http.get(
            f"/library/status?library_id={library_id}"
        )
        return _unwrap_envelope(resp.json(), StatusResponse)

    async def list_nodes(
        self, *, library_id: str, node_kind: str, limit: int = 100
    ) -> NodeListResponse:
        resp = await self._http.get(
            f"/library/nodes?library_id={library_id}"
            f"&node_kind={node_kind}&limit={limit}"
        )
        return _unwrap_envelope(resp.json(), NodeListResponse)

    async def list_libraries(self, *, limit: int = 100) -> NodeListResponse:
        resp = await self._http.get(f"/library/libraries?limit={limit}")
        return _unwrap_envelope(resp.json(), NodeListResponse)

    async def list_collections(
        self, *, library_id: str, limit: int = 100
    ) -> NodeListResponse:
        resp = await self._http.get(
            f"/library/collections?library_id={library_id}&limit={limit}"
        )
        return _unwrap_envelope(resp.json(), NodeListResponse)

    async def seed_fixture(
        self, *, library_id: str, fixture: str,
        seed: int | None = None, scale: str | None = None,
    ) -> SeedFixtureResponse:
        body: dict = {"library_id": library_id, "fixture": fixture}
        if seed is not None:
            body["seed"] = seed
        if scale is not None:
            body["scale"] = scale
        resp = await self._http.post("/library/seed-fixture", json=body)
        return SeedFixtureResponse.model_validate(resp.json())

    async def zoom(
        self,
        *,
        library_id: str,
        query: str | None = None,
        focal_ids: list[str] | None = None,
        zoom: int = 25,
        budget_tokens: int = 2000,
        top_k_focal: int = 5,
        confidence_floor: float = 0.55,
        node_kinds: list[str] | None = None,
    ) -> ZoomResponse:
        if query is None and not focal_ids:
            raise ValueError("Provide `query` or `focal_ids`.")
        body: dict[str, Any] = {
            "library_id": library_id,
            "zoom": zoom,
            "budget_tokens": budget_tokens,
            "top_k_focal": top_k_focal,
            "confidence_floor": confidence_floor,
        }
        if query is not None:
            body["query"] = query
        if focal_ids:
            body["focal_ids"] = focal_ids
        if node_kinds:
            body["node_kinds"] = node_kinds
        resp = await self._http.post("/library/zoom", json=body)
        return _unwrap_envelope(resp.json(), ZoomResponse)

    async def record_fact(
        self,
        *,
        library_id: str,
        statement: str,
        fact_kind: str = "contextual_note",
        source_node_ids: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        confidence: float = 1.0,
        name: str | None = None,
    ) -> FactResponse:
        body: dict[str, Any] = {
            "library_id": library_id,
            "statement": statement,
            "fact_kind": fact_kind,
            "source_node_ids": source_node_ids or [],
            "evidence_refs": evidence_refs or [],
            "confidence": confidence,
        }
        if name:
            body["name"] = name
        resp = await self._http.post("/library/facts", json=body)
        return FactResponse.model_validate(resp.json())

    async def chat_stream(
        self,
        *,
        library_id: str,
        message: str,
        chat_id: str | None = None,
        mode: str = "default",
    ) -> AsyncIterator[dict[str, Any]]:
        body: dict[str, Any] = {
            "library_id": library_id,
            "message": message,
            "mode": mode,
        }
        if chat_id:
            body["chat_id"] = chat_id
        async with self._http._client.stream(  # type: ignore[attr-defined]
            "POST", "/library/chat", json=body
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    break
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    continue

    async def create_kpi(
        self,
        *,
        library_id: str,
        name: str,
        canonical_name: str = "",
        categories: list[str] | None = None,
        summary: str = "",
        state: str = "draft",
        parent_kpis: list[str] | None = None,
        measurement: dict | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "library_id": library_id,
            "name": name,
            "canonical_name": canonical_name,
            "categories": categories or [],
            "summary": summary,
            "state": state,
            "parent_kpis": parent_kpis or [],
        }
        if measurement is not None:
            body["measurement"] = measurement
        resp = await self._http.post("/library/kpis", json=body)
        return resp.json()

    async def list_kpis(self, *, library_id: str, limit: int = 100) -> dict[str, Any]:
        resp = await self._http.get(f"/library/kpis?library_id={library_id}&limit={limit}")
        return _unwrap_dict(resp.json())

    async def get_kpi(self, kpi_id: str) -> dict[str, Any]:
        # See sync get_kpi — alias for /nodes/{id}, returned flat.
        resp = await self._http.get(f"/library/kpis/{kpi_id}")
        return resp.json()

    async def list_kpi_categories(self, *, library_id: str) -> dict[str, Any]:
        resp = await self._http.get(f"/library/kpi-categories?library_id={library_id}")
        return _unwrap_dict(resp.json())

    async def list_chats(
        self, *, library_id: str, limit: int = 50
    ) -> dict[str, Any]:
        resp = await self._http.get(
            f"/library/chats?library_id={library_id}&limit={limit}"
        )
        return _unwrap_dict(resp.json())

    async def get_chat(self, chat_id: str) -> dict[str, Any]:
        resp = await self._http.get(f"/library/chats/{chat_id}")
        return _unwrap_dict(resp.json())

    async def get_onboarding_summary(
        self, *, library_id: str, chat_id: str | None = None
    ) -> dict[str, Any]:
        """Async parallel of :meth:`Library.get_onboarding_summary`."""
        path = f"/library/onboarding/summary?library_id={library_id}"
        if chat_id:
            path += f"&chat_id={chat_id}"
        resp = await self._http.get(path)
        return _unwrap_dict(resp.json())

    async def chat(
        self,
        *,
        library_id: str,
        message: str,
        chat_id: str | None = None,
        mode: str = "default",
    ) -> ChatResponse:
        # WS-B6: mirror the sync drainer — same VercelStream event types,
        # same accumulation logic.
        tool_inputs: dict[str, dict[str, Any]] = {}
        tool_call_t0: dict[str, float] = {}
        tool_calls: list[dict[str, Any]] = []
        text_chunks: list[str] = []
        meta: dict[str, Any] = {}
        async for ev in self.chat_stream(
            library_id=library_id, message=message, chat_id=chat_id, mode=mode
        ):
            etype = ev.get("type", "")
            if etype == "tool-input-available":
                tool_inputs[ev.get("toolCallId", "")] = {
                    "name": ev.get("toolName", ""),
                    "input": ev.get("input", {}),
                }
                tool_call_t0[ev.get("toolCallId", "")] = time.monotonic()
            elif etype == "tool-output-available":
                tcid = ev.get("toolCallId", "")
                meta_in = tool_inputs.get(tcid, {})
                t0 = tool_call_t0.get(tcid, time.monotonic())
                tool_calls.append({
                    "name": meta_in.get("name", ""),
                    "input": meta_in.get("input", {}),
                    "result": ev.get("output", {}),
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                })
            elif etype == "text-delta":
                text_chunks.append(ev.get("delta", ""))
            elif etype == "data-librarian":
                meta = ev.get("data", {})
        return ChatResponse(
            chat_id=meta.get("chat_id", chat_id or ""),
            library_id=meta.get("library_id", library_id),
            assistant_message=meta.get("assistant_message") or "".join(text_chunks),
            tool_calls=tool_calls,  # type: ignore[arg-type]
            turns_used=meta.get("turns_used", 0),
            stop_reason=meta.get("stop_reason", ""),
            input_tokens=meta.get("input_tokens", 0),
            output_tokens=meta.get("output_tokens", 0),
            total_ms=meta.get("total_ms", 0),
        )

    async def collection_contents(self, collection_id: str) -> CollectionContents:
        """Async parallel of :meth:`Library.collection_contents`."""
        resp = await self._http.get(
            f"/library/collections/{collection_id}/contents"
        )
        return _unwrap_envelope(resp.json(), CollectionContents)

    async def build_view_stream(
        self,
        *,
        collection_id: str,
        source_node_ids: list[str],
        answers_question_ids: list[str] | None = None,
        name: str | None = None,
        summary: str | None = None,
        instructions: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async parallel of :meth:`Library.build_view_stream`."""
        if not source_node_ids:
            raise ValueError("source_node_ids cannot be empty.")
        body: dict[str, Any] = {"source_node_ids": source_node_ids}
        if answers_question_ids:
            body["answers_question_ids"] = answers_question_ids
        if name is not None:
            body["name"] = name
        if summary is not None:
            body["summary"] = summary
        if instructions is not None:
            body["instructions"] = instructions
        async with self._http._client.stream(  # type: ignore[attr-defined]
            "POST", f"/library/collections/{collection_id}/views", json=body
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    break
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    continue

    async def build_view(
        self,
        *,
        collection_id: str,
        source_node_ids: list[str],
        answers_question_ids: list[str] | None = None,
        name: str | None = None,
        summary: str | None = None,
        instructions: str | None = None,
    ) -> dict[str, Any]:
        """Async parallel of :meth:`Library.build_view`."""
        result: dict[str, Any] = {}
        async for ev in self.build_view_stream(
            collection_id=collection_id,
            source_node_ids=source_node_ids,
            answers_question_ids=answers_question_ids,
            name=name,
            summary=summary,
            instructions=instructions,
        ):
            if ev.get("type") == "data-view-built":
                result = ev.get("data", {}) or {}
        return result

    async def get_node(self, node_id: str) -> LibraryNode:
        resp = await self._http.get(f"/library/nodes/{node_id}")
        return _node_from_get(resp.json())

    async def patch_node(
        self, node_id: str, *, name: str | None = None, summary: str | None = None
    ) -> LibraryNode:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if summary is not None:
            body["summary"] = summary
        resp = await self._http.request("PATCH", f"/library/nodes/{node_id}", json=body)
        return _node_from_get(resp.json())

    async def rename_view(
        self,
        view_stub_id: str,
        *,
        name: str | None = None,
        display_name: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Rename / re-describe a library view across BOTH its layers.

        See :meth:`LibraryResource.rename_view` for semantics.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if display_name is not None:
            body["display_name"] = display_name
        if summary is not None:
            body["summary"] = summary
        resp = await self._http.request(
            "PATCH", f"/library/views/{view_stub_id}", json=body
        )
        return resp.json()

    async def delete_node(self, node_id: str) -> dict[str, Any]:
        resp = await self._http.request("DELETE", f"/library/nodes/{node_id}")
        return resp.json()

    async def search(
        self,
        *,
        query: str,
        library_id: str,
        limit: int = 20,
        node_kinds: list[str] | None = None,
        surface: str = "node_summaries",
    ) -> SearchResponse:
        body: dict[str, Any] = {
            "query": query,
            "library_id": library_id,
            "limit": limit,
            "surface": surface,
        }
        if node_kinds is not None:
            body["node_kinds"] = node_kinds
        resp = await self._http.post("/library/search", json=body)
        return _unwrap_envelope(resp.json(), SearchResponse)

    async def backfill(
        self, *, library_id: str, include_series: bool = True
    ) -> BackfillResponse:
        resp = await self._http.post(
            "/library/backfill",
            json={"library_id": library_id, "include_series": include_series},
        )
        return BackfillResponse.model_validate(resp.json())

    async def intake(
        self, *, library_id: str, include_series: bool = True,
        stages: list[str] | None = None,
    ) -> IntakeResponse:
        body: dict = {"library_id": library_id, "include_series": include_series}
        if stages is not None:
            body["stages"] = stages
        resp = await self._http.post("/library/intake", json=body)
        return IntakeResponse.model_validate(resp.json())

    async def eval(
        self, *, library_id: str, routing_only: bool = True
    ) -> EvalResponse:
        resp = await self._http.post(
            "/library/eval",
            json={"library_id": library_id, "routing_only": routing_only},
        )
        return EvalResponse.model_validate(resp.json())

    async def ask(self, *, library_id: str, question: str) -> AskResponse:
        resp = await self._http.post(
            "/library/ask",
            json={"library_id": library_id, "question": question},
        )
        return AskResponse.model_validate(resp.json())

    async def consolidate(
        self,
        *,
        library_id: str,
        commit: bool = False,
        question: str | None = None,
        limit: int = 3,
        min_systems: int = 2,
        unify: bool = False,
        replace: bool = False,
    ) -> ConsolidateResponse:
        """Mine the ask log for hard, cross-system metrics. Dry-run by default
        (returns ranked candidates); `commit=True` commissions a unified
        per-channel View + a definition Fact for the top-N. `unify=True` also
        builds the entity-resolved view (one row per resolved product ×
        currency, currencies kept separate)."""
        resp = await self._http.post(
            "/library/consolidate",
            json={
                "library_id": library_id, "commit": commit,
                "question": question, "limit": limit, "min_systems": min_systems,
                "unify": unify, "replace": replace,
            },
        )
        return ConsolidateResponse.model_validate(resp.json())

    async def health(self) -> HealthResponse:
        resp = await self._http.get("/library/health")
        return HealthResponse.model_validate(resp.json())
