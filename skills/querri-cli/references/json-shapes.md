# Querri CLI — JSON Output Shapes

## `querri whoami`

```json
{
  "host": "http://localhost",
  "auth_type": "jwt",
  "org_id": "org_01JBETJ7PYNGXVMXV0BD3CFNA8",
  "credential": "<token>",
  "org_name": "Querri",
  "user_email": "dave@querri.com",
  "user_name": "Dave Ingram",
  "user_id": "user_01J8X2EPW1PVPPC3SJ4JFF5Q4Y"
}
```

## `querri project new` / `querri project get`

```json
{
  "id": "81f5238e-df93-4441-a858-3419bbe55d1f",
  "name": "CLI Test 2",
  "description": "Post-rebuild test",
  "status": "idle",           // idle | running | error | complete
  "step_count": 0,
  "chat_count": 0,
  "created_by": "user_01J8X2EPW1PVPPC3SJ4JFF5Q4Y",
  "created_at": "2026-04-10T02:59:35.692000",
  "updated_at": "2026-04-10T02:59:35.692000",
  "steps": null,              // populated on project get
  "chats_store": null
}
```

## `querri project list`

Array of project objects (same shape as above) plus an `"active"` boolean field.

Cursor-paginated — the SDK auto-iterates pages. Raw API returns `{"data": [...], "next": "<cursor>"}`.

## `querri file upload`

```json
{
  "id": "03ad2983-8d75-4b47-9a0f-8f8773f9d911",
  "name": "sales_test.csv",
  "size": 478,
  "content_type": null,
  "created_by": null,
  "created_at": "2026-04-10T03:00:25.905743",
  "columns": null,
  "row_count": null
}
```

## `querri file get`

Same as upload response but with `columns` and `row_count` populated after processing.

## `querri project add-source`

```json
{
  "source_id": "03ad2983-8d75-4b47-9a0f-8f8773f9d911",
  "project_id": "81f5238e-df93-4441-a858-3419bbe55d1f",
  "status": "added",
  "response": "<agent's summary text of the loaded dataset>"
}
```

## `querri chat` (non-streaming response)

```json
{
  "message_id": "948dd65a-3552-4e3d-a0a9-b66b4c8e5389",
  "text": "<AI response text>",
  "tool_calls": [
    {
      "tool_name": "Total Revenue by Region",
      "output": {
        "status": "running|success|error",
        "steps": { "<step_id>": { "name": "...", "status": "...", "tool": "duckdb_query", ... } }
      }
    }
  ],
  "files": [],
  "reasoning": "<internal reasoning trace, if --reasoning flag used>"
}
```

## `querri project run`

```json
{
  "id": "<project_id>",
  "run_id": "api_abc123def456",
  "status": "submitted"
}
```

## `querri project run-status`

```json
{
  "id": "<project_id>",
  "status": "idle|running|error|complete",
  "is_running": false
}
```

## `querri key new`

```json
{
  "id": "<key_uuid>",
  "name": "My Key",
  "key_prefix": "qk_abc1",
  "scopes": ["admin:projects:read"],
  "status": "active",
  "created_by": "<user_id>",
  "created_at": "...",
  "last_used_at": null,
  "expires_at": null,
  "rate_limit_per_minute": 60,
  "bound_user_id": null,
  "source_scope": null,
  "access_policy_ids": null,
  "ip_allowlist": null,
  "secret": "qk_..."        // only returned once, at creation
}
```

`querri key get` prints the same object without `secret`.

## `querri session new` / `querri session refresh`

```json
{
  "session_token": "es_...",
  "expires_in": 3600,
  "user_id": "<user_id>",
  "role_id": "role_..."     // the applied Custom Role (--role); null without one
}
```

