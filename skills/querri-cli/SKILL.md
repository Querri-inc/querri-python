---
name: querri-cli
description: Work with the Querri data analysis platform via the querri CLI. Use this skill whenever the user wants to interact with Querri — creating or managing projects, uploading files, loading data sources, running analysis via chat, managing dashboards, sharing resources, handling API keys, managing users, working with access policies, embedded analytics, or any other Querri CLI operation. Also use when debugging Querri CLI issues, scripting automation against the Querri API, or exploring what the querri command can do.
---

# Querri CLI Skill

Querri is a data analysis platform. The `querri` CLI talks to the Querri API.

**Install:** `pip install querri`
**Upgrade:** `pip install --upgrade querri`

The CLI is self-documenting — run `querri <command> --help` for full flag details.

## Critical: Global Flags Must Come First

`--json`, `--no-interactive`, `--project`, and `--chat` are **global flags** and must appear **before** the subcommand:

```bash
querri --json project list          # correct
querri project list --json          # WRONG — will error
querri --no-interactive project chat ...    # correct
```

`-p` is **reserved globally** for `--project`. No subcommand uses `-p` as a short alias.

## Auth

```bash
querri whoami                        # check who you're logged in as + host
querri auth login                    # browser-based login (interactive only)
querri --json whoami                 # machine-readable auth info
```

Tokens are stored at `~/.querri/tokens.json`. The CLI auto-refreshes them. For non-interactive/scripted use, set `QUERRI_API_KEY` instead of relying on stored tokens.

## Core Workflows

### 1. Upload a file and analyze it

```bash
# Upload a file (CSV, Excel, JSON, etc.)
querri --json file upload path/to/data.csv

# Create a project (auto-selects it as active)
querri --json project new "My Analysis"

# Add the file to the project (triggers ingestion + agent summary)
querri --json project add-source <file_id>

# Ask a question
querri --json project chat -m "What are the top 5 products by revenue?"
```

### 2. Non-interactive / scripted use

Always pass `--no-interactive` to prevent prompts and `--json` for parseable output:

```bash
FILE_ID=$(querri --json --no-interactive file upload data.csv | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
PROJ_ID=$(querri --json --no-interactive project new "Automated Analysis" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
querri --json --no-interactive --project "$PROJ_ID" project add-source "$FILE_ID"
querri --json --no-interactive --project "$PROJ_ID" project chat -m "Summarize the data"
```

### 3. Work with an existing project

```bash
querri --json project list                              # list all projects
querri project select "My Analysis"                     # fuzzy-match by name, set active
querri --json --project <id> project chat -m "..."      # use specific project without selecting
```

## Projects

```bash
querri project new "Name"                          # create + auto-select
querri project new "Name" -d "description"        # with description
querri project list                                # list all (FGA-filtered)
querri project get [project_id]                    # detail (default: active)
querri project select <name_or_uuid>               # set active project
querri project update [id] --name "New Name"       # rename
querri project delete <id>                         # delete
querri project show [id]                           # visual step DAG
querri project run [id] --wait                     # run pipeline, optionally block
querri project run-status [id]                     # check run status
querri project run-cancel [id]                     # cancel running pipeline
querri project add-source <file_id> [project_id]  # load a file into project
```

**FGA note:** Projects are only visible to users who have been granted access via FGA. A project created via the CLI will be visible in `project list` — if it's not, it means the FGA grant failed during creation (check server logs for `[FGA]` errors).

## Files

```bash
querri file upload path/to/file.csv               # upload single file
querri file upload "data/*.csv"                   # glob batch upload
querri --json file upload file.csv                # upload + get JSON with id
querri file list                                   # list uploaded files
querri file get <file_id>                          # file details + column info
querri file delete <file_id>                       # delete
```

Supported formats: CSV, Excel (.xlsx/.xls), JSON, Parquet, and others.

## Chat

`querri project chat` is the convenience command for sending messages to the AI in a project. `querri chat` is a management command for listing and inspecting chat sessions.

### Sending messages

```bash
querri project chat -m "What is the average revenue by region?"   # send message
querri project chat -m "..." --new                                  # force new chat session
querri project chat -m "..." --model fast                          # model selection
querri project chat -m "..." --reasoning                           # show reasoning traces
querri project chat show                                            # show conversation history
querri project chat cancel                                          # cancel active stream
```

Chat responses include `message_id`, `text` (the AI response), `tool_calls` (analysis steps run), `files` (any generated files), and `reasoning`.

### Managing chat sessions

All `querri chat` commands default to the active project and chat. Pass explicit IDs to override.

```bash
querri chat list [project_id]                              # list chats (default: active project)
querri chat get [project_id] [chat_id]                     # chat detail
querri chat new [project_id]                               # create a new chat session
querri chat stream [project_id] [chat_id] --message "..."  # stream to a specific chat
querri chat cancel [project_id] [chat_id]                  # cancel a specific chat
querri chat delete [project_id] [chat_id]                  # delete
```

## Views

A view is a named SQL query over sources that can be materialized into a table. Views are created either by writing SQL directly or by describing what you want to an AI authoring agent.

### Two creation flows

**AI agent flow** — describe what you want; the agent writes the SQL and auto-generates a name and description:

```bash
querri view new --prompt "monthly revenue by product line"
querri view new -n "Revenue" --prompt "revenue by region"    # AI + custom name
```

