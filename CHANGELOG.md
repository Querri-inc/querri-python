# Changelog

## 2.2.0 (unreleased)

### Added

- **Custom Roles on embed sessions.** `client.embed.create_session()` and
  `client.embed.get_session()` (sync and async) take `role=` — the id or key
  of the Custom Role the session runs as. It is sent only when set, and it
  is not `user["role"]` (the org role used when creating a user). Decide it
  on your server, never from the browser's request. Granting a role the user
  does not hold is **permanent**: it is added to the user's role assignment
  (later sessions and the app see it), revoking the session does not remove
  it, and an admin removes it in Settings → People. `EmbedSession.role_id`
  and `EmbedSessionListItem.role_id` carry the applied role (`None` without
  one — or when an older server ignored `role`, in which case the session
  runs as the user's own role; servers released after 2026-10-21 also
  return it from refresh and list, earlier ones only from create);
  `refresh_session()` returns it too, and the `get_session()` dict carries
  `role_id` when a role was applied. CLI: `querri session new --role` /
  `querri session get --role`; `session new` and `session refresh` print
  `Role ID`, and the `session list` table has a `Role ID` column.
- **`APIError.permission` and `APIError.reason`.** A `403
  permission_denied` names the permission the call needed (from the body,
  else the `X-Permission-Denied` header) and why it was refused
  (`role_denied`, `not_in_plan`, `flag_off`, `embed_disabled`,
  `dependency_unmet`, `forbidden`, `scope_exceeds_role`; the server may add
  more). The header is used only when the error's code is
  `permission_denied` or there is no code, and only when it holds a
  permission key (contains a `.`), not an error code — so an
  `escalation_denied` refusal never borrows it. The in-app flat body
  `{"detail": {"error": "<code>", ...}}` is parsed too. `RateLimitError`
  keeps them too.
- **`APIError.body`**: the parsed JSON response body (any JSON value; `None`
  when the response was not JSON), on every `APIError`, streamed requests
  included. It carries the fields the exception does not lift out, e.g.
  `err.body["detail"]["error"]["scopes"]` on `scope_exceeds_role` and
  `err.body["detail"]["error"]["missing"]` on `escalation_denied`.
- **Error-code constants**: `querri.ROLE_DISABLED`, `querri.PERMISSION_DENIED`,
  `querri.ESCALATION_DENIED` (403), `querri.LAST_ADMIN` (409),
  `querri.INVALID_PARAMETERS` (400), … (26 in all) and the
  `querri.ErrorCode` / `querri.PermissionDeniedReason` `Literal`s — the
  codes for authentication, access, Custom Roles, embed sessions and user
  role changes; the API sends other codes too, so treat `code` as a string.
  docs/server-sdk.md has an Error codes table.
- `embed:role:assign` in the `querri key new` scope picker.
- **`X-Querri-Client` header.** Every client sends `X-Querri-Client:
  sdk/<version>`; clients built by the `querri` command, and its
  login/refresh token requests, send `cli/<version>`, so the server can tell
  CLI use from library use.

### Changed

- **`422` request-validation errors raise `ValidationError`** (was the base
  `APIError`) with a readable message — `"Validation failed: body.ttl: Input
  should be greater than or equal to 900"` — instead of the raw `detail`
  list. A bare `{"detail": {"code", "message"}}` body is parsed like the
  `error` envelope.
- **Behaviour change — CLI: a 403 exits `6`** instead of `1`. Scripts that
  test for exit code `1` on a refused call must accept `6`. In text mode the
  message gains the permission and reason (`(permission:
  dashboards.list.view, reason: role_denied)`); the API code is printed once,
  on its `Code:` line, as before.
