# Querri Python Server SDK Reference

The Querri Python SDK (`querri`) provides a server-side client for the Querri API, covering user management, embed session creation, and access policies. For most apps, a single `get_session()` call is all you need to create embed sessions.

```bash
pip install querri
```

## Quick Start

### Flask

```python
# app.py
from flask import Flask, jsonify, request
from querri import Querri

app = Flask(__name__)
client = Querri()  # reads QUERRI_API_KEY from env

@app.route("/api/querri-session", methods=["POST"])
def querri_session():
    # In production, derive user identity from YOUR auth system.
    # Never read user/access from the request body — a malicious client
    # can impersonate any user or escalate access.
    auth_user = get_authenticated_user(request)  # your auth logic

    session = client.embed.get_session(
        user={
            "external_id": auth_user.id,
            "email": auth_user.email,
        },
        access={
            "sources": ["src_sales_data"],
            "filters": {"tenant_id": auth_user.tenant_id},
        },
        ttl=3600,
    )

    return jsonify(session)
```

### Django

```python
# views.py
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from querri import Querri

client = Querri()

@require_POST
@login_required
def querri_session(request):
    user = request.user

    session = client.embed.get_session(
        user={
            "external_id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
        },
        access={
            "sources": ["src_sales_data"],
            "filters": {"tenant_id": user.tenant_id},
        },
    )

    return JsonResponse(session)
```

### FastAPI

```python
# main.py
from fastapi import FastAPI, Depends
from querri import Querri

app = FastAPI()
client = Querri()

@app.post("/api/querri-session")
async def querri_session(user = Depends(get_current_user)):
    # Use the async client for FastAPI
    async with AsyncQuerri() as async_client:
        session = await async_client.embed.get_session(
            user={
                "external_id": user.id,
                "email": user.email,
            },
            access={
                "sources": ["src_sales_data"],
                "filters": {"tenant_id": user.tenant_id},
            },
        )

    return session
```

### Understanding `filters`

The `filters` field in inline access uses column names as keys and allowed values:

```python
access={
    "sources": ["src_sales"],
    "filters": {
        "tenant_id": "acme",                    # exact match
        "region": ["us-east", "us-west"],        # any of these values (OR)
    },
}
```

The SDK auto-creates and caches a named access policy from this specification.

> **Security:** Always derive user identity and access from your server-side auth system. Never read `user` or `access` from the request body — a malicious client can impersonate any user or escalate access.

---

## Table of Contents

