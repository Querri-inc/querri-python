# Changelog

## 2.0.0 (2026-08-31)

Migration guide with before/after snippets: [docs/MIGRATION.md](docs/MIGRATION.md).

### Breaking

- **`source_scope` removed from `client.embed.create_session()`** (sync and
  async). It was never enforced by the server — a silently-ignored parameter
  that *looked* like access control. Passing it now raises `TypeError`. Scope
  sessions with access policies instead: `client.embed.get_session(access=...)`.
- **`as_user()` / `UserQuerri` rebased from `/api` to `/api/v1`.** Embed
  sessions (`X-Embed-Session`) are the public API's highest-priority
  credential, so user-scoped clients now call the same public API paths as
  the admin client.
- **`user_client.dashboards` is read-only.** Embed sessions exclude the
  `admin:dashboards:write` scope server-side; the user-scoped surface now
  exposes only `list()`, `get()`, and `refresh_status()` — `create`,
  `update`, `delete`, and `refresh` no longer exist there (they always
  belonged to the admin client).
- There is no `user_client.embed`: embed sessions exclude
  `embed:session:create` server-side (a session cannot mint sessions).
  The accessor never existed in the SDK; the contract is now documented
  and tested.
- **`ttl` is validated client-side**: `create_session()` and
  `get_session()` raise `ValueError` for TTLs outside [900, 86400] seconds
  instead of sending a value the server would silently clamp.

### Added

- `client.embed.get_ui_config(org)` — fetches the public, unauthenticated
  `GET {host}/api/embed/ui-config?org=...` (main app path, not `/api/v1`)
  and returns the raw `{chrome, theme, privacy}` dict.
- `querri session ui-config --org <id>` CLI command for the same.
- `OriginRequiredError` (subclass of `ValidationError`), raised for
  `400 origin_required` with a message explaining the org's embed-domain
  allowlist and how to pass `origin`.
- `querri share source org` gained `--disable` to turn org-wide sharing
  off (the server contract always supported `enabled: false`).
- `querri keys create` interactive scope picker now includes the
  `admin:skills:*`, `admin:library:*` scopes and `*` (superadmin).

### Fixed

- `client.embed.revoke_user_sessions()` no longer stops at the first
  listing page: the server caps listings at 200 with no cursor, so it now
  loops revoke-and-relist until a listing shows no sessions for the user
  (bounded at 50 passes).

## 1.1.1 (2026-08-31)

### Fixed

- **Web-embed example** (`examples/web-embed/server.py`): three dispatched
  actions called keyword-only SDK methods positionally, raising `TypeError`
  (returned as HTTP 500): `embed.refreshSession`, `users.getOrCreate`, and
  `policies.resolve`. All now pass keyword arguments.
- **Web-embed example** (`examples/web-embed/index.html`): the SDK Explorer's
  "Data" group sent `data.*` action names the server never dispatched — every
  action in the group returned "Unknown action". Renamed to the real
  `sources.*` actions.
- **Docs**: `docs/server-sdk.md` and `README.md` showed `create_session`,
  `refresh_session`, and `get_session` with positional parameters; all three
  are keyword-only (`create_session(*, user_id=..., origin=..., ttl=...)`,
  `refresh_session(session_token=...)`). Snippets updated to keyword form.
- **Browser embed loading**: examples and docs now load the embed script from
  the product — `<script src="{serverUrl}/sdk/querri-embed.js">` — instead of
  an unverifiable CDN/npm IIFE path. The web-embed example injects the script
  after fetching `serverUrl` from its `/api/config` endpoint.
- **Embed chrome options**: examples use the v2 vocabulary
  (`chrome: { rail: { show: true }, header: { show: true } }` — `rail`
  replaces `sidebar`).
- **Origin allowlist guidance**: create-session docs and examples now pass
  `origin` and document the enforcement behavior — when the organization
  configures allowed embed domains, session creation without an origin fails
  with `400 origin_required`, and an origin not on the allowlist fails with
  `403 origin_not_allowed`.

### Deprecated

- `source_scope` on `client.embed.create_session()` (sync and async): the
  server does not enforce it, and it will be removed in v2.0.0. Passing it now
  emits a `DeprecationWarning`; the field is still sent, so behavior is
  unchanged. Scope sessions with access policies instead — see
  `client.embed.get_session(access=...)`.
