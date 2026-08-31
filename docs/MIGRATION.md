# Migrating from 1.x to 2.0

v2.0.0 removes a fake security parameter, aligns the user-scoped client with
what the server actually authorizes, and makes two silent server behaviors
loud. Most 1.x code runs unchanged; the breaking changes are below, each with
before/after.

## `source_scope` removed from `create_session()`

**This is a security fix, not a cleanup.** `source_scope` was accepted by the
SDK and sent to the server, but the server never enforced it. Code that passed
it got sessions that *looked* scoped to specific sources and were not — a
silently-ignored access-control parameter is worse than none, because it reads
as a guarantee. v1.1.1 started warning; v2.0.0 removes it, so passing it now
raises `TypeError`.

Scope sessions with access policies, which the server enforces:

```python
# Before (1.x) — source_scope was silently ignored
session = client.embed.create_session(
    user_id="usr_1",
    source_scope=["src_sales"],   # did nothing
)

# After (2.0) — access policies are enforced server-side
session = client.embed.get_session(
    user="customer-42",
    access={"sources": ["src_sales"], "filters": {"tenant_id": "acme"}},
)
```

`get_session()` resolves the user, finds-or-creates a policy from the access
spec, assigns it, and mints the session in one call. If you manage policies
yourself, use `client.policies.setup(...)` / `assign_users(...)` and then
`create_session(user_id=...)` — the session inherits whatever the user's
policies grant.

## `as_user()` now calls `/api/v1`

`UserQuerri` previously called the internal API at `{host}/api`. Embed
sessions are the public API's highest-priority credential, so user-scoped
clients now call the same `/api/v1` paths as the admin client, still with the
`X-Embed-Session` header. No code change needed unless you depended on the
URL (e.g. in proxies, allowlists, or request logging):

```python
# Same code in 1.x and 2.0 — only the wire paths changed:
#   1.x: GET {host}/api/projects
#   2.0: GET {host}/api/v1/projects
with client.as_user(session) as uc:
    for project in uc.projects.list():
        print(project.name)
```

## User-scoped dashboards are read-only

Embed sessions exclude the `admin:dashboards:write` scope server-side —
writes always failed with 403. The SDK surface now says so:
`user_client.dashboards` exposes `list()`, `get()`, and `refresh_status()`
only.

```python
# Before (1.x) — compiled, then 403'd at runtime
with client.as_user(session) as uc:
    uc.dashboards.delete("dash_1")        # AttributeError in 2.0

# After (2.0) — dashboard writes belong to the admin client
client.dashboards.delete("dash_1")
```

Similarly, there is no `user_client.embed` (there never was one that worked:
`embed:session:create` is excluded from embed-session scopes). Mint and
manage sessions from the admin client.

## `ttl` outside [900, 86400] raises `ValueError`

The server silently clamps out-of-range TTLs. The SDK now refuses to send a
TTL that would not be honored as given:

```python
# Before (1.x) — sent ttl=60, server silently created a 900s session
client.embed.create_session(user_id="usr_1", ttl=60)

# After (2.0) — fails loudly before any HTTP
# ValueError: ttl must be between 900 and 86400 seconds, got 60
```

## `400 origin_required` raises `OriginRequiredError`

When the org configures an embed-domain allowlist and no `origin` is passed,
the SDK now raises `OriginRequiredError` — a subclass of `ValidationError`,
so existing `except ValidationError` handlers keep working — with a message
that says what to do (pass the embedding page's origin):

```python
from querri import OriginRequiredError

try:
    session = client.embed.create_session(user_id="usr_1")
except OriginRequiredError:
    session = client.embed.create_session(
        user_id="usr_1", origin="https://app.customer.com"
    )
```

## `revoke_user_sessions()` paginates

In 1.x it revoked at most whatever one listing returned (the server caps
listings at 200 with no cursor). It now loops revoke-and-relist until a
listing shows no sessions for the user. The signature and return value are
unchanged; only the completeness improved — expect more requests (and a
larger returned count) for users with many sessions.

## New in 2.0 (non-breaking)

- `client.embed.get_ui_config(org)` — the public embed UI config
  (`{chrome, theme, privacy}`) from `GET {host}/api/embed/ui-config?org=...`.
- `querri session ui-config --org <id>` — CLI for the same.
- `querri share source org SOURCE_ID --disable` — turn org-wide sharing off.
