"""Data Library SDK resource — paired sync (Library) + async (AsyncLibrary).

Maps to /api/library/* endpoints in server-api. Phase-1 surface: create
Library / Collection / AnchorQuestion / RefiningQuestion, get node by id,
semantic search, health probe.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any, TypeVar

from pydantic import BaseModel

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from ..types.library import (
    BackfillResponse,
    ChatResponse,
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
        return NodeListResponse.model_validate(resp.json())

    def list_libraries(self, *, limit: int = 100) -> NodeListResponse:
        resp = self._http.get(f"/library/libraries?limit={limit}")
        return NodeListResponse.model_validate(resp.json())

    def list_collections(
        self, *, library_id: str, limit: int = 100
    ) -> NodeListResponse:
        resp = self._http.get(
            f"/library/collections?library_id={library_id}&limit={limit}"
        )
        return NodeListResponse.model_validate(resp.json())

    def seed_fixture(
        self, *, library_id: str, fixture: str
    ) -> SeedFixtureResponse:
        resp = self._http.post(
            "/library/seed-fixture",
            json={"library_id": library_id, "fixture": fixture},
        )
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
        return ZoomResponse.model_validate(resp.json())

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
    ) -> Iterator[dict[str, Any]]:
        """Stream LibrarianAgent events. Yields parsed event dicts as they
        arrive — typically `tool_use`, `tool_progress`, `tool_result`,
        `assistant_text`, and finally `done`.
        """
        body: dict[str, Any] = {"library_id": library_id, "message": message}
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
        return resp.json()

    def get_kpi(self, kpi_id: str) -> dict[str, Any]:
        resp = self._http.get(f"/library/kpis/{kpi_id}")
        return resp.json()

    def list_kpi_categories(self, *, library_id: str) -> dict[str, Any]:
        resp = self._http.get(f"/library/kpi-categories?library_id={library_id}")
        return resp.json()

    def list_chats(
        self, *, library_id: str, limit: int = 50
    ) -> dict[str, Any]:
        # Enumerate chats for a library — most-recent first. Each item
        # carries chat_id, message_count, last_user_message_preview,
        # timestamps. Full history via get_chat(chat_id).
        resp = self._http.get(
            f"/library/chats?library_id={library_id}&limit={limit}"
        )
        return resp.json()

    def get_chat(self, chat_id: str) -> dict[str, Any]:
        # Full chat history (every message + tool call) for `chat_id`.
        resp = self._http.get(f"/library/chats/{chat_id}")
        return resp.json()

    def chat(
        self,
        *,
        library_id: str,
        message: str,
        chat_id: str | None = None,
    ) -> ChatResponse:
        # Drain the stream into the legacy ChatResponse shape so callers
        # that don't care about incremental events get a single object.
        tool_calls: list[dict[str, Any]] = []
        final = ChatResponse(
            chat_id=chat_id or "",
            library_id=library_id,
            assistant_message="",
        )
        for ev in self.chat_stream(
            library_id=library_id, message=message, chat_id=chat_id
        ):
            etype = ev.get("type")
            if etype == "tool_result":
                tool_calls.append({
                    "name": ev.get("name", ""),
                    "input": ev.get("input", {}),
                    "result": ev.get("result", {}),
                    "duration_ms": ev.get("duration_ms", 0),
                })
            elif etype == "done":
                final = ChatResponse(
                    chat_id=ev.get("chat_id", chat_id or ""),
                    library_id=ev.get("library_id", library_id),
                    assistant_message=ev.get("assistant_message", ""),
                    tool_calls=tool_calls,  # type: ignore[arg-type]
                    turns_used=ev.get("turns_used", 0),
                    stop_reason=ev.get("stop_reason", ""),
                    input_tokens=ev.get("input_tokens", 0),
                    output_tokens=ev.get("output_tokens", 0),
                    total_ms=ev.get("total_ms", 0),
                )
        return final

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
        return SearchResponse.model_validate(resp.json())

    # ── Backfill ────────────────────────────────────────────────────────────

    def backfill(
        self, *, library_id: str, include_series: bool = True
    ) -> BackfillResponse:
        resp = self._http.post(
            "/library/backfill",
            json={"library_id": library_id, "include_series": include_series},
        )
        return BackfillResponse.model_validate(resp.json())

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
        return NodeListResponse.model_validate(resp.json())

    async def list_libraries(self, *, limit: int = 100) -> NodeListResponse:
        resp = await self._http.get(f"/library/libraries?limit={limit}")
        return NodeListResponse.model_validate(resp.json())

    async def list_collections(
        self, *, library_id: str, limit: int = 100
    ) -> NodeListResponse:
        resp = await self._http.get(
            f"/library/collections?library_id={library_id}&limit={limit}"
        )
        return NodeListResponse.model_validate(resp.json())

    async def seed_fixture(
        self, *, library_id: str, fixture: str
    ) -> SeedFixtureResponse:
        resp = await self._http.post(
            "/library/seed-fixture",
            json={"library_id": library_id, "fixture": fixture},
        )
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
        return ZoomResponse.model_validate(resp.json())

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
    ) -> AsyncIterator[dict[str, Any]]:
        body: dict[str, Any] = {"library_id": library_id, "message": message}
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
        return resp.json()

    async def get_kpi(self, kpi_id: str) -> dict[str, Any]:
        resp = await self._http.get(f"/library/kpis/{kpi_id}")
        return resp.json()

    async def list_kpi_categories(self, *, library_id: str) -> dict[str, Any]:
        resp = await self._http.get(f"/library/kpi-categories?library_id={library_id}")
        return resp.json()

    async def list_chats(
        self, *, library_id: str, limit: int = 50
    ) -> dict[str, Any]:
        resp = await self._http.get(
            f"/library/chats?library_id={library_id}&limit={limit}"
        )
        return resp.json()

    async def get_chat(self, chat_id: str) -> dict[str, Any]:
        resp = await self._http.get(f"/library/chats/{chat_id}")
        return resp.json()

    async def chat(
        self,
        *,
        library_id: str,
        message: str,
        chat_id: str | None = None,
    ) -> ChatResponse:
        tool_calls: list[dict[str, Any]] = []
        final = ChatResponse(
            chat_id=chat_id or "",
            library_id=library_id,
            assistant_message="",
        )
        async for ev in self.chat_stream(
            library_id=library_id, message=message, chat_id=chat_id
        ):
            etype = ev.get("type")
            if etype == "tool_result":
                tool_calls.append({
                    "name": ev.get("name", ""),
                    "input": ev.get("input", {}),
                    "result": ev.get("result", {}),
                    "duration_ms": ev.get("duration_ms", 0),
                })
            elif etype == "done":
                final = ChatResponse(
                    chat_id=ev.get("chat_id", chat_id or ""),
                    library_id=ev.get("library_id", library_id),
                    assistant_message=ev.get("assistant_message", ""),
                    tool_calls=tool_calls,  # type: ignore[arg-type]
                    turns_used=ev.get("turns_used", 0),
                    stop_reason=ev.get("stop_reason", ""),
                    input_tokens=ev.get("input_tokens", 0),
                    output_tokens=ev.get("output_tokens", 0),
                    total_ms=ev.get("total_ms", 0),
                )
        return final

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
        return SearchResponse.model_validate(resp.json())

    async def backfill(
        self, *, library_id: str, include_series: bool = True
    ) -> BackfillResponse:
        resp = await self._http.post(
            "/library/backfill",
            json={"library_id": library_id, "include_series": include_series},
        )
        return BackfillResponse.model_validate(resp.json())

    async def health(self) -> HealthResponse:
        resp = await self._http.get("/library/health")
        return HealthResponse.model_validate(resp.json())
