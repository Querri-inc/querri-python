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


class BackfillResponse(_LibraryBase):
    library_id: str
    tenant_id: str
    counts: dict[str, int]


class SeedFixtureResponse(_LibraryBase):
    library_id: str
    tenant_id: str
    fixture: str
    counts: dict[str, int]


class StatusResponse(_LibraryBase):
    library_id: str
    tenant_id: str
    counts_by_kind: dict[str, int]
    total_nodes: int


class NodeListItem(_LibraryBase):
    id: str
    name: str
    node_kind: str
    summary: str = ""


class NodeListResponse(_LibraryBase):
    library_id: str
    node_kind: str
    results: list[NodeListItem]


class LinkResponse(_LibraryBase):
    a_id: str
    b_id: str
    relation: str
    tenant_id: str


class ZoomFocalNode(_LibraryBase):
    node_id: str
    score: float
    name: str = ""
    node_kind: str = ""
    summary: str = ""
    confidence_tier: str = ""


class ZoomSubgraphNode(_LibraryBase):
    node_id: str
    name: str = ""
    node_kind: str = ""
    summary: str = ""
    from_focal: str = ""
    edge_path: list[str] = []
    hops: int = 0
    edge_strength: float = 0.0


class ZoomSubgraphEdge(_LibraryBase):
    from_: str = ""
    to: str = ""
    relation: str = ""

    # JSON key is `from` (Python reserved word) — alias the field.
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ZoomStats(_LibraryBase):
    embed_ms: int = 0
    qdrant_ann_ms: int = 0
    mongo_traverse_ms: int = 0
    total_ms: int = 0
    focal_count: int = 0
    subgraph_node_count: int = 0
    candidates_considered: int = 0
    budget_used_chars: int = 0
    budget_used_pct: int = 0
    kind_diversity_rebalance_applied: bool = False
    confidence_floor: float = 0.0
    zoom: int = 0


class ZoomResponse(_LibraryBase):
    query: str = ""
    library_id: str
    tenant_id: str
    embedding_model: str = ""
    focal_nodes: list[ZoomFocalNode] = []
    subgraph_nodes: list[ZoomSubgraphNode] = []
    subgraph_edges: list[dict[str, Any]] = []  # raw — `from` is reserved
    stats: ZoomStats


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
