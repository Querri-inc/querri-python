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


class Provenance(_LibraryBase):
    path: list[str] = []


class SearchHit(_LibraryBase):
    node_id: str
    score: float
    # SPEC §5.2: adjacency_score == score for flat ANN, decays for graph
    # traversal. confidence_tier is the display-side bucket.
    adjacency_score: float | None = None
    confidence_tier: str | None = None
    provenance: Provenance | None = None
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


class IntakeResponse(_LibraryBase):
    library_id: str
    tenant_id: str
    structure: dict[str, int] = {}
    link: dict[str, int] = {}


class EvalResponse(_LibraryBase):
    library_id: str
    tenant_id: str
    routing: dict = {}


class AskResponse(_LibraryBase):
    library_id: str
    tenant_id: str
    question: str
    declined: bool
    answer: str
    outcome: str = ""
    provenance: dict | None = None
    attempted: dict | None = None  # surfaced on decline: source + attempted_sql
    total_rows: int = 0
    data: list = []


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
    # library_id + node_kind are present on /nodes + /collections responses
    # but absent on /libraries (which lists across the tenant, not within a
    # specific library). Optional so the same model serves all three.
    library_id: str | None = None
    node_kind: str | None = None
    tenant_id: str | None = None
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


class EdgeStrengthFactors(_LibraryBase):
    semantic_affinity: float = 0.0
    base_confidence: float = 1.0
    distance_decay: float = 1.0


class ZoomSubgraphNode(_LibraryBase):
    node_id: str
    name: str = ""
    node_kind: str = ""
    summary: str = ""
    from_focal: str = ""
    edge_path: list[str] = []
    hops: int = 0
    edge_strength: float = 0.0
    edge_strength_factors: EdgeStrengthFactors | None = None


class ZoomSubgraphEdge(_LibraryBase):
    from_: str = ""
    to: str = ""
    relation: str = ""
    weight: float = 1.0
    confidence: float = 1.0
    source: str = ""
    frequency_count: int = 0
    salience_score: float = 0.0
    created_at: str = ""

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


class ChatToolCall(_LibraryBase):
    name: str
    input: dict[str, Any]
    result: dict[str, Any]
    duration_ms: int


class ChatResponse(_LibraryBase):
    chat_id: str
    library_id: str
    assistant_message: str
    tool_calls: list[ChatToolCall] = []
    turns_used: int = 0
    stop_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_ms: int = 0


class FactResponse(_LibraryBase):
    id: str
    name: str
    statement: str
    fact_kind: str
    source_node_ids: list[str] = []
    evidence_refs: list[str] = []
    confidence: float = 1.0
    node_kind: str = "Fact"
    library_id: str


class ZoomResponse(_LibraryBase):
    query: str = ""
    library_id: str
    tenant_id: str
    embedding_model: str = ""
    focal_nodes: list[ZoomFocalNode] = []
    subgraph_nodes: list[ZoomSubgraphNode] = []
    subgraph_edges: list[dict[str, Any]] = []  # raw — `from` is reserved
    stats: ZoomStats


class LibraryNodeEdge(_LibraryBase):
    """Outbound edge on a LibraryNode. Mirrors the server-side `Edge`
    model. `from` is implicitly the node carrying this edge."""
    to: str
    relation: str
    weight: float = 1.0
    confidence: float = 1.0
    source: str = ""
    frequency_count: int = 0
    salience_score: float = 0.0
    created_at: str = ""


class LibraryNode(_LibraryBase):
    # Permissive — we don't enforce every kind-specific field server-side
    # carries; callers who need typed access to (e.g.) KPI.measurement
    # should reach into `extra` until the codegen pass lands.
    id: str
    name: str
    node_kind: str
    library_id: str
    tenant_id: str
    summary: str = ""
    # Edges are first-class — canvas + agents both need them on every
    # get_node hit without rummaging through `extra`.
    edges: list[LibraryNodeEdge] = []

    # Holds ONLY the fields that aren't already on this model — kind-
    # specific stuff like Fact.statement, KPI.measurement, ViewStub.
    # output_schema. Populated by `_node_from_get` via set-difference so
    # we don't duplicate the typed fields on the wire.
    extra: dict[str, Any] = {}