- [Configuration](#configuration)
- [Resource API Reference](#resource-api-reference)
  - [Users](#users)
  - [Embed](#embed)
  - [Policies](#policies)
  - [Dashboards](#dashboards)
  - [Projects](#projects)
  - [Chats](#chats)
  - [Data](#data)
  - [Sources](#sources)
  - [Files](#files)
  - [Keys](#keys)
  - [Audit](#audit)
  - [Usage](#usage)
  - [Sharing](#sharing)
- [User-Scoped Client (`as_user`)](#user-scoped-client-as_user)
- [get_session() Deep Dive](#get_session-deep-dive)
- [Error Handling](#error-handling)
- [Async Client](#async-client)
- [Framework Guides](#framework-guides)

---

## Configuration

### Constructor

```python
from querri import Querri

# Read from environment variables
client = Querri()

# Explicit credentials
client = Querri(api_key="qk_...", org_id="org_...")

# Full config
client = Querri(
    api_key="qk_...",
    org_id="org_...",
    host="https://app.querri.com",
    timeout=30.0,
    max_retries=3,
)
```

### Environment Variables

The client reads these environment variables as fallbacks when values are not provided in the constructor:

| Variable | Maps to | Description |
|---|---|---|
| `QUERRI_API_KEY` | `api_key` | API key for authentication |
| `QUERRI_ORG_ID` | `org_id` | Organization / tenant ID |
| `QUERRI_HOST` | `host` | API host URL |
| `QUERRI_TIMEOUT` | `timeout` | Request timeout in seconds |
| `QUERRI_MAX_RETRIES` | `max_retries` | Max retry attempts |

Resolution order: constructor argument > environment variable > default value.

### Config Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | _(required)_ | Your Querri API key (`qk_...`) |
| `org_id` | `str` | _(required)_ | Organization ID. Sent as `X-Tenant-ID` header. |
| `host` | `str` | `https://app.querri.com` | API host. `/api/v1` is appended automatically. |
| `timeout` | `float` | `30.0` | Request timeout in seconds |
| `max_retries` | `int` | `3` | Max retry attempts on 429/5xx errors |

---

## Resource API Reference

### Users

Manage users in your organization.

> The `role` field accepts `"admin"` or `"member"` (default). This controls the user's organization-level role. Resource-level permissions (viewer/editor/owner on projects, dashboards, and sources) are managed separately through access policies.

#### `client.users.create()`

Create a new user.

```python
create(*, email: str, external_id: str | None = None, first_name: str | None = None,
       last_name: str | None = None, role: str = "member") -> User
```

```python
user = client.users.create(
    email="alice@example.com",
    external_id="usr_alice",
    first_name="Alice",
    last_name="Smith",
    role="member",
)
```

#### `client.users.get()`

Fetch a single user by their Querri user ID.

```python
get(user_id: str) -> User
```

```python
user = client.users.get("user_abc123")
```

#### `client.users.list()`

List users with optional filters. Returns a paginated iterator.

```python
list(*, limit: int = 50, after: str | None = None,
     external_id: str | None = None) -> SyncCursorPage[User]
```

```python
# Auto-paginate through all users
for user in client.users.list():
    print(user.email)

# Single page
page = client.users.list(limit=10)
users = page.data

# Filter by external ID
for user in client.users.list(external_id="usr_alice"):
    print(user.id)

# Collect all into a flat list
all_users = client.users.list().to_list()
```

#### `client.users.update()`

Update an existing user.

```python
update(user_id: str, *, role: str | None = None, first_name: str | None = None,
       last_name: str | None = None) -> User
```

```python
updated = client.users.update("user_abc123", role="admin")
```

#### `client.users.delete()`

Delete a user.

```python
delete(user_id: str) -> UserDeleteResponse
```

```python
result = client.users.delete("user_abc123")
# result.deleted == True
```

#### `client.users.get_or_create()`

Look up a user by external ID, creating them if they do not exist. This is an upsert operation backed by `PUT /users/external/:externalId`.

```python
get_or_create(*, external_id: str, email: str | None = None,
              first_name: str | None = None, last_name: str | None = None,
              role: str = "member") -> User
```

```python
user = client.users.get_or_create(
    external_id="usr_alice",
    email="alice@example.com",
    first_name="Alice",
)
```

#### `client.users.remove_external_id()`

Remove an external ID mapping without deleting the user.

```python
remove_external_id(external_id: str) -> ExternalIdDeleteResponse
```

```python
result = client.users.remove_external_id("usr_alice")
```

---

### Embed

Manage embed session tokens.

#### `client.embed.create_session()`

Create a new embed session token for a user.

```python
create_session(user_id: str, *, origin: str | None = None,
               ttl: int = 3600) -> EmbedSession
```

```python
session = client.embed.create_session(
    user_id="user_abc123",
    origin="https://myapp.com",
    ttl=3600,
)
print(session.session_token)
```

#### `client.embed.refresh_session()`

Refresh a session token. The old token is revoked and a new one is returned.

```python
refresh_session(session_token: str) -> EmbedSession
```

```python
new_session = client.embed.refresh_session("es_old_token...")
```

#### `client.embed.list_sessions()`

List active embed sessions.

```python
list_sessions(*, limit: int = 100) -> EmbedSessionList
```

```python
session_list = client.embed.list_sessions(limit=20)
for s in session_list.data:
    print(s.session_token, s.user_id)
```

#### `client.embed.revoke_session()`

Revoke an embed session.

```python
revoke_session(session_id: str | None = None, *,
               session_token: str | None = None) -> EmbedSessionRevokeResponse
```

```python
client.embed.revoke_session(session_token="es_...")
```

#### `client.embed.revoke_user_sessions()`

Revoke all embed sessions for a user.

```python
revoke_user_sessions(user_id: str) -> int
```

```python
count = client.embed.revoke_user_sessions("user_abc123")
print(f"Revoked {count} sessions")
```

#### `client.embed.get_session()`

The flagship convenience method. See [get_session() Deep Dive](#get_session-deep-dive) for full documentation.

```python
get_session(user: str | dict, *, access: dict | None = None,
            origin: str | None = None, ttl: int = 3600) -> dict
```

```python
session = client.embed.get_session(
    user={"external_id": "usr_alice", "email": "alice@example.com"},
    access={"sources": ["src_sales"], "filters": {"tenant_id": "acme"}},
    ttl=3600,
)
print(session["session_token"])
```

---

### Policies

Manage access policies for row-level security (RLS).

#### `client.policies.create()`

Create a new access policy.

```python
create(name: str, *, description: str | None = None,
       source_ids: list[str] | None = None,
       row_filters: list[dict] | None = None) -> Policy
```

```python
policy = client.policies.create(
    name="APAC Sales",
    description="Row-level security for APAC region",
    source_ids=["src_sales"],
    row_filters=[
        {"column": "region", "values": ["APAC"]},
        {"column": "department", "values": ["Sales", "Marketing"]},
    ],
)
```

#### `client.policies.get()`

Fetch a single policy by ID.

```python
get(policy_id: str) -> Policy
```

```python
policy = client.policies.get("pol_abc123")
```

#### `client.policies.list()`

List policies with optional name filter. Returns a paginated iterator.

```python
list(*, name: str | None = None, limit: int = 25,
     after: str | None = None) -> SyncCursorPage[Policy]
```

```python
for policy in client.policies.list():
    print(policy.name)

# Filter by name
for policy in client.policies.list(name="APAC Sales"):
    print(policy.id)
```

#### `client.policies.update()`

Update an existing policy.

```python
update(policy_id: str, *, name: str | None = None,
       description: str | None = None,
       source_ids: list[str] | None = None,
       row_filters: list[dict] | None = None) -> PolicyUpdateResponse
```

```python
client.policies.update("pol_abc123", name="Updated Name")
```

#### `client.policies.delete()`

Delete a policy.

```python
delete(policy_id: str) -> PolicyDeleteResponse
```

```python
client.policies.delete("pol_abc123")
```

#### `client.policies.assign_users()`

Assign users to a policy. This is additive — existing assignments are preserved.

```python
assign_users(policy_id: str, *, user_ids: list[str]) -> PolicyAssignResponse
```

```python
result = client.policies.assign_users("pol_abc123", user_ids=["user_1", "user_2"])
```

#### `client.policies.remove_user()`

Remove a user from a policy.

```python
remove_user(policy_id: str, user_id: str) -> PolicyRemoveUserResponse
```

```python
client.policies.remove_user("pol_abc123", "user_1")
```

#### `client.policies.replace_user_policies()`

Atomically replace all policy assignments for a user. This removes any existing assignments and replaces them with the provided set.

```python
replace_user_policies(user_id: str, *, policy_ids: list[str]) -> PolicyReplaceResponse
```

```python
result = client.policies.replace_user_policies(
    "user_abc123",
    policy_ids=["pol_1", "pol_2"],
)
print(result.added)    # newly assigned policy IDs
print(result.removed)  # removed policy IDs
```

> **Tip:** Prefer `replace_user_policies()` over `assign_users()` when managing the full policy set for a user. It prevents policy accumulation from repeated `get_session()` calls.

#### `client.policies.resolve()`

Resolve the effective access for a user on a specific source.

```python
resolve(user_id: str, source_id: str) -> ResolvedAccess
```

```python
access = client.policies.resolve("user_abc123", "src_sales")
print(access.effective_access)  # "full", "filtered", or "none"
print(access.where_clause)      # SQL WHERE clause
```

#### `client.policies.columns()`

List filterable columns for a source.

```python
columns(*, source_id: str | None = None) -> list[SourceColumns]
```

```python
cols = client.policies.columns(source_id="src_sales")
for sc in cols:
    for col in sc.columns:
        print(f"{col.name} ({col.type})")
```

#### `client.policies.setup()`

Create a policy and assign users in one call.

```python
setup(name: str, *, sources: list[str] | None = None,
      row_filters: dict | None = None,
      users: list[str] | None = None,
      description: str | None = None) -> Policy
```

```python
policy = client.policies.setup(
    name="APAC Sales",
    sources=["src_sales"],
    row_filters={"region": ["APAC"], "department": "Sales"},
    users=["user_1", "user_2"],
    description="Auto-created via setup()",
)
```

---

### Dashboards

Manage dashboards.

#### `client.dashboards.create()`

```python
create(name: str, *, description: str | None = None) -> Dashboard
```

```python
dashboard = client.dashboards.create(name="Sales Overview")
```

#### `client.dashboards.get()`

```python
get(dashboard_id: str) -> Dashboard
```

```python
dashboard = client.dashboards.get("dash_abc123")
```

#### `client.dashboards.list()`

List dashboards. Returns a paginated iterator.

```python
list(*, limit: int = 25, after: str | None = None,
     user_id: str | None = None) -> SyncCursorPage[Dashboard]
```

```python
for dashboard in client.dashboards.list():
    print(dashboard.name)
```

#### `client.dashboards.update()`

```python
update(dashboard_id: str, *, name: str | None = None,
       description: str | None = None) -> DashboardUpdateResponse
```

```python
client.dashboards.update("dash_abc123", name="Updated Dashboard")
```

#### `client.dashboards.delete()`

```python
delete(dashboard_id: str) -> None
```

```python
client.dashboards.delete("dash_abc123")
```

#### `client.dashboards.refresh()`

Trigger a refresh of the dashboard's underlying projects.

```python
refresh(dashboard_id: str) -> DashboardRefreshResponse
```

```python
result = client.dashboards.refresh("dash_abc123")
print(result.project_count)
```

#### `client.dashboards.refresh_status()`

Check the status of a dashboard refresh.

```python
refresh_status(dashboard_id: str) -> DashboardRefreshStatus
```

```python
status = client.dashboards.refresh_status("dash_abc123")
print(status.status)
```

---

### Projects

Manage projects and their execution.

#### `client.projects.create()`

```python
create(name: str, user_id: str, *, description: str | None = None) -> Project
```

```python
project = client.projects.create(name="Q1 Analysis", user_id="user_abc123")
```

#### `client.projects.get()`

```python
get(project_id: str) -> Project
```

#### `client.projects.list()`

```python
list(*, limit: int = 25, after: str | None = None,
     user_id: str | None = None) -> SyncCursorPage[Project]
```

```python
for project in client.projects.list():
    print(f"{project.name} ({project.status})")
```

#### `client.projects.update()`

```python
update(project_id: str, *, name: str | None = None,
       description: str | None = None) -> Project
```

#### `client.projects.delete()`

```python
delete(project_id: str) -> None
```

#### `client.projects.run()`

Submit a project for execution.

```python
run(project_id: str, *, user_id: str) -> ProjectRunResponse
```

```python
result = client.projects.run("proj_abc123", user_id="user_abc123")
print(result.run_id)
```

#### `client.projects.run_status()`

Check the status of a project run.

```python
run_status(project_id: str) -> ProjectRunStatus
```

```python
status = client.projects.run_status("proj_abc123")
print(status.status, status.is_running)
```

#### `client.projects.run_cancel()`

Cancel a running project.

```python
run_cancel(project_id: str) -> ProjectCancelResponse
```

#### `client.projects.list_steps()`

List the steps in a project.

```python
list_steps(project_id: str) -> list[StepSummary]
```

```python
steps = client.projects.list_steps("proj_abc123")
for step in steps:
    print(f"{step.name} ({step.type}) — {step.status}")
```

#### `client.projects.get_step_data()`

Get the output data for a specific step.

```python
get_step_data(project_id: str, step_id: str, *,
              page: int = 1, page_size: int = 100) -> DataPage
```

```python
data = client.projects.get_step_data("proj_abc123", "step_1", page=1)
for row in data.data:
    print(row)
```

---

### Chats

Manage chats within projects. Accessed via `client.projects.chats`.

#### `client.projects.chats.create()`

```python
create(project_id: str, *, name: str | None = None) -> Chat
```

```python
chat = client.projects.chats.create("proj_abc123", name="Revenue Analysis")
```

#### `client.projects.chats.get()`

```python
get(project_id: str, chat_id: str) -> Chat
```

#### `client.projects.chats.list()`

```python
list(project_id: str, *, limit: int = 25) -> list[Chat]
```

#### `client.projects.chats.stream()`

Stream a chat response token-by-token.

```python
stream(project_id: str, chat_id: str, prompt: str,
       user_id: str, *, model: str | None = None) -> ChatStream
```

```python
stream = client.projects.chats.stream(
    "proj_abc123", "chat_abc123",
    prompt="What were Q1 sales?",
    user_id="user_abc123",
)

# Iterate chunks
for chunk in stream:
    print(chunk, end="", flush=True)

# Or get full text at once
text = stream.text()
```

#### `client.projects.chats.cancel()`

Cancel a streaming chat.

```python
cancel(project_id: str, chat_id: str) -> ChatCancelResponse
```

#### `client.projects.chats.delete()`

```python
delete(project_id: str, chat_id: str) -> None
```

---

### Data

Query and manage data sources.

#### `client.data.sources()`

List data sources. Returns a paginated iterator.

```python
sources(*, limit: int = 25, after: str | None = None) -> SyncCursorPage[Source]
```

```python
for source in client.data.sources():
    print(f"{source.name} — {source.row_count} rows")
```

#### `client.data.source()`

Get a single data source by ID.

```python
source(source_id: str) -> Source
```

#### `client.data.create_source()`

Create a new data source with initial rows.

```python
create_source(name: str, *, rows: list[dict]) -> Source
```

```python
source = client.data.create_source(
    name="Sales Data",
    rows=[
        {"region": "US", "revenue": 1000},
        {"region": "EU", "revenue": 2000},
    ],
)
```

#### `client.data.append_rows()`

Append rows to an existing data source.

```python
append_rows(source_id: str, *, rows: list[dict]) -> DataWriteResult
```

```python
result = client.data.append_rows("src_abc123", rows=[
    {"region": "APAC", "revenue": 1500},
])
print(result.rows_affected)
```

#### `client.data.replace_data()`

Replace all data in a source.

```python
replace_data(source_id: str, *, rows: list[dict]) -> DataWriteResult
```

```python
result = client.data.replace_data("src_abc123", rows=[
    {"region": "US", "revenue": 1200},
    {"region": "EU", "revenue": 2100},
])
```

#### `client.data.delete_source()`

Delete a data source.

```python
delete_source(source_id: str) -> dict
```

#### `client.data.query()`

Run a SQL query against a data source with RLS enforcement.

```python
query(sql: str, source_id: str, *, page: int = 1,
      page_size: int = 100) -> QueryResult
```

```python
result = client.data.query(
    sql="SELECT region, SUM(revenue) FROM sales GROUP BY region",
    source_id="src_abc123",
)
```

#### `client.data.source_data()`

Get raw data from a source with pagination.

```python
source_data(source_id: str, *, page: int = 1,
            page_size: int = 100) -> DataPage
```

```python
data = client.data.source_data("src_abc123", page=1, page_size=100)
```

---

### Sources

Manage data source connectors and syncing.

#### `client.sources.list_connectors()`

List available connectors.

```python
list_connectors() -> list[dict]
```

```python
connectors = client.sources.list_connectors()
```

#### `client.sources.list()`

List configured sources.

```python
list() -> list[dict]
```

```python
sources = client.sources.list()
```

#### `client.sources.create()`

Create a new source from a connector.

```python
create(name: str, connector_id: str, *,
       config: dict | None = None) -> dict
```

```python
source = client.sources.create(
    name="Production DB",
    connector_id="conn_postgres",
    config={"host": "db.example.com", "database": "analytics"},
)
```

#### `client.sources.update()`

Update a source configuration.

```python
update(source_id: str, *, name: str | None = None,
       config: dict | None = None) -> dict
```

#### `client.sources.delete()`

```python
delete(source_id: str) -> None
```

#### `client.sources.sync()`

Trigger a sync for a source.

```python
sync(source_id: str) -> dict
```

```python
client.sources.sync("src_abc123")
```

---

### Files

Manage uploaded files.

#### `client.files.upload()`

Upload a file.

```python
upload(file_path: str, *, name: str | None = None) -> File
```

```python
file = client.files.upload("/path/to/data.csv")
```

#### `client.files.get()`

```python
get(file_id: str) -> File
```

#### `client.files.list()`

```python
list() -> list[File]
```

```python
files = client.files.list()
```

#### `client.files.delete()`

```python
delete(file_id: str) -> None
```

---

### Keys

Manage API keys.

#### `client.keys.create()`

Create a new API key.

```python
create(name: str, scopes: list[str], *,
       expires_in_days: int | None = None,
       source_scope: dict | None = None,
       access_policy_ids: list[str] | None = None,
       bound_user_id: str | None = None,
       rate_limit_per_minute: int | None = None,
       ip_allowlist: list[str] | None = None) -> ApiKeyCreated
```

```python
key = client.keys.create(
    name="Production Key",
    scopes=["data:read", "data:write"],
    expires_in_days=90,
    access_policy_ids=["pol_abc"],  # restrict key to specific policies
    rate_limit_per_minute=100,
)
print(key.secret)  # only returned once at creation
```

#### `client.keys.get()`

```python
get(key_id: str) -> ApiKey
```

#### `client.keys.list()`

```python
list() -> list[ApiKey]
```

#### `client.keys.delete()`

Revoke and delete an API key.

```python
delete(key_id: str) -> dict
```

---

### Audit

Query the audit log.

#### `client.audit.list()`

List audit events with optional filters.

```python
list(*, actor_id: str | None = None, target_id: str | None = None,
     action: str | None = None, start_date: str | None = None,
     end_date: str | None = None, page: int = 1,
     page_size: int = 50) -> list[AuditEvent]
```

```python
events = client.audit.list(
    actor_id="user_abc123",
    action="user.created",
    start_date="2025-01-01",
    end_date="2025-12-31",
)
```

---

### Usage

Query usage metrics.

#### `client.usage.org_usage()`

Get organization-wide usage metrics.

```python
org_usage(*, period: str = "current_month") -> UsageReport
```

```python
usage = client.usage.org_usage()
usage = client.usage.org_usage(period="last_30_days")
# Period values: "current_month", "last_month", "last_30_days"
```

#### `client.usage.user_usage()`

Get usage metrics for a specific user.

```python
user_usage(user_id: str, *, period: str = "current_month") -> UsageReport
```

```python
usage = client.usage.user_usage("user_abc123", period="last_month")
```

---

### Sharing

Grant, revoke, and list access to projects, dashboards, and sources.

#### `client.sharing.share_project()`

Grant a user access to a project.

```python
share_project(project_id: str, *, user_id: str,
              permission: str = "view") -> ShareEntry
```

```python
client.sharing.share_project(
    "proj_abc123",
    user_id="user_abc123",
    permission="view",  # "view" or "edit"
)
```

#### `client.sharing.revoke_project_share()`

```python
revoke_project_share(project_id: str, user_id: str) -> dict
```

#### `client.sharing.list_project_shares()`

```python
list_project_shares(project_id: str) -> list[ShareEntry]
```

#### `client.sharing.share_dashboard()`

```python
share_dashboard(dashboard_id: str, *, user_id: str,
                permission: str = "view") -> ShareEntry
```

#### `client.sharing.revoke_dashboard_share()`

```python
revoke_dashboard_share(dashboard_id: str, user_id: str) -> dict
```

#### `client.sharing.list_dashboard_shares()`

```python
list_dashboard_shares(dashboard_id: str) -> list[ShareEntry]
```

#### `client.sharing.share_source()`

Grant a user access to a data source.

```python
share_source(source_id: str, *, user_id: str,
             permission: str = "view") -> ShareEntry
```

#### `client.sharing.org_share_source()`

Enable or disable org-wide sharing for a source.

```python
org_share_source(source_id: str, *, enabled: bool,
                 permission: str = "view") -> dict
```

```python
client.sharing.org_share_source("src_abc123", enabled=True, permission="view")
```

---

## User-Scoped Client (`as_user`)

The `UserQuerri` client lets you call the Querri API as a specific embed user. Resources are automatically filtered by FGA (Fine-Grained Authorization) — the user only sees data they have access to.

### Quick Example

```python
client = Querri()

# Step 1: Create an embed session for the user
session = client.embed.get_session(
    user={"external_id": "usr_alice", "email": "alice@example.com"},
    ttl=900,
)

# Step 2: Create a user-scoped client
with client.as_user(session) as user_client:
    # Step 3: Call resources — results are FGA-filtered
    for project in user_client.projects.list():     # only Alice's projects
        print(project.name)
    for dashboard in user_client.dashboards.list():  # only Alice's dashboards
        print(dashboard.name)
```

### How It Works

`as_user()` creates a `UserQuerri` that calls the internal API (`/api/`) with the embed session token in the `X-Embed-Session` header. The internal API applies FGA filtering automatically — only resources the user has been granted access to (via `sharing.share_project()`, `sharing.share_dashboard()`, etc.) are returned.

This is different from the admin `Querri` client, which calls the public API (`/api/v1/`) with an API key and returns all resources in the organization.

### Available Resources

| Resource | Example | Description |
|----------|---------|-------------|
| `user_client.projects` | `.list()`, `.get(id)`, `.run(id, user_id)` | Projects the user can access |
| `user_client.dashboards` | `.list()`, `.get(id)`, `.refresh(id)` | Dashboards the user can access |
| `user_client.sources` | `.list()`, `.list_connectors()` | Data sources and connectors |
| `user_client.data` | `.query(...)`, `.source_data(id)` | Query data with RLS enforcement |
| `user_client.chats` | `.create(proj_id)`, `.list(proj_id)` | Chats within accessible projects |

These are the same resource classes used by the admin client — only the authentication and base URL differ.

### Granting Access

To give a user access to a project or dashboard, use the admin client's sharing resource:

```python
client = Querri()

# Grant Alice viewer access to a project
client.sharing.share_project("proj_abc", user_id="user_alice_id", permission="view")

# Now Alice's user client will include this project
session = client.embed.get_session(user="usr_alice", ttl=900)
with client.as_user(session) as user_client:
    for project in user_client.projects.list():  # includes proj_abc
        print(project.name)
```

---

## get_session() Deep Dive

`client.embed.get_session()` is the flagship convenience method for the embed use case. It orchestrates three steps in a single call: user resolution, access policy setup, and embed session creation.

### The 3-Step Flow

```
1. User Resolution      →  users.get_or_create()
2. Access Policy Setup   →  policies.create() + policies.replace_user_policies()
3. Session Creation      →  embed.create_session()
```

> **Note:** Step 2 uses `replace_user_policies()` (not `assign_users()`) to atomically replace all policy assignments. This prevents policy accumulation when the same user is given different access filters across sessions.

### Basic Usage

```python
session = client.embed.get_session(
    user="usr_alice",
    access={
        "sources": ["src_sales"],
        "filters": {"tenant_id": "acme"},
    },
    ttl=3600,
    origin="https://myapp.com",
)

session["session_token"]   # str — JWT for the embed
session["expires_in"]      # int — seconds until expiry
session["user_id"]         # str — Querri user ID
session["external_id"]     # str | None — your external ID
```

### Parameters

```python
client.embed.get_session(
    user: str | dict,
    *,
    access: dict | None = None,
    origin: str | None = None,
    ttl: int = 3600,
) -> dict
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `user` | `str \| dict` | Yes | External ID string, or dict with `external_id` + optional profile fields |
| `access` | `dict \| None` | No | Policy IDs or inline sources + filters |
| `origin` | `str \| None` | No | Allowed origin for the embed iframe (CORS validation) |
| `ttl` | `int` | No | Session lifetime in seconds (default: `3600`) |

### Return Value

| Key | Type | Description |
|---|---|---|
| `session_token` | `str` | Pass this to the embed component's `fetchSessionToken` |
| `expires_in` | `int` | Seconds until the token expires |
| `user_id` | `str` | Querri internal user ID |
| `external_id` | `str \| None` | Your external ID for the user |

### User Resolution

The `user` parameter supports two forms:

**String shorthand** — pass an external ID directly:

```python
client.embed.get_session(user="usr_alice")
```

**Dict form** — pass an `external_id` along with optional profile fields:

```python
client.embed.get_session(
    user={
        "external_id": "usr_alice",
        "email": "alice@example.com",
        "first_name": "Alice",
        "last_name": "Smith",
        "role": "member",
    },
)
```

In both cases, if the user already exists, they are returned as-is (profile fields are used at creation time).

### Access Policies

The `access` parameter controls what data the user can see. It supports two forms:

**Policy ID reference** — attach the user to existing policies by ID:

```python
access={"policy_ids": ["pol_abc", "pol_def"]}
```

**Inline sources + filters** — specify the allowed sources and row-level filters directly:

```python
access={
    "sources": ["src_sales", "src_inventory"],
    "filters": {
        "tenant_id": "acme",
        "region": ["us-east", "us-west"],   # list values are OR'd
    },
}
```

### Deterministic Policy Hashing

When you use inline access, the SDK does not create a new policy on every call. Instead, it:

1. Sorts the `sources` array and `filters` keys alphabetically.
2. Normalizes filter values to sorted arrays.
3. Computes a SHA-256 hash of the resulting JSON.
4. Truncates the hash to 8 hex characters.
5. Names the policy `sdk_auto_{hash}` (e.g., `sdk_auto_a1b2c3d4`).

On subsequent calls with the same sources and filters, the SDK finds the existing policy by name and reuses it. This means:

- Identical access specs always map to the same policy.
- You do not accumulate duplicate policies over time.
- The user is assigned to the policy if not already assigned.
- The hash is cross-SDK compatible — the JS, PHP, and Python SDKs produce identical hashes for the same input.

### Race Condition Handling

When two concurrent requests try to create the same auto-managed policy, the SDK handles the TOCTOU (time-of-check-time-of-use) race condition:

1. Request A checks for policy — not found.
2. Request B checks for policy — not found.
3. Request A creates the policy — success.
4. Request B tries to create the same policy — gets a `409 Conflict`.
5. Request B catches the conflict, re-fetches the policy by name, and proceeds.

---

## Error Handling

### Error Hierarchy

```
QuerriError
├── APIError                — HTTP error response from API
│   ├── ValidationError     — 400 Bad Request
│   ├── AuthenticationError — 401 Unauthorized
│   ├── PermissionError     — 403 Forbidden
│   ├── NotFoundError       — 404 Not Found
│   ├── ConflictError       — 409 Conflict
│   ├── RateLimitError      — 429 Too Many Requests
│   └── ServerError         — 5xx Server Error
├── StreamError             — SSE stream issues
│   ├── StreamTimeoutError  — Stream timed out
│   └── StreamCancelledError — Stream was cancelled
└── ConfigError             — Missing/invalid SDK configuration
```

### APIError Properties

All `APIError` subclasses expose:

| Property | Type | Description |
|---|---|---|
| `status` | `int` | HTTP status code |
| `message` | `str` | Human-readable error message |
| `type` | `str \| None` | Error type from the API |
| `code` | `str \| None` | Error code from the API |
| `doc_url` | `str \| None` | Link to relevant documentation |
| `request_id` | `str \| None` | Request ID for support tickets |

### Common Patterns

```python
from querri import (
    Querri,
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    ConfigError,
)

try:
    user = client.users.get("user_nonexistent")
except NotFoundError:
    print("User not found")
except AuthenticationError:
    print("Invalid API key")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except ValidationError as e:
    print(f"Bad request: {e.message}")
except APIError as e:
    print(f"API error {e.status}: {e.message}")
    print(f"Request ID: {e.request_id}")
except ConfigError as e:
    print(f"Config error: {e.message}")
```

> **Tip:** Always catch specific exceptions before general ones. Python resolves `except` blocks top-down, so `APIError` must come after `NotFoundError`, `RateLimitError`, etc.

### Automatic Retry Behavior

The SDK automatically retries failed requests under these conditions:

- **429 (Rate Limited)**: Always retried, regardless of HTTP method.
- **500, 502, 503 (Server Errors)**: Retried only for idempotent methods (`GET`, `PUT`, `DELETE`, `HEAD`, `OPTIONS`).
- **Connection errors and timeouts**: Retried only for idempotent methods.

Retry delays use exponential backoff starting at 1 second (2^attempt), with random jitter (0–0.5s), capped at 30 seconds. The `Retry-After` header is respected when present.

The maximum number of retries defaults to 3 and can be configured via `max_retries` in the constructor.

### Rate Limit Backoff

`RateLimitError` includes a `retry_after` property (in seconds), parsed from the `Retry-After` response header:

```python
try:
    client.users.list()
except RateLimitError as e:
    if e.retry_after is not None:
        time.sleep(e.retry_after)
        # Retry the request
```

In practice, you rarely need manual retry logic — the SDK retries 429s automatically up to `max_retries` times.

---

## Async Client

The SDK provides a full async client (`AsyncQuerri`) with identical methods. Use it in async frameworks like FastAPI, or any `asyncio`-based application.

```python
from querri import AsyncQuerri

async with AsyncQuerri() as client:
    # Async iteration
    async for user in client.users.list():
        print(user.email)

    # Single page
    page = client.users.list(limit=10)
    users = await page.get_data()  # use get_data() instead of .data

    # Collect all
    all_users = await client.users.list().to_list()

    # get_session
    session = await client.embed.get_session(user="usr_alice")

    # User-scoped client
    async with client.as_user(session) as user_client:
        async for project in user_client.projects.list():
            print(project.name)
```

Key differences from the sync client:

| Sync | Async |
|------|-------|
| `client.users.list().data` | `await client.users.list().get_data()` |
| `for user in client.users.list():` | `async for user in client.users.list():` |
| `client.users.list().to_list()` | `await client.users.list().to_list()` |
| `with Querri() as client:` | `async with AsyncQuerri() as client:` |

---

## Framework Guides

### Flask

#### File Structure

```
your-app/
├── app.py
├── requirements.txt
└── templates/
    └── index.html
```

#### `app.py`

```python
from flask import Flask, jsonify, request
from querri import Querri
from querri._exceptions import APIError, QuerriError

app = Flask(__name__)
client = Querri()  # reads from env

@app.route("/api/querri-session", methods=["POST"])
def querri_session():
    auth_user = get_authenticated_user(request)

    try:
        session = client.embed.get_session(
            user={
                "external_id": str(auth_user.id),
                "email": auth_user.email,
            },
            access={
                "sources": ["src_sales"],
                "filters": {"tenant_id": auth_user.tenant_id},
            },
        )
        return jsonify(session)
    except APIError as e:
        return jsonify({"error": e.message}), e.status
    except QuerriError as e:
        return jsonify({"error": str(e)}), 500
```

### Django

#### `urls.py`

```python
from django.urls import path
from . import views

urlpatterns = [
    path("api/querri-session", views.querri_session),
]
```

#### `views.py`

```python
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from querri import Querri
from querri._exceptions import APIError

client = Querri()

@require_POST
@login_required
def querri_session(request):
    user = request.user

    try:
        session = client.embed.get_session(
            user={
                "external_id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
            },
            access={
                "sources": ["src_sales"],
                "filters": {"tenant_id": user.profile.tenant_id},
            },
        )
        return JsonResponse(session)
    except APIError as e:
        return JsonResponse({"error": e.message}, status=e.status)
```

### FastAPI

#### `main.py`

```python
from fastapi import FastAPI, Depends, HTTPException
from querri import AsyncQuerri
from querri._exceptions import APIError

app = FastAPI()

@app.post("/api/querri-session")
async def querri_session(user=Depends(get_current_user)):
    async with AsyncQuerri() as client:
        try:
            session = await client.embed.get_session(
                user={
                    "external_id": user.id,
                    "email": user.email,
                },
                access={
                    "sources": ["src_sales"],
                    "filters": {"tenant_id": user.tenant_id},
                },
            )
            return session
        except APIError as e:
            raise HTTPException(status_code=e.status, detail=e.message)
```

> **Tip:** For FastAPI, use `AsyncQuerri` to avoid blocking the event loop. If you must use the sync client, wrap calls in `run_in_executor`.
