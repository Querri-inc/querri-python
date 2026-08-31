# Querri — Python SDK and CLI

> **CLI:** Interact with the Querri data analysis platform from the terminal or in scripts.
> **Python SDK:** Embed Querri analytics in your Python web application with one method call.

## Install

The package ships in two flavors. Pick based on whether you want the CLI:

```bash
pip install querri          # SDK only (httpx + pydantic)
pip install 'querri[cli]'   # SDK + CLI (adds typer, rich, Pillow)
```

The `querri` command-line tool requires the `[cli]` extra. If you install the bare package and run `querri`, it'll tell you to reinstall with `'querri[cli]'`.

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

For embedding Querri analytics in a Python web application. The backend SDK creates embed sessions; the frontend loads the embed script directly from your Querri server at `{serverUrl}/sdk/querri-embed.js` (a React wrapper is also available — see below).

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

Always forward the request's `Origin` header as shown. If your organization configures an allowlist of embed domains, the server enforces it when the session is created: a missing origin fails with `400 origin_required`, and an origin not on the allowlist fails with `403 origin_not_allowed`. Without an allowlist, `origin` is accepted but not enforced.

### Add the embed (browser)

Load the embed script from your Querri server — it is served at `{serverUrl}/sdk/querri-embed.js` and always matches the server's version:

```html
<div id="querri" style="width: 100%; height: 600px;"></div>
<script src="https://app.querri.com/sdk/querri-embed.js"></script>
<script>
  QuerriEmbed.create(document.getElementById('querri'), {
    serverUrl: 'https://app.querri.com',
    auth: {
      fetchSessionToken: async () => {
        const res = await fetch('/api/querri-session', { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Session failed');
        return data.session_token;
      },
    },
    startView: '/home',
    chrome: { rail: { show: true }, header: { show: true } },
  });
</script>
```

Use the same host for the script tag and `serverUrl`. See [`examples/web-embed/`](examples/web-embed/) for a working page that fetches the server URL from its backend before injecting the script.

### Add the embed (React)

A React wrapper is available (requires `@querri-inc/embed` >= 1.0.0):

```tsx
import { QuerriEmbed } from '@querri-inc/embed/react';

<QuerriEmbed
  style={{ width: '100%', height: '600px' }}
  serverUrl="https://app.querri.com"
  auth={{
    fetchSessionToken: async () => {
      const res = await fetch('/api/querri-session', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Session failed');
      return data.session_token;
    },
  }}
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
| `client.embed` | Embed sessions (flagship) | `get_session`, `create_session`, `refresh_session`, `revoke_session`, `list_sessions`, `get_ui_config` |
| `client.policies` | Row-level access control | `setup`, `create`, `list`, `get`, `update`, `delete`, `assign_users`, `remove_user`, `resolve`, `columns` |
| `client.users` | User management | `list`, `create`, `get`, `get_or_create`, `update`, `delete` |
| `client.dashboards` | Dashboard management | `list`, `create`, `get`, `update`, `delete`, `refresh`, `refresh_status` |
| `client.projects` | Analysis projects | `list`, `create`, `get`, `update`, `delete`, `add_source`, `run`, `run_status`, `run_cancel`, `list_steps`, `get_step_data` |
| `client.projects.chats` | Chats within projects | `create`, `list`, `get`, `stream`, `cancel`, `delete` |
| `client.sources` | Sources, connectors & data | `list`, `create`, `create_data_source`, `query`, `source_data`, `append_rows`, `replace_data`, `ask`, `sync`, `list_connectors` |
| `client.views` | SQL-defined views | `list`, `create`, `get`, `update`, `delete`, `run`, `get_run`, `wait_for_run`, `preview`, `chat` |
| `client.files` | File management | `upload`, `list`, `get`, `delete` |
| `client.keys` | API key management | `create`, `list`, `get`, `delete` |
| `client.sharing` | Sharing & permissions | `share_project`, `share_dashboard`, `share_source`, `list_project_shares`, `list_dashboard_shares`, `revoke_project_share`, `revoke_dashboard_share`, `org_share_source` |
| `client.audit` | Audit log | `list` |
| `client.usage` | Usage metrics | `org_usage`, `user_usage` |

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
│   │   └── OriginRequiredError — 400 origin_required (org has an embed-domain allowlist)
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

- Python 3.10+
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

## Support policy

The 1.x line receives security fixes only, for 6 months from the 2.0.0 release (2026-08-31). Migrate with [docs/MIGRATION.md](docs/MIGRATION.md).
