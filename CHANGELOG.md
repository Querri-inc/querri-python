# Changelog

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