`role_id` is also `null` when `--role` was passed to a server too old to know
it (the session then runs as the user's own role). A role the user did not
hold is granted **permanently** — revoking the session does not remove it.
Servers released after 2026-10-21 return `role_id` from refresh too; earlier
ones only from `session new`.

## `querri session list`

```json
{
  "data": [
    {
      "session_token": "es_...",
      "user_id": "<user_id>",
      "origin": "https://app.example.com",
      "created_at": "...",
      "auth_method": "api_key",
      "role_id": null
    }
  ],
  "has_more": false
}
```

## `querri session get`

The `get_session()` dict: `session_token`, `expires_in`, `user_id`,
`external_id`, and `role_id` only when a role was applied.

## Errors (`--json`)

Every error prints one object on stdout — the CLI 2.1.0 shape plus
`exit_code` (the process exit code). An API error:

```json
{
  "error": "api_error",          // auth_failed | not_found | rate_limited | server_error | not_implemented | api_error (incl. 403)
  "message": "...",
  "code": "permission_denied",   // the API error code, else the exit code (a number)
  "status": "403",               // string; status/type/request_id/doc_url only when set
  "type": "permission_error",
  "request_id": "req_...",
  "doc_url": "...",
  "exit_code": 6
}
```

Other errors: `{"error": "<kind>", "message": "...", "code": <exit code>,
"exit_code": <exit code>}` (plus `hint` for missing credentials).
`querri view run` timing out prints `{"error": "<message>", "exit_code": 1}`;
`querri auth switch-org` with one org prints `{"error": "single_org",
"message": "...", "exit_code": 1}`.

## `querri view get`

```json
{
  "id": "<view_uuid>",
  "name": "Total (preparado desde crudo)",
  "description": "...",
  "sql_definition": "SELECT ... FROM {source:<source_uuid>} WHERE ...",  // raw SQL, with {source:UUID} tokens
  "source_dependencies": ["<source_uuid>", "..."],   // source UUIDs the SQL references
  "status": "ready",                                  // pending | running | ready | failed
  "row_count": 253,                                   // null until materialized (view run)
  "created_at": "...",
  "updated_at": "..."
}
```

Note: the SQL field is `sql_definition` (not `sql`), and the referenced sources are in
`source_dependencies` (not `source_ids`). To see what source a view actually scans, read the
`{source:UUID}` token(s) inside `sql_definition`.

## `querri view run`

```json
{
  "run_id": "run_da5dc27425df",
  "organization_id": "org_...",
  "status": "completed",                 // completed | partial | failed (terminal); queued | running (transient)
  "view_uuids": ["<view_uuid>"],
  "succeeded": ["<view_uuid>"],
  "failed": [],
  "started_at": "...",
  "finished_at": "...",
  "error": null
}
```

A `failed` run often returns `error: null` — the real reason (e.g. `Source '<uuid>' has not been
materialized (no QDF attached)`) surfaces in `view preview`'s error body instead.

## `querri view preview`

```json
{
  "columns": ["col1", "col2", "..."],
  "rows": [ { "col1": "...", "col2": "..." } ],   // up to --limit rows (default 25)
  "row_count": 25
}
```

On an unrunnable view returns an error body instead, e.g.:
```json
{ "error": "api_error", "code": "preview_failed", "status": "422",
  "message": "Source '<uuid>' has not been materialized (no QDF attached)" }
```

## `querri source list` / `querri source describe`

```json
{
  "id": "<source_uuid>",
  "name": "total_combined.csv",
  "description": null,
  "summary": null,
  "columns": ["Reservation ID", "Fecha", "..."],   // [] if not materialized (e.g. fresh .xlsx)
  "column_types": { "Fecha": "VARCHAR", "...": "..." },
  "column_details": {
    "Km": { "type": "DOUBLE", "non_null_count": 2126, "unique_count": 1500,
             "min_value": 0.1, "max_value": 356.9, "mean": 25.6, "summary": "..." }
  },
  "row_count": 2870,                                 // null if not materialized
  "access_controlled": false,
  "updated_at": "..."
}
```

`row_count: null` + `columns: []` ⇒ the source has no QDF yet (not materialized) and can't be
queried or used in a view. CSV/JSON/Parquet materialize on upload; `.xlsx`/`.xls` do not.

## `querri source query` / `querri source data`

```json
{
  "data": [ { "col1": "...", "col2": "..." } ],
  "total_rows": 1,
  "page": 1,
  "page_size": 25
}
```

`source query` SQL must use the literal table name `data` (`FROM data`). `source data` is the same
shape (the API may send the count as `total_count`; the SDK normalizes it to `total_rows`).
