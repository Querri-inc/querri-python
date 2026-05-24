"""Data Library SDK resource — paired sync (Library) + async (AsyncLibrary).

Maps to /api/library/* endpoints in server-api. Phase-1 surface: create
Library / Collection / AnchorQuestion / RefiningQuestion, get node by id,
semantic search, health probe.
"""

from __future__ import annotations

from typing import Any

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


def _node_from_get(payload: dict[str, Any]) -> LibraryNode:
    return LibraryNode(
        id=payload.get("_id") or payload.get("id", ""),
        name=payload.get("name", ""),
        node_kind=payload.get("node_kind", ""),
        library_id=payload.get("library_id", ""),
        tenant_id=payload.get("tenant_id", ""),
        summary=payload.get("summary", ""),
        extra=payload,
    )


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
        resp = self._http.get(
            f"/library/status?library_id={library_id}"
        )
        return StatusResponse.model_validate(resp.json())

    def list_nodes(
        self, *, library_id: str, node_kind: str, limit: int = 100
    ) -> NodeListResponse:
        resp = self._http.get(
            f"/library/nodes?library_id={library_id}"
            f"&node_kind={node_kind}&limit={limit}"
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

    def chat(
        self,
        *,
        library_id: str,
        message: str,
        chat_id: str | None = None,
    ) -> ChatResponse:
        body: dict[str, Any] = {"library_id": library_id, "message": message}
        if chat_id:
            body["chat_id"] = chat_id
        resp = self._http.post("/library/chat", json=body)
        return ChatResponse.model_validate(resp.json())

    # ── Read ────────────────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> LibraryNode:
        resp = self._http.get(f"/library/nodes/{node_id}")
        return _node_from_get(resp.json())

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
        resp = await self._http.get(
            f"/library/status?library_id={library_id}"
        )
        return StatusResponse.model_validate(resp.json())

    async def list_nodes(
        self, *, library_id: str, node_kind: str, limit: int = 100
    ) -> NodeListResponse:
        resp = await self._http.get(
            f"/library/nodes?library_id={library_id}"
            f"&node_kind={node_kind}&limit={limit}"
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

    async def chat(
        self,
        *,
        library_id: str,
        message: str,
        chat_id: str | None = None,
    ) -> ChatResponse:
        body: dict[str, Any] = {"library_id": library_id, "message": message}
        if chat_id:
            body["chat_id"] = chat_id
        resp = await self._http.post("/library/chat", json=body)
        return ChatResponse.model_validate(resp.json())

    async def get_node(self, node_id: str) -> LibraryNode:
        resp = await self._http.get(f"/library/nodes/{node_id}")
        return _node_from_get(resp.json())

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
