# querri-python

Python SDK for the [Querri](https://querri.com) data analysis platform.

## Installation

```bash
pip install querri
```

Requires Python 3.9+.

## Quick Start

```python
import os
from querri import Querri

client = Querri(
    api_key=os.environ["QUERRI_API_KEY"],
    org_id=os.environ["QUERRI_ORG_ID"],
)

for project in client.projects.list():
    print(project.name)
```

Or let the SDK read from environment variables automatically:

```bash
export QUERRI_API_KEY="qk_live_..."
export QUERRI_ORG_ID="org_..."
```

```python
from querri import Querri

client = Querri()  # reads QUERRI_API_KEY and QUERRI_ORG_ID from env
```

## Authentication

API keys start with `qk_` and are scoped to a single organization. Generate one from **Settings > API Keys** in the Querri web app, or via the REST API.

Every request requires both an API key and an organization ID. Pass them to the constructor or set the `QUERRI_API_KEY` and `QUERRI_ORG_ID` environment variables.

## Configuration

| Parameter | Env Variable | Default | Description |
|-----------|-------------|---------|-------------|
| `api_key` | `QUERRI_API_KEY` | *(required)* | Your `qk_` API key |
| `org_id` | `QUERRI_ORG_ID` | *(required)* | Organization ID |
| `host` | `QUERRI_HOST` | `https://app.querri.com` | Server host |
| `timeout` | `QUERRI_TIMEOUT` | `30.0` | Request timeout (seconds) |
| `max_retries` | `QUERRI_MAX_RETRIES` | `3` | Retry attempts for transient errors |

Explicit arguments always override environment variables.

> **Note:** The parameter is `host`, not `base_url`. The SDK appends `/api/v1` automatically.
> For local development: `Querri(host="http://localhost")`.

```python
client = Querri(
    api_key="qk_live_...",
    org_id="org_...",
    host="http://localhost",  # for local development
    timeout=60.0,
    max_retries=5,
)
```

## User Management

```python
# Create a user
user = client.users.create(
    email="alice@example.com",
    external_id="cust-42",
    first_name="Alice",
    last_name="Smith",
    role="member",  # "member" or "admin"
)
print(user.id, user.email)

# Get a user by ID
user = client.users.get("usr_...")

# Idempotent get-or-create by external ID
user = client.users.get_or_create(
    external_id="cust-42",
    email="alice@example.com",
    first_name="Alice",
)
# Returns existing user if external_id already exists (never updates)

# List users (auto-paginates)
for user in client.users.list():
    print(user.email)

# Filter by external ID
page = client.users.list(external_id="cust-42")
user = page.data[0]

# Update
updated = client.users.update(user.id, first_name="Alicia")

# Delete
client.users.delete(user.id)
```

## Access Policies

Access policies control row-level security (RLS) — which data sources a user can see and which rows are visible.

### Create a policy

```python
policy = client.policies.create(
    name="APAC Sales",
    description="Restricts data to APAC region",
    source_ids=["src_abc", "src_def"],
    row_filters=[
        {"column": "region", "values": ["APAC"]},
        {"column": "department", "values": ["Sales", "Marketing"]},
    ],
)
```

### Assign users to a policy

```python
client.policies.assign_users(policy.id, user_ids=[user.id])
```

### The `setup()` convenience method

Create a policy and assign users in one call, using a friendlier dict syntax for row filters:

```python
policy = client.policies.setup(
    name="APAC Sales Team",
    sources=["src_abc", "src_def"],
    row_filters={"region": ["APAC"], "department": "Sales"},
    users=["usr_111", "usr_222"],
)
```

### Other operations

```python
# List policies
policies = client.policies.list()

# Filter by name
policies = client.policies.list(name="APAC Sales")

# Get policy details
policy = client.policies.get("pol_...")

# Update
client.policies.update(policy.id, name="New Name")

# Remove a user
client.policies.remove_user(policy.id, "usr_...")

# Delete policy
client.policies.delete(policy.id)

# Discover filterable columns
columns = client.policies.columns(source_id="src_abc")

# Preview resolved access (effective filters for a user + source)
resolved = client.policies.resolve(user_id="usr_...", source_id="src_abc")
print(resolved)
```

## Projects

```python
# List projects (auto-paginates)
for project in client.projects.list():
    print(project.name)

# Get a single page
page = client.projects.list(limit=10)
projects = page.data

# Get project details
project = client.projects.get("proj_...")

# Create a project
project = client.projects.create(
    name="Q4 Analysis",
    user_id="usr_...",
    description="Quarterly sales analysis",
)

# Update
client.projects.update(project.id, name="Q4 Analysis v2")

# Submit for execution
run = client.projects.run(project.id, user_id="usr_...")
print(run.status)  # "submitted"

# Check execution status
status = client.projects.run_status(project.id)
print(status.is_running)

# Cancel execution
client.projects.run_cancel(project.id)

# List steps
steps = client.projects.list_steps(project.id)
for step in steps:
    print(step.id, step.name)

# Get step result data (paginated, RLS-enforced)
data = client.projects.get_step_data(project.id, step.id, page=1, page_size=100)
print(data.columns)
print(data.rows[:5])

# Delete
client.projects.delete(project.id)
```

## Dashboards

```python
# List
dashboards = client.dashboards.list()

# Get details
dashboard = client.dashboards.get("dash_...")

# Create
dashboard = client.dashboards.create(name="Sales Overview")

# Update
client.dashboards.update(dashboard.id, name="Sales Overview v2")

# Trigger refresh (re-runs underlying projects)
client.dashboards.refresh(dashboard.id)

# Check refresh status
status = client.dashboards.refresh_status(dashboard.id)
print(status.status)

# Delete
client.dashboards.delete(dashboard.id)
```

## Embed Sessions

Create short-lived sessions for embedding Querri views in iframes.

```python
# Create an embed session
session = client.embed.create_session(
    user_id="usr_...",
    origin="https://app.customer.com",
    ttl=3600,  # seconds (15min to 24h)
)
print(session.session_token)  # "es_..."

# Refresh before expiry (old token is revoked)
new_session = client.embed.refresh_session(
    session_token=session.session_token,
)

# List active sessions
session_list = client.embed.list_sessions(limit=50)
for s in session_list.data:
    print(s.session_token, s.user_id)

# Revoke a session
client.embed.revoke_session(session.session_token)
```

## The Flagship `get_session()` Method

`client.embed.get_session()` is the **single most important method** in the SDK. It combines user resolution, access policy application, and embed session creation into one call — the complete white-label embedding workflow.

### String shorthand (existing user)

If the user already exists, pass their `external_id` as a string:

```python
session = client.embed.get_session(
    user="customer-42",
    ttl=7200,
)
print(session["session_token"])
```

### Dict form (auto-create user)

Pass a dict to get-or-create the user automatically:

```python
session = client.embed.get_session(
    user={
        "external_id": "customer-42",
        "email": "alice@customer.com",
        "first_name": "Alice",
        "last_name": "Smith",
        "role": "member",
    },
    origin="https://app.customer.com",
)
```

### Inline access spec (auto-managed policy)

Specify `sources` and `filters` directly. The SDK creates a deterministic auto-named policy (or reuses an existing one with the same spec):

```python
session = client.embed.get_session(
    user={
        "external_id": "customer-42",
        "email": "alice@customer.com",
    },
    access={
        "sources": ["src_sales", "src_marketing"],
        "filters": {
            "region": ["APAC", "EMEA"],
            "department": "Sales",
        },
    },
    origin="https://app.customer.com",
    ttl=3600,
)
```

### Reference existing policies

```python
session = client.embed.get_session(
    user="customer-42",
    access={"policy_ids": ["pol_abc", "pol_def"]},
)
```

### Return value

`get_session()` returns a plain dict (not a Pydantic model):

```python
{
    "session_token": "es_...",
    "expires_in": 3600,
    "user_id": "usr_...",
    "external_id": "customer-42",
}
```

## Chat Streaming

Stream AI responses within a project's chat:

```python
# Create a chat
chat = client.projects.chats.create(project.id, name="Analysis Chat")

# Stream response chunk by chunk
stream = client.projects.chats.stream(
    project.id,
    chat.id,
    prompt="Summarize the sales data by region",
    user_id="usr_...",
)
for chunk in stream:
    print(chunk, end="", flush=True)
print()

# Or get the full response text at once
stream = client.projects.chats.stream(
    project.id, chat.id,
    prompt="What are the top 5 products?",
    user_id="usr_...",
)
full_text = stream.text()
print(full_text)

# Cancel an active stream
client.projects.chats.cancel(project.id, chat.id)
```

## Error Handling

All API errors inherit from `APIError` and include structured attributes:

```python
from querri import (
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    ServerError,
)

try:
    project = client.projects.get("nonexistent-id")
except NotFoundError as e:
    print(f"Not found: {e.message} (status={e.status})")
except RateLimitError as e:
    print(f"Rate limited — retry after {e.retry_after}s")
except AuthenticationError:
    print("Invalid API key")
except ValidationError as e:
    print(f"Bad request: {e.message}")
except ServerError as e:
    print(f"Server error: {e.status}")
except APIError as e:
    print(f"API error {e.status}: {e.message}")
    print(f"  type={e.type}, code={e.code}, request_id={e.request_id}")
```

### Exception hierarchy

```
QuerriError
├── APIError
│   ├── AuthenticationError  (401)
│   ├── PermissionError      (403)
│   ├── NotFoundError        (404)
│   ├── ValidationError      (400)
│   ├── ConflictError        (409)
│   ├── RateLimitError       (429)  — has retry_after attribute
│   └── ServerError          (500+)
├── StreamError
│   ├── StreamTimeoutError
│   └── StreamCancelledError
└── ConfigError
```

## Async Client

The `AsyncQuerri` client mirrors the sync API with `async`/`await`:

```python
import asyncio
from querri import AsyncQuerri

async def main():
    async with AsyncQuerri() as client:
        # Auto-paginate
        async for project in client.projects.list():
            print(project.name)

        # Single page (use get_data() instead of .data)
        page = client.users.list(limit=20)
        users = await page.get_data()

        # Streaming
        stream = await client.projects.chats.stream(
            project_id, chat_id,
            prompt="Summarize the data",
            user_id="usr_...",
        )
        async for chunk in stream:
            print(chunk, end="", flush=True)

        full_text = await stream.text()

        # get_session works the same way
        session = await client.embed.get_session(
            user={"external_id": "cust-42", "email": "a@b.com"},
            access={"sources": ["src_sales"]},
        )

asyncio.run(main())
```

> **Async pagination note:** `AsyncCursorPage` doesn't have a `.data` property. Use `await page.get_data()` to fetch the first page, or `async for item in page` to auto-paginate.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run unit tests
pytest tests/ -v

# Run integration tests (requires running Querri instance)
export QUERRI_API_KEY="qk_..."
export QUERRI_ORG_ID="org_..."
pytest tests/test_integration.py -m integration -v
```

## Examples

See the [`examples/`](examples/) directory for runnable scripts covering every SDK feature.
