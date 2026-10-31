# Custom roles as code — CLI + SDK reference

A Querri custom role is a JSON **definition document** identified by a stable `key`, much like an AWS IAM policy. You export it, edit it in your editor, and apply it back in one call. Apply is an idempotent upsert: it creates the role when the key is new, replaces it when the key exists, and reports `unchanged` when nothing differs.

The `querri role` command (`querri roles` works too) and the `client.roles` SDK resource expose the full surface.

## Auth + setup

Roles-as-code calls need an API key with the roles scopes:

| Scope | Allows |
|---|---|
| `admin:roles:read` | `list`, `get`, `catalog`, `export` |
| `admin:roles:write` | `apply`, `import`, `delete` |

An admin creates a key with those scopes in **Settings → API Keys** (or `querri key new` and pick the **Roles** group). The person behind the key must also hold `admin.roles.manage`.

A key never does more than its person. A role may not grant a permission the caller does not hold; the server refuses that with 403 `escalation_denied`.

```bash
export QUERRI_API_KEY=qk_...
export QUERRI_ORG_ID=org_...
```

## The workflow

```bash
# 1. Export the custom roles (system roles are left out) to a file.
querri role export -o roles.json

# Or export one role.
querri role get ev-datapro > ev.json

# 2. Preview what an edit would change. Nothing is written.
querri role apply -f ev.json --dry-run

# 3. Apply it, and keep applying on every save.
querri role apply -f ev.json --watch
```

With `--watch` running, open the app in another browser as someone who holds the role, edit `ev.json`, and save: the role updates within about a second. Each apply prints what changed:

```
ev-datapro: updated  denies: +chat.code.view -tools.dashboards.use
ev-datapro: updated  config.home_chat: "chat" -> "project"
ev-datapro: unchanged
```

Press Ctrl-C to stop watching. A file that is mid-save or holds invalid JSON prints an error and the watch keeps going.

## The definition document

```json
{
  "schema": "querri.role/v1",
  "key": "ev-datapro",
  "name": "EV DataPro",
  "description": "Estrenar Vivienda end users: projects only, charts on request",
  "base": "creator",
  "enabled": true,
  "grants": [],
  "denies": ["tools.charts.use", "chat.code.view", "chat.tables.view"],
  "settings": {"chat.think_longer.use": {"default": "fast", "user_can_change": false}},
  "config": {"home_chat": "project"}
}
```

| Field | Notes |
|---|---|
| `schema` | Optional on input; always `querri.role/v1` on output. Any other value is refused (422 `unsupported_schema`). |
| `key` | `^[a-z0-9][a-z0-9-]{0,47}$`. The built-in keys `guest`, `creator`, `admin` cannot be applied or deleted (405 `system_role_immutable`). |
| `name` | Required, 1-80 characters, unique per org ignoring case (409 `name_taken`). |
| `base` | `guest`, `creator` or `admin` (default `creator`). The role starts from this and adds `grants` / removes `denies`. |
| `enabled` | Default `true`. |
| `grants` / `denies` | Permission keys from `querri role catalog`. Normalised by the server: a grant the base already has, or a deny the base lacks, is dropped. |
| `settings` | `{permission_key: {"default": ..., "user_can_change": bool}}` for setting-kind permissions. |
| `config` | `home_chat`, `landing`, `credits_monthly`, `context_overrides`, `theme`, `support_contact`, `access_policy_ids`, with the same validation as Settings → Roles. |

The API also returns `id`, `system`, `seat_class`, `user_count` and `updated_at`. They are output only: the server ignores them on input, and `get` and `export` leave them out of what they write.

### File formats

`querri role apply -f` reads JSON that holds any of:

- one definition: applied with `PUT /roles/{key}`
- a list of definitions, or `{"roles": [...]}` (what `export` writes): applied with one `POST /roles/import` call, in order. Each role succeeds or fails on its own.

YAML is not supported. The SDK does not depend on PyYAML.

`apply` exits non-zero when any role failed, so it is safe to use in CI.

## CLI reference

| Command | What it does |
|---|---|
| `querri role list` | Table of every role: key, name, base, enabled, users, system. |
| `querri role get REF` | The role's definition as JSON (`REF` is a key or ID). |
| `querri role export [-o PATH] [--include-system]` | `{"roles": [...]}` for the custom roles. |
| `querri role apply -f PATH [--dry-run] [--watch]` | Create or update roles from a file. |
| `querri role delete REF [--reassign-to KEY] [--yes]` | Delete a role. Asks first unless `--yes`. |
| `querri role catalog [--area AREA]` | Permission keys: key, area, kind, default per base role, requires. |

Deleting a role that some people hold as their only role needs `--reassign-to` (409 `role_in_use` otherwise).

All commands take the global `--json` flag.

## SDK reference

```python
from querri import Querri

client = Querri()

# Read
roles = client.roles.list()             # every role, system ones included
role = client.roles.get("ev-datapro")   # RoleDefinition
catalog = client.roles.catalog()        # PermissionCatalog

# Export what you would save to a file and re-apply
definitions = client.roles.export()     # list[dict], output-only fields stripped

# Apply one (dict or RoleDefinition); the key comes from the definition
result = client.roles.apply(
    {"key": "ev-datapro", "name": "EV DataPro", "denies": ["chat.code.view"]},
    dry_run=True,
)
print(result.action)                    # would_create / would_update / unchanged
for change in result.changes:
    print(change.field, change.before, "->", change.after)

# Apply several in one call
out = client.roles.import_roles(definitions)
if out.failed:
    for r in out.results:
        if r.failed:
            print(r.key, r.error.code, r.error.message)

# Delete
client.roles.delete("ev-datapro", reassign_to="creator")
```

`AsyncQuerri` has the same methods on `client.roles`, awaited.

`apply` raises `ValueError` when the definition has no `key`. Errors from the server raise the usual `APIError` subclasses. For example, `escalation_denied` raises `PermissionError`, and `name_taken` and `role_in_use` raise `ConflictError`.

| `result.action` | Meaning |
|---|---|
| `created` / `updated` | Written. |
| `unchanged` | The stored role already matches. |
| `would_create` / `would_update` | Dry run: what an apply would do. |
| `failed` | Import only: `result.error` has `code` and `message`. |
