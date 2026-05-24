"""Response types for the Data Library SDK resource.

Phase 1 — minimal envelopes; will be regenerated from OpenAPI in a later
SDK-codegen pass (Task 1.16). For now these are hand-maintained and
deliberately permissive (extra fields ignored on validation).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _LibraryBase(BaseModel):
    model_config = ConfigDict(extra="ignore")


class LibraryNodeSummary(_LibraryBase):
    id: str
    name: str
    node_kind: str
    library_id: str
    summary: str = ""


class SearchHit(_LibraryBase):
    node_id: str
    score: float
    name: str | None = None
    node_kind: str | None = None


class SearchResponse(_LibraryBase):
    query: str
    embedding_model: str
    surface: str
    results: list[SearchHit]


class HealthResponse(_LibraryBase):
    status: str
    tenant_id: str
    library_graph_doc_count: int
    embedding_model: str


class LibraryNode(_LibraryBase):
    # Permissive — we don't enforce every field server-side carries; callers
    # who need typed access to (e.g.) KPI.measurement should reach into the
    # `extra` payload until the codegen pass lands.
    id: str
    name: str
    node_kind: str
    library_id: str
    tenant_id: str
    summary: str = ""

    # Keep the raw payload around for fields we haven't strongly typed yet.
    extra: dict[str, Any] = {}
