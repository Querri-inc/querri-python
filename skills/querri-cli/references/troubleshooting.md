# Querri CLI — Troubleshooting

## Project created but not visible in `project list`

**Symptom:** `project new` returns a UUID and 200 OK, but `project list` returns `[]`.

**Cause:** FGA (fine-grained authorization) failed to write permission tuples during project creation. The project exists in MongoDB but no `viewer`/`owner` grants were written, so FGA filters it out of list results.

**Check:** Look at server logs for `[FGA]` errors:
```bash
docker compose -f docker-compose.core.yml -f docker-compose.dev.yml logs server-api --since 10m | grep "\[FGA\]"
```

**Common root cause:** WorkOS SDK version mismatch. The `fga_service.py` uses `client.authorization.*` (added in WorkOS 5.43.0), but an older image may have 5.19.x installed with only `client.fga`.

**Fix:** Rebuild the server-api container:
```bash
docker compose -f docker-compose.core.yml -f docker-compose.dev.yml up --build server-api
```

**Verify fix:**
```bash
docker compose ... exec server-api pip show workos  # should be >=5.43.0
```

---

## `querri --json` not working (option not recognized)

**Symptom:** `querri project list --json` errors with "No such option".

**Cause:** `--json` is a **global flag** and must come before the subcommand.

**Fix:**
```bash
querri --json project list    # correct
```

---

## `No active project. Run 'querri project select'`

**Cause:** No project has been selected (or the profile doesn't have one set).

**Fix:**
```bash
querri project select "My Project"           # select by name
querri --project <uuid> chat -p "..."        # or pass explicitly
```

---

## Chat returns `403 Forbidden` on `/projects/<id>/chat`

**Symptom:** Server logs show `GET /projects/<id>/chat HTTP/1.1" 403 Forbidden` before a successful `POST /v1/projects/<id>/chats`.

**Cause:** The CLI first tries the internal (non-v1) endpoint with the JWT, which is rejected. It then falls back to the v1 API key endpoint. This is expected behavior — the 403 is harmless.

---

## `invalid token format` from curl

The JWT stored in `~/.querri/tokens.json` is a Querri-internal token, not a raw WorkOS JWT. It can't be used directly in `Authorization: Bearer` headers with curl. Use the API key flow instead:

```bash
export QUERRI_API_KEY="sk_live_..."
querri --json project list
```

---

## `QUERRI_USER_ID` not set error

**Symptom:** CLI errors with "Could not determine user ID."

**Cause:** Some commands (`project new`, `project run`) need a user ID to set ownership. This is resolved from:
1. `QUERRI_USER_ID` env var
2. Stored login profile

**Fix:**
```bash
export QUERRI_USER_ID="user_01J8X2EPW1PVPPC3SJ4JFF5Q4Y"   # from `querri whoami`
# or log in interactively:
querri auth login
```

---

## File upload succeeds but source data not available immediately

File processing (column detection, row count, indexing) is async. After upload, `file get <id>` may show `columns: null` briefly. Wait a few seconds and retry, or proceed — `project add-source` will trigger ingestion regardless.

---

## Debugging streaming chat issues

Enable debug logging for all SSE stream events:
```bash
querri chat -p "..." --debug
tail -f ~/.querri/debug.log
```

---

## Server is running but CLI can't connect

Check the host configuration:
```bash
querri whoami    # shows "host" field
```

For local dev, it should be `http://localhost`. Override if needed:
```bash
export QUERRI_HOST=http://localhost
```

---

## View `run` fails / `preview` returns "Source '...' has not been materialized (no QDF attached)"

The view references a source that has no materialized table (QDF). Most common cause: the source is
an **Excel** file (`.xlsx`/`.xls`), which is **not** materialized on upload (it's parsed on demand
only inside a chat/project). A view scans sources directly, so the Excel source has nothing to scan.

Fix: convert the sheet to CSV and upload that — CSV/JSON/Parquet materialize on upload — then point
the view at the CSV's source UUID:
```bash
querri --json file upload data.csv          # grab the returned source id
querri view update <view_id> --sql "SELECT ... FROM {source:<csv_source_id>} ..."
querri view run --view-ids <view_id>
```
Confirm a source is materialized first: `querri --json source describe <id>` should show a non-null
`row_count` and non-empty `columns`. (`source sync` to force materialization is **not** available via
the public API — it returns 501.)

---

## View returns the wrong rows / scans the wrong source

When you create a view with `--prompt` (AI authoring), the agent picks the source(s) and the CLI does
**not** print which UUID it chose. It can pick a different source than you intended. Always verify:
```bash
querri --json view get <view_id>     # read sql_definition → check the FROM {source:UUID} token
```
If it's wrong, overwrite the SQL with the correct source UUID (from `source list`):
```bash
querri view update <view_id> --sql "SELECT ... FROM {source:<correct_uuid>} ..."
querri view run --view-ids <view_id>
```
Remember: view SQL uses `FROM {source:UUID}` tokens, **not** plain table names and **not** the
`FROM data` convention that `source query` uses.

---

## `dashboard new` / `dashboard delete` / `source sync` return HTTP 501 not_implemented

These three operations are not yet bridged to the public API (tracked gaps, not permanent). Use the
Querri **web app** to create/delete dashboards or pin charts. From the CLI, dashboards support only
`list`, `get`, `update` (name/description), `refresh`, and `refresh-status`. A Querri project's
"Data Flow" view already shows all its charts, so it can serve as a lightweight dashboard substitute.