**Direct SQL flow** — provide the SQL yourself; the view is created immediately:

```bash
querri view new --name "Orders" --sql "SELECT * FROM orders"
```

Running `querri view new` with no flags drops into interactive mode, prompting for name, SQL, description, and AI prompt (all optional). At least one of `--prompt` or `--sql` is required.

### Iterating with `view chat`

After a view exists, continue the AI conversation to refine its SQL:

```bash
querri view chat <UUID> -m "join customers with orders by customer_id"
querri view chat <UUID> -m "add a filter for active customers only"
```

### Other view commands

```bash
querri view list                                   # list all views
querri view get <uuid>                             # view details
querri view update <uuid> --sql "..."              # update SQL definition
querri view preview <uuid>                         # preview rows without materializing
querri view run [--view-ids <uuid,uuid>]         # materialize (omit for full DAG)
querri view delete <uuid>                          # delete
```

## Sources

A source is a connected data set — either ingested from a file or synced from a connector. Sources are the raw inputs that projects and views query over.

```bash
querri source list [--search TEXT]                 # list all sources
querri source get <source_id>                     # source detail
querri source describe <source_id>                # schema: columns, types, row count
querri source data <source_id>                    # preview paginated row data
querri source query --source-id ID --sql SQL      # run SQL against source
querri source ask <source_id> "question"          # NL question on source
querri source new --name "X" --file f.json          # create source from JSON file
querri source update <source_id> --name "..."     # update config
querri source sync <source_id>                    # trigger sync
querri source delete <source_id>                  # delete
querri source connectors                          # list available connector types
```

`source new` reads a JSON array of objects from `--file` or stdin.

**Important — `source query` table name**: The source data is registered in DuckDB as a view
called `data`. Always write `FROM data` in your SQL:

```bash
querri source query --source-id <ID> --sql "SELECT * FROM data LIMIT 10"
querri source query --source-id <ID> --sql "SELECT col1, COUNT(*) FROM data GROUP BY col1"
```

Using any other table name (e.g. `FROM source`, `FROM contacts`) will return HTTP 400.

## Dashboards

```bash
querri dashboard list
querri dashboard get <dashboard_id>
querri dashboard new --name "Name" --project <id>
querri dashboard update <id> --name "..."
querri dashboard refresh <id>                     # trigger refresh
querri dashboard refresh-status <id>
querri dashboard delete <id>
```

## Sharing & Access

```bash
# Projects
querri share project add <project_id> --user-id <user_id> [--permission view]
querri share project remove <project_id> <user_id>
querri share project list <project_id>

# Dashboards
querri share dashboard add <dashboard_id> --user-id <user_id> [--permission view]
querri share dashboard remove <dashboard_id> <user_id>
querri share dashboard list <dashboard_id>

# Sources
querri share source add <source_id> --user-id <user_id> [--permission view]
querri share source remove <source_id> <user_id>
querri share source list <source_id>
querri share source org <source_id> [--permission view]   # share with entire org
```

## API Keys

```bash
querri key list
querri key get <key_id>
querri key new --name "My Key" --scopes "admin:projects:read,admin:projects:write"
querri key delete <key_id>
```

Scopes follow `admin:<resource>:<action>` pattern. Common scopes:
- `admin:projects:read` / `admin:projects:write`
- `admin:files:read` / `admin:files:write`
- `admin:sources:read` / `admin:sources:write`
- `admin:chats:read` / `admin:chats:write`

## Users

```bash
querri user list
querri user get <user_id>
querri user new --email "user@example.com" --first-name "..." --last-name "..."
querri user update <user_id> --role admin --first-name "..."
querri user delete <user_id>
```

## Access Policies (Row-Level Security)

```bash
querri policy list
querri policy get <policy_id>
querri policy new --name "Region Filter" --source-ids <source_id> --row-filters '[...]'
querri policy update <id> --name "..." --source-ids "..." --row-filters '[...]'
querri policy assign <policy_id> --user-ids <user_id1,user_id2>
querri policy remove <policy_id> <user_id>
querri policy resolve --user-id <user_id> --source-id <source_id>  # effective access
querri policy columns [--source-id <source_id>]                    # available columns
querri policy delete <id>
```

## Embedded Analytics (Sessions)

```bash
querri session new --user-id <user_id> [--origin <url>] [--ttl 3600]
querri session list
querri session get --user <user_id>                # get-or-create convenience
querri session refresh --token <token>
querri session revoke --session-id <session_id>
```

## Administration

```bash
querri usage org                                   # org-wide usage report
querri usage user <user_id>                        # per-user usage
querri audit list                                  # audit log events
querri audit list --action "project.create"        # filter by action
```

## Environment Variables

| Variable | Purpose |
|---|---|
| `QUERRI_API_KEY` | API key (preferred for scripting over stored JWT) |
| `QUERRI_HOST` | Server host (default: `https://app.querri.com`; locally: `http://localhost`) |
| `QUERRI_ORG_ID` | Organization ID override |
| `QUERRI_PROJECT_ID` | Active project override (same as `--project`) |
| `QUERRI_CHAT_ID` | Active chat override (same as `--chat`) |
| `QUERRI_USER_ID` | User ID for operations that require one |

## JSON Output Shape Reference

See `references/json-shapes.md` for the exact fields returned by each command.

## Troubleshooting

See `references/troubleshooting.md` for common issues and fixes.