- **CLI `--json` errors: unchanged from 2.1.0, plus `exit_code`.** Every
  JSON error prints the same keys and values 2.1.0 printed for the same
  situation — a 403 is still `"error": "api_error"`, `code` is still the API
  error code when the server sent one and otherwise the exit code, and
  `permission` / `reason` are not added as keys — plus `"exit_code"`, the
  process exit code. The one value that moves is a consequence of the exit
  code above: a 403 with no API code has `"code": 6` (it was `1`). The `querri
  view run` timeout (`{"error": "<message>"}`) and `querri auth switch-org`
  single-org outputs keep their 2.1.0 shapes, plus `exit_code`.
- Docs: API-key scopes follow a person's role — a key keeps only the scopes
  both its creator and its bound user currently hold, and the permission
  checks made on its behalf (embed role grants, the users endpoints' role
  guards) use the permissions both hold (servers released after 2026-10-21;
  earlier servers cap only keys created in Settings and check role grants
  against the bound user, else the creator). The keys section covers
  binding (Admins only), pseudo ids, and what a key minted by another key
  inherits. On those servers `client.users` `create` / `update` / `delete` /
  `get_or_create` (and `get_session()` for a new user) can be refused with
  `escalation_denied` or `last_admin`. The real scope list replaces the
  invented names in the CLI skill. `as_user` calls can raise
  `permission_denied` under the session's role.

### Fixed

- **Streaming calls keep their error details.** A streamed request
  (`projects.chats.stream()`, view streams) that failed raised an
  `APIError` with no `code`, `message`, `permission` or `reason`, because
  the unread body could not be parsed. The body is now read (and the
  response closed) before raising; a body that fails mid-read still raises
  the status's exception class.
- **Retried streamed responses are closed.** A streamed request that got a
  429 or a retryable 5xx left each discarded response open, holding its
  connection; each is now closed before the retry.
- **A JSON array or scalar error body no longer crashes error handling.**
  `raise_for_status` assumed a JSON object and raised `AttributeError` on a
  body like `["bad"]` or `"oops"`; it now raises the status's exception.
- `create_session(role="")` / `get_session(role="")` no longer send an
  empty `role`.
- **`querri view list` no longer truncates IDs.** The Rich table clipped
  36-character view UUIDs with `…`, and pasting the clipped ID into `querri
  view chat` failed with a misleading 403. ID/UUID columns now never wrap
  (QUE-135).
- `skills/querri-cli/references/json-shapes.md` documented a non-existent
  `querri embed create-session` and a stale `querri key create`; it now
  documents `querri session new` / `refresh` / `list` / `get`, `querri key
  new` and the `--json` error shape.
- **`examples/web-embed/server.py` no longer exposes the Werkzeug
  debugger.** It bound `0.0.0.0` with `debug=True`, letting anyone on the
  network run code on the machine. It now binds `127.0.0.1` with debug off;
  `HOST` and `FLASK_DEBUG=1` opt in, and debug is refused on a non-local
  host.

## 2.1.0 (2026-09-24)

### Added

- **`client.library`** (sync and async) and the `querri library` CLI: the Data
  Library surface — libraries, collections, anchor and refining questions,
  graph search and zoom, `record_fact`, the Librarian `chat` / `chat_stream`,
  `ask`, `intake`, `consolidate`, `eval`, backfill and health. Reference:
  [docs/data-library.md](docs/data-library.md). This is the `dev` line that
  had been building since 1.1.0; it ships here unchanged.

### Fixed

- **Error bodies without a Stripe-style envelope keep their message and
  code.** FastAPI raises `{"detail": {"error": {...}}}` (or a plain string
  `detail`); `APIError.message`, `.code` and `.type` were left as
  `"HTTP <status>"` / `None` for those, so a `NotFoundError` for a step with
  no data read the same as one for a missing project. Both shapes are parsed
  now.

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
  (bounded at 50 passes), and tolerates a session expiring between list
  and delete. Still best-effort — with more than 200 concurrent sessions
  org-wide the listing is a sample and stragglers can survive; do not
  treat a return as proof every session is gone.

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
