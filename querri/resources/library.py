"""Data Library SDK resource — paired sync (Library) + async (AsyncLibrary).

Maps to /api/library/* endpoints in server-api. Phase-1 surface: create
Library / Collection / AnchorQuestion / RefiningQuestion, get node by id,
semantic search, health probe.
"""

from __future__ import annotations

from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from ..types.library import (
    HealthResponse,
    LibraryNode,
    LibraryNodeSummary,
    SearchHit,
    SearchResponse,
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
        self, *, library_id: str, name: str, summary: str = ""
    ) -> LibraryNodeSummary:
        resp = self._http.post(
            "/library/collections",
            json={"library_id": library_id, "name": name, "summary": summary},
        )
        return LibraryNodeSummary.model_validate(resp.json())

    def create_anchor_question(
        self,
        *,
        library_id: str,
        name: str,
        question_text: str,
        summary: str = "",
    ) -> LibraryNodeSummary:
        resp = self._http.post(
            "/library/questions/anchor",
            json={
                "library_id": library_id,
                "name": name,
                "question_text": question_text,
                "summary": summary,
            },
        )
        return LibraryNodeSummary.model_validate(resp.json())

    def create_refining_question(
        self,
        *,
        library_id: str,
        name: str,
        question_text: str,
        summary: str = "",
    ) -> LibraryNodeSummary:
        resp = self._http.post(
            "/library/questions/refining",
            json={
                "library_id": library_id,
                "name": name,
                "question_text": question_text,
                "summary": summary,
            },
        )
        return LibraryNodeSummary.model_validate(resp.json())

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
        self, *, library_id: str, name: str, summary: str = ""
    ) -> LibraryNodeSummary:
        resp = await self._http.post(
            "/library/collections",
            json={"library_id": library_id, "name": name, "summary": summary},
        )
        return LibraryNodeSummary.model_validate(resp.json())

    async def create_anchor_question(
        self,
        *,
        library_id: str,
        name: str,
        question_text: str,
        summary: str = "",
    ) -> LibraryNodeSummary:
        resp = await self._http.post(
            "/library/questions/anchor",
            json={
                "library_id": library_id,
                "name": name,
                "question_text": question_text,
                "summary": summary,
            },
        )
        return LibraryNodeSummary.model_validate(resp.json())

    async def create_refining_question(
        self,
        *,
        library_id: str,
        name: str,
        question_text: str,
        summary: str = "",
    ) -> LibraryNodeSummary:
        resp = await self._http.post(
            "/library/questions/refining",
            json={
                "library_id": library_id,
                "name": name,
                "question_text": question_text,
                "summary": summary,
            },
        )
        return LibraryNodeSummary.model_validate(resp.json())

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

    async def health(self) -> HealthResponse:
        resp = await self._http.get("/library/health")
        return HealthResponse.model_validate(resp.json())
