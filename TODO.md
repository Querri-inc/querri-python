# CLI QA Findings

Issues found during end-to-end QA of every CLI command (2026-04-14).

---

## Fixed

### ✅ `querri session list` — timestamp displayed as Unix epoch float
`created_at` was a float (e.g. `1776171557.8591616`). Now formatted as `2026-04-14 15:42 UTC`.
**Fix:** `querri/cli/embed.py` — pre-process row dicts before passing to `print_table`.

### ✅ `querri project select` — multiple matches broke non-interactive mode
Was falling through to the interactive picker loop and auto-selecting [1] via `EOFError` catch,
printing a noisy prompt. Now errors cleanly: "Ambiguous name '…' matches N projects. Use a project UUID."
**Fix:** `querri/cli/projects.py` — check `obj["interactive"]` before showing the picker.

### ✅ `querri share source list` / `remove` — HTTP 405
GET and DELETE endpoints for `/sources/{id}/shares` were never wired up on the server,
even though the `_list_shares` and `_revoke_share` helpers existed.
**Fix:** `Querri/server-api/api/public_api/routes/sharing.py` — added `list_source_shares` (GET)
and `revoke_source_share` (DELETE) routes, mirroring the project/dashboard pattern.

### ✅ `querri share source org` — HTTP 404
CLI was calling `/sources/{id}/shares/org` but the server route is `/sources/{id}/org-share`.
Also the request body was missing the `enabled` field that the server expects.
**Fix:** `querri/cli/sharing.py` — corrected path and added `"enabled": True` to the body.

### ✅ 501 errors — cryptic "HTTP 501" message
`dashboard new`, `dashboard delete`, `source sync` all hit intentional 501s (FGA warrant
creation/cleanup and Redis job queue not yet implemented server-side). Error message was
just "Error: HTTP 501 / Request ID: …".
**Fix:** `querri/cli/_output.py` — 501 now prints:
"This feature is not yet available via the API. Use the Querri web app instead."

---

## Needs Server Infrastructure Work (out of scope for CLI)

### ⏳ `querri dashboard new` / `dashboard delete` — HTTP 501
Intentional. Server has FGA warrant creation (`fga.create_warrant()`) and cleanup
(`fga.delete_warrants_for_resource()`) not yet implemented. Until the FGA service is
updated, dashboard create/delete must go through the web app.

### ⏳ `querri source sync` — HTTP 501
Intentional. Server is missing `RedisStreamsClient.enqueue_source_job()`. The infrastructure
for submitting sync jobs to the Redis queue hasn't been built out yet.

### ⏳ `querri step data` — HTTP 404 (qdf_not_found)
`step list` correctly reports `has_data: True` but `/steps/{id}/data` returns 404.
The QDF metadata or parquet file is absent in storage despite the step showing data.
Likely a garbage collection or race condition in the data pipeline — needs investigation
in the server's QDF save/load path.
