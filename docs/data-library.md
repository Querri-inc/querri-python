# Data Library — CLI + SDK reference

The Data Library is Querri's knowledge-graph + semantic-search layer over Collections, Questions, Sources, Views, KPIs, and Facts. The `querri library` CLI subcommand + `client.library` SDK resource expose the full surface.

This doc is the user-facing reference. For module-level architecture see [`~/Q/Querri/server-api/querri_core/library/MODULE.md`](https://github.com/Querri-inc/server-api/blob/feat/data-overview/server-api/querri_core/library/MODULE.md) and the program-level [`documentation/data-library/`](https://github.com/Querri-inc/server-api/tree/feat/data-overview/documentation/data-library).

## Auth + setup

```bash
export QUERRI_API_KEY=qk_...
export QUERRI_ORG_ID=<tenant-id>      # required for API-key auth
export QUERRI_HOST=http://localhost   # dev; production defaults to https://app.querri.com
```

Most commands take `--library-id` explicitly. To save typing, set an active library once and subsequent commands pick it up:

```bash
querri library use lib_<tenant-id>_<uuid>
```

The active library is stored in `~/.querri/library_context.json`. Override per-call with `--library-id` or `QUERRI_LIBRARY_ID`.

## Quick start — the demo path

```bash
# 1. Create a library and select it.
querri library create-library "Primary Library"
querri library use <library-id-printed-above>

# 2. Seed it with realistic demo data (5 collections, 16 sources, ~150 series).
querri library seed-demo --fixture demo-acme

# 3. Inspect.
querri library status
querri library list Collection
querri library list ViewStub

# 4. Search semantically.
querri library search "customer churn signals"
querri library zoom "marketing attribution by channel" --zoom 50 --explain

# 5. Chat with the Librarian agent.
querri library chat "What collections relate to revenue?" --new --show-tools

# 6. Record a Fact (CLI-direct OR via the agent).
querri library record-fact \
  "orders.status enum gained 'awaiting_carrier' in Mar 2026" \
  --attach <source-node-id> --kind data_quality

# 7. Have the agent commission a new view.
querri library chat \
  "Commission a view called orders_by_country that sums total_amount grouped by shipping_country, using the orders source. Build it." \
  --show-tools
```

## CLI reference

All commands accept `--json` (a top-level flag, e.g. `querri --json library status`) for scripting.

### Workspace state

| Command | What it does |
|---|---|
| `querri library use <library-id>` | Set active library (persists across invocations). |
| `querri library status [--library-id <id>]` | Counts per node_kind + tenant + total. |
| `querri library health` | Tenant-scoped health probe (Mongo doc count, embedding model). |

### Create

| Command | What it does |
|---|---|
| `querri library create-library <name> [--summary <s>]` | New `Library` node. |
| `querri library create-collection <name> [--anchor "<text>"] [--summary <s>]` | New `Collection`. With `--anchor` also mints an `AnchorQuestion` + the `anchor_of` edge in one call. |
| `querri library create-question <text> [--refining] [--name <n>]` | Anchor question by default; pass `--refining` for a `RefiningQuestion`. |
| `querri library add-refining <anchor-id> "<text>"` | New `RefiningQuestion` linked to the anchor via `refines`. |
| `querri library link <a> <b> <relation> [--weight X] [--confidence X]` | Bidirectional edge between two existing nodes. `<relation>` is one of `contains`, `anchor_of`, `refines`, `parent_of`, `in_category`, `uses_source`, `uses_view`, `connector_provides`, `view_built_from`, `series_in`, `about`, `semantic_neighbor`, `mentions`. |

### Read

| Command | What it does |
|---|---|
| `querri library get <node-id>` | Fetch a single node by id. |
| `querri library list <node-kind> [--limit N]` | All nodes of a given kind in the active library. |
| `querri library search <query> [--kind K] [--limit N] [--surface S]` | Vector ANN search — flat top-K, no graph traversal. Fast surface. |
| `querri library zoom <query> [--zoom N] [--budget N] [--top-k N] [--threshold X] [--kind K] [--explain]` | Vector-seeded multi-focal graph zoom: ANN-resolves focals, BFS up to 2 hops, scores by `edge.confidence × edge.weight × (zoom/100)^hops`. `--explain` prints per-stage latency + algorithm decisions. |
| `querri library zoom --focal <id> [--focal <id>] [--zoom N]` | Skip ANN; zoom directly from given focal IDs (for iterative drill-in). |

### Write — facts + view commissioning

| Command | What it does |
|---|---|
| `querri library record-fact "<statement>" --attach <node-id> [--attach <id>] [--kind <K>] [--evidence <url>] [--confidence X]` | Create a `Fact` node + `about` edges to each `--attach` target. `--kind` is one of `contextual_note` (default), `data_quality`, `timing`, `scope_constraint`. |
| `querri library view-rename <view-stub-id> [--name "<name>"] [--display-name "<title>"] [--summary "<text>"]` | Rename / re-describe a view across BOTH its layers — the graph ViewStub (re-embedded for search/routing) and the legacy source doc the Sources tab renders. `--display-name` defaults to a sentence-cased `--name` (`revenue_by_channel` → `Revenue by channel`). SDK: `client.library.rename_view(...)`. |
| `querri library chat "<message>" [--new] [--chat-id <id>] [--show-tools]` | Streaming chat with the LibrarianAgent. Three tools available to the agent: `search_graph`, `record_fact`, `commission_view`. `--show-tools` prints tool calls + Views-agent progress dots in real time. Active chat id persists per-library so subsequent calls continue the same conversation; `--new` starts fresh. |

### Bulk / admin

| Command | What it does |
|---|---|
| `querri library seed-demo [--fixture <name>]` | Apply a named demo fixture (currently: `demo-acme`). Writes both library_graph stubs AND real legacy `sources` + `connectors` docs so the Views agent can resolve fixture sources. Idempotent. |
| `querri library backfill [--library-id <id>] [--no-series]` | Walk the tenant's existing `connectors` + `sources` collections and create matching stubs in `library_graph`. Idempotent. |

## SDK reference

Sync (`client.library`) and async (`client.library` on `AsyncQuerri`) have identical surfaces.

```python
from querri import Querri

client = Querri(api_key="qk_...", org_id="<tenant>", host="http://localhost")

# Workspace
status = client.library.status(library_id="lib_...")
print(status.counts_by_kind)            # {"Collection": 8, "Fact": 4, ...}

# Search
hits = client.library.search(query="churn risk", library_id="lib_...", limit=5)
for h in hits.results:
    print(h.score, h.node_kind, h.name)

# Vector-seeded graph zoom
zoom = client.library.zoom(
    library_id="lib_...",
    query="channel attribution and ROI",
    zoom=50, budget_tokens=2000, top_k_focal=4,
)
for f in zoom.focal_nodes:
    print(f.score, f.confidence_tier, f.node_kind, f.name)
for n in zoom.subgraph_nodes:
    print(n.edge_strength, n.hops, "/".join(n.edge_path), n.name)

# Record a fact via the API directly
fact = client.library.record_fact(
    library_id="lib_...",
    statement="orders.status enum gained 'awaiting_carrier' in Mar 2026",
    fact_kind="data_quality",
    source_node_ids=["src_..."],
    evidence_refs=["https://runbooks/orders-status-evolution"],
    confidence=0.95,
)

# Chat — drained ChatResponse
result = client.library.chat(
    library_id="lib_...",
    message="What collections relate to revenue?",
    chat_id=None,                       # omit to start fresh
)
print(result.assistant_message)
print(result.tool_calls)                # list of {name, input, result, duration_ms}

# Chat — streaming events (sync iterator)
for event in client.library.chat_stream(
    library_id="lib_...",
    message="Commission a payment_failures view from the payments source",
):
    print(event["type"], event.get("name") or event.get("text", "")[:80])
```

### Streaming event types

The chat stream yields these `type`s (in order, typically):

| Type | Payload |
|---|---|
| `tool_use` | `{tool_use_id, name, input}` — emitted right before each tool call |
| `tool_progress` | `{tool_use_id, raw}` — pass-through inner-agent SSE chunks during `commission_view` |
| `tool_result` | `{tool_use_id, name, input, result, duration_ms}` |
| `assistant_text` | `{text}` — terminal LLM text in the final turn |
| `done` | `{chat_id, library_id, assistant_message, turns_used, stop_reason, input_tokens, output_tokens, total_ms}` |
| `error` | `{message}` — stream-level failure |

## Scopes

Library routes require API-key scopes:

| Scope | Routes |
|---|---|
| `admin:library:read` | GET `/library/nodes`, `/library/nodes/{id}`, `/library/status`, `/library/health`, POST `/library/search`, `/library/zoom` |
| `admin:library:write` | POST `/library/libraries`, `/library/collections`, `/library/questions/*`, `/library/edges`, `/library/facts`, `/library/backfill`, `/library/seed-fixture`, `/library/chat` |

The wildcard `*` superadmin scope satisfies both. JWT auth gives both scopes to `member` role.
