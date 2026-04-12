---
name: querri-cli
description: Work with the Querri data analysis platform via the querri CLI. Use this skill whenever the user wants to interact with Querri — creating or managing projects, uploading files, loading data sources, running analysis via chat, managing dashboards, sharing resources, handling API keys, managing users, working with access policies, embedded analytics, or any other Querri CLI operation. Also use when debugging Querri CLI issues, scripting automation against the Querri API, or exploring what the querri command can do.
---

# Querri CLI Skill

Querri is a data analysis platform. The `querri` CLI (`~/.local/bin/querri`, v0.2.0) talks to the Querri API. The SDK source lives at `~/paperclip/querri-python-sdk` and is installed in editable mode — code changes there take effect immediately.

## Critical: Global Flags Must Come First

`--json`, `--no-interactive`, `--project`, and `--chat` are **global flags** and must appear **before** the subcommand:

```bash
querri --json project list          # correct
querri project list --json          # WRONG — will error
querri --no-interactive chat ...    # correct
```

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
querri --json chat -p "What are the top 5 products by revenue?"
```

### 2. Non-interactive / scripted use

Always pass `--no-interactive` to prevent prompts and `--json` for parseable output:

```bash
FILE_ID=$(querri --json --no-interactive file upload data.csv | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
PROJ_ID=$(querri --json --no-interactive project new "Automated Analysis" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
querri --json --no-interactive --project "$PROJ_ID" project add-source "$FILE_ID"
querri --json --no-interactive --project "$PROJ_ID" chat -p "Summarize the data"
```

### 3. Work with an existing project

```bash
querri --json project list                         # list all projects
querri project select "My Analysis"                # fuzzy-match by name, set active
querri --json --project <id> chat -p "..."         # use specific project without selecting
```

## The `-p` Flag Collision

`-p` means `--project` at the global level, but `--prompt` inside `chat`. When using both in the same command, use the full form for one of them:

```bash
# Correct: global --project (long form) + chat -p (short form for prompt)
querri --json --no-interactive --project "$PROJ_ID" chat -p "my question"
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

```bash
querri chat -p "What is the average revenue by region?"   # send prompt
querri chat -p "..." --new                                  # force new chat session
querri chat -p "..." --model fast                          # model selection
querri chat -p "..." --reasoning                           # show reasoning traces
querri chat show                                            # show full conversation
querri chat cancel                                          # cancel active stream
```

Chat responses include `message_id`, `text` (the AI response), `tool_calls` (analysis steps run), `files` (any generated files), and `reasoning`.

## Sources

```bash
querri source list [--search TEXT]                 # list all sources
querri source get <source_id>                     # source detail
querri source describe <source_id>                # schema: columns, types, row count
querri source data <source_id>                    # preview row data
querri source query --source-id ID --sql SQL      # run SQL against source
querri source ask <source_id> "question"          # NL question on source
querri source create-data --name "X" --file f.json # create from JSON
querri source update <source_id> --name "..."     # update config
querri source sync <source_id>                    # trigger sync
querri source delete <source_id>                  # delete
querri source connectors                          # list available connector types
```

## Dashboards

```bash
querri dashboard list
querri dashboard get <dashboard_id>
querri dashboard create --name "Name" --project <id>
querri dashboard update <id> --name "..."
querri dashboard refresh <id>                     # trigger refresh
querri dashboard refresh-status <id>
querri dashboard delete <id>
```

## Sharing & Access

```bash
# Share with a specific user
querri share share-project <project_id> <user_id> --role viewer  # viewer|editor|owner
querri share revoke-project <project_id> <user_id>
querri share list-project <project_id>

# Same pattern for dashboards and sources
querri share share-dashboard <dashboard_id> <user_id> --role viewer
querri share share-source <source_id> <user_id>
querri share org-share-source <source_id>         # share with entire org
```

## API Keys

```bash
querri key list
querri key get <key_id>
querri key create --name "My Key" --scopes "admin:projects:read,admin:projects:write"
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
querri user create --email "user@example.com" --first-name "..." --last-name "..."
querri user delete <user_id>
```

## Access Policies (Row-Level Security)

```bash
querri policy list
querri policy get <policy_id>
querri policy create --name "Region Filter" --source <source_id> --condition "region = '{user.email}'"
querri policy update <id> --condition "..."
querri policy assign <policy_id> <user_id>
querri policy remove <policy_id> <user_id>
querri policy resolve <user_id> <source_id>       # effective access for a user
querri policy columns <source_id>                  # available columns for policy
querri policy delete <id>
```

## Embedded Analytics

```bash
querri embed create-session --user-id <id> --project <project_id>
querri embed get-session --user-id <id>            # get-or-create convenience
querri embed refresh-session <session_id>
querri embed list-sessions
querri embed revoke-session <session_id>
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
