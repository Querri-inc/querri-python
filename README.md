# Querri — Python SDK and CLI

> **CLI:** Interact with the Querri data analysis platform from the terminal or in scripts.
> **Python SDK:** Embed Querri analytics in your Python web application with one method call.

## Install

```bash
pip install querri
```

---

## CLI Quick Start

The `querri` CLI lets you upload data, create analysis projects, and ask questions — interactively or from scripts.

### Auth

```bash
querri auth login          # browser-based login
querri whoami              # confirm who you're logged in as
```

For scripted/non-interactive use, set `QUERRI_API_KEY` instead of relying on stored tokens:

```bash
export QUERRI_API_KEY=qk_your_api_key
export QUERRI_ORG_ID=org_your_org_id
```

### Example workflow: upload a file and analyze it

```bash
# Upload a file (CSV, Excel, JSON, etc.)
querri --json file upload path/to/data.csv

# Create a project
querri --json project new "My Analysis"

# Add the file to the project (triggers ingestion + agent summary)
querri --json project add-source <file_id>

# Ask a question
querri --json project chat -m "What are the top 5 products by revenue?"
```

For scripting, add `--no-interactive` to prevent prompts and `--json` for parseable output. Note that `--json` and other global flags must come **before** the subcommand:

```bash
querri --json --no-interactive project chat -m "Summarize the data"   # correct
querri project chat -m "Summarize the data" --json                    # WRONG
```

### Self-documenting

The CLI covers all Querri resources — projects, files, sources, views, dashboards, sharing, API keys, users, policies, embed sessions, and more.

```bash
querri --help
querri <command> --help
```

See [`skills/querri-cli/SKILL.md`](skills/querri-cli/SKILL.md) for the full command reference.

---

## Python SDK

