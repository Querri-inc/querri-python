# Workspaces

A workspace is the room your data lives in. It decides two things: who can see
an object by default, and what an agent searches when a question is asked from
inside it.

Both matter more than they sound. Asked "what is the total of the invoices?" in
an organization holding several unrelated databases, an unscoped question fans
out across all of them and opens with a number from whichever one sorted first.
Scoped to a workspace, the same question gets the answer you meant.

```
$ querri library ask "What is the total of the invoices?"
  scope: whole organization
  I found invoice totals across several different systems in your data...
  → "Airlines bookings: 20,766,980,900 ..."

$ querri workspace use finance
$ querri library ask "What is the total of the invoices?"
  scope: workspace workspace_7d85eac5...
  → "The total of all invoices is $2,328.60, from 412 invoices."
```

## Signed in, or an API key

Reading workspaces works either way: `querri workspace list` / `show` /
`members` (and `client.workspaces.list/get/members`) use the public
`/api/v1/workspaces` routes. A login sees the workspaces it can enter; an API
key sees every workspace in the organization.

Library creates (collections, questions, facts, KPIs) send the active workspace
as `workspace_id`, so an API key can home them too.

Uploads, projects, and `workspace new` / `add-member` / `move` still need a
signed-in user (`querri auth login`): under an API key the server has no
membership roster to check the claim against, and those creates land in the key
owner's personal workspace.

## Choosing one

```bash
querri workspace list              # the ones you can enter, default first
querri workspace use finance       # persists across commands
querri workspace show              # where am I?
querri workspace use --none        # "Everything": creates go to your personal
                                   # workspace, reads are unscoped
```

`--workspace/-w` overrides for a single command without changing what is stored:

```bash
querri -w sales source list
```

A slug, a name, or an id all work; the CLI resolves it to an id before sending
it. That resolution costs one extra call and is worth it — the server silently
ignores a claim it cannot match, so an unresolved slug would put your upload
somewhere you did not ask for and report success.

## Getting data in

```bash
querri workspace use finance
querri file upload 'data/*.csv' --wait --concurrency 4
```

`--wait` is the important flag. An upload returns as soon as the bytes land;
parsing happens afterwards on a queue, and the file is not queryable until it
finishes. On a real load those are minutes apart, so anything that uploads and
immediately queries is racing. `--wait` blocks until every file is usable and
exits non-zero if any failed, naming them.

To check a whole workspace rather than one upload:

```bash
querri source ready            # ready / processing / failed, for the current scope
querri source ready --wait     # block until nothing is processing
```

It exits 0 only when everything settled, so it composes:

```bash
querri source ready --wait && querri project chat -m "what changed this quarter?"
```

## Moving things

```bash
querri workspace move <source-id> [<source-id>...] --to finance
```

Re-homes uploaded files. Both copies of an item's home move together — the file
and its data source — so it cannot end up in two rooms depending on which
surface you arrive through. A move that would cross an ownership boundary needs
`--transfer-ownership`, so it can never silently hand your object to someone
else.

## Creating one

```bash
querri workspace new "Finance" --slug finance --use
querri workspace add-member user_01ABC --to finance --role member
```

Requires an organization admin. A new workspace is **private**: you are its only
member until you add people. That is deliberate — a workspace that defaulted to
org-visible would be a shared room nobody chose to share.

## From Python

```python
from querri import Querri

client = Querri(workspace_id="workspace_7d85eac5...")   # or QUERRI_WORKSPACE_ID

client.files.upload("q3.csv")                  # homed there
client.sources.wait_until_ready([...])         # per-source state, never raises
client.projects.create(name="Q3", user_id=...) # homed there
answer = client.library.ask(library_id=lib, question="...")
print(answer.workspace_id)                     # the scope it ANSWERED under
```

`client.workspaces` has `list`, `get` and `members` (public API, API keys
welcome), and `create`, `add_member` and `move` (app routes, login only). Each
workspace has a `kind`: `personal`, `named` or `company` (the org's shared one).

To share one item with a whole workspace without moving it, use
`client.sharing.share_workspace(resource_type, resource_id, workspace_id)` or
`querri share workspace add <type> <id> --to <workspace>`. Library nodes move
with `client.library.move_node(node_id, workspace_id)` /
`querri library move <id> --to <workspace>`.

## Two things worth knowing

**The claim is a hint the server may refuse.** Name a workspace you are not a
member of and homing falls closed to your personal workspace rather than
failing — you would otherwise lose access to the thing you just created. So
read the resolved answer (`file.workspace_id`, `AskResponse.workspace_id`)
rather than assuming the claim you sent was honoured.

**Scoping narrows what an agent searches, and it is not absolute.** When a
workspace holds very little that relates to the question, the planner may widen
to the organization rather than answer from nothing. Anything that reports a
scope tells you which happened.