For embedding Querri analytics in a Python web application. Use alongside the [`@querri-inc/embed`](https://www.npmjs.com/package/@querri-inc/embed) frontend component.

### Quick Start

```python
from querri import Querri

client = Querri(api_key="qk_your_api_key", org_id="org_...")

session = client.embed.get_session(
    user="customer-42",  # external ID from your system
    ttl=3600,
)

print(session["session_token"])  # JWT to pass to the frontend
```

### Wire a session endpoint

**Flask:**

```python
from flask import Flask, jsonify, request
from querri import Querri

app = Flask(__name__)
client = Querri()  # reads QUERRI_API_KEY and QUERRI_ORG_ID from env

@app.route("/api/querri-session", methods=["POST"])
def querri_session():
    # Derive user identity from YOUR auth system — never from the request body.
    auth_user = get_authenticated_user()

    session = client.embed.get_session(
        user={"external_id": auth_user.id, "email": auth_user.email},
        access={
            "sources": ["src_sales_data"],
            "filters": {"tenant_id": auth_user.tenant_id},
        },
        origin=request.headers.get("Origin"),
        ttl=3600,
    )
    return jsonify(session)
```

Django and FastAPI follow the identical pattern — see **[docs/server-sdk.md](docs/server-sdk.md)** for those examples.

### Add the embed (React)

```tsx
import { QuerriEmbed } from '@querri-inc/embed/react';

<QuerriEmbed
  style={{ width: '100%', height: '600px' }}
  serverUrl="https://app.querri.com"
  auth={{ sessionEndpoint: '/api/querri-session' }}
/>
```

> **Security:** Always derive user identity and access from server-side auth. Never read `user` or `access` from the request body — a malicious client can impersonate any user or escalate access.

### Configuration

The SDK reads configuration from constructor arguments or environment variables:

| Parameter | Env Variable | Default | Description |
|-----------|-------------|---------|-------------|
| `api_key` | `QUERRI_API_KEY` | *(required)* | Your `qk_` API key |
| `org_id` | `QUERRI_ORG_ID` | *(required)* | Organization ID |
| `host` | `QUERRI_HOST` | `https://app.querri.com` | Server host |
| `timeout` | `QUERRI_TIMEOUT` | `30.0` | Request timeout (seconds) |
| `max_retries` | `QUERRI_MAX_RETRIES` | `3` | Retry attempts for transient errors |

> **Note:** The parameter is `host`, not `base_url`. The SDK appends `/api/v1` automatically.

### `get_session()` — Embed Sessions

The flagship convenience method: resolves or creates a user, applies access policies, and generates a session JWT in one call.

```python
session = client.embed.get_session(
    user={
        "external_id": "customer-42",
        "email": "alice@acme.com",
        "first_name": "Alice",
    },
    access={
        "sources": ["src_sales_data"],
        "filters": {
            "tenant_id": "acme",
            "region": ["us-east", "us-west"],  # list values are OR'd
        },
    },
    origin="https://app.acme.com",
    ttl=7200,
)

session["session_token"]  # str — JWT for the embed
session["expires_in"]     # int — seconds until expiry
session["user_id"]        # str — Querri user ID
```

You can also pass pre-created policy IDs directly:

```python
session = client.embed.get_session(
    user={"external_id": "customer-42"},
    access={"policy_ids": ["pol_abc123"]},
)
```

### User-Scoped Client (`as_user`)

```python
session = client.embed.get_session(user="customer-42", ttl=900)

with client.as_user(session) as user_client:
    for project in user_client.projects.list():
        print(project.name)
```

See **[docs/server-sdk.md](docs/server-sdk.md#user-scoped-client-as_user)** for details on granting access and available resources.

### All Resources

| Resource | Access | Key Methods |
|----------|--------|-------------|
| `client.dashboards` | Dashboard management | `list`, `create`, `get`, `update`, `delete`, `refresh` |
| `client.projects` | Analysis projects | `list`, `create`, `get`, `run`, `run_status`, `list_steps` |
| `client.projects.chats` | Chats within projects | `create`, `list`, `stream`, `cancel`, `delete` |
| `client.sources` | Sources, connectors & data | `list`, `create`, `create_data_source`, `query`, `source_data`, `append_rows`, `replace_data`, `ask`, `sync`, `list_connectors` |
| `client.views` | SQL-defined views | `list`, `create`, `get`, `update`, `delete`, `run`, `preview`, `chat` |
| `client.files` | File management | `upload`, `list`, `get`, `delete` |
| `client.users` | User management | `list`, `create`, `get`, `update`, `delete` |
| `client.keys` | API key management | `create`, `list`, `get`, `delete` |
| `client.audit` | Audit log | `list` |
| `client.usage` | Usage metrics | `org_usage`, `user_usage` |
| `client.sharing` | Sharing & permissions | `share_project`, `share_dashboard`, `share_source` |

### Async Client

`AsyncQuerri` mirrors the sync API with `async`/`await`:

```python
from querri import AsyncQuerri

async with AsyncQuerri() as client:
    session = await client.embed.get_session(
        user={"external_id": "cust-42", "email": "a@b.com"},
        access={"sources": ["src_sales"]},
    )
```

### Error Handling

All errors extend `QuerriError`:

```
QuerriError
├── APIError                — HTTP error responses
│   ├── ValidationError     — 400
│   ├── AuthenticationError — 401
│   ├── PermissionError     — 403
│   ├── NotFoundError       — 404
│   ├── ConflictError       — 409
│   ├── RateLimitError      — 429 (auto-retried)
│   └── ServerError         — 5xx (auto-retried)
├── StreamError             — SSE stream issues
└── ConfigError             — missing/invalid configuration
```

The SDK automatically retries **429** (always) and **5xx** (idempotent methods only) with exponential backoff + jitter.

### Full Reference

See **[docs/server-sdk.md](docs/server-sdk.md)** for complete method signatures, all framework examples, and the `get_session()` deep dive.

---

## Requirements

- Python 3.9+
- [`httpx`](https://www.python-httpx.org/) >= 0.27
- [`pydantic`](https://docs.pydantic.dev/) >= 2.0

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
pytest tests/test_integration.py -m integration -v  # requires API credentials
```

## License

MIT
