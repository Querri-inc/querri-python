"""querri key — manage API keys."""

from __future__ import annotations

import sys

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    handle_api_error,
    print_detail,
    print_error,
    print_id,
    print_json,
    print_success,
    print_table,
)

# All available API key scopes, grouped for the interactive picker.
_SCOPE_GROUPS: list[tuple[str, list[str]]] = [
    ("Projects", ["admin:projects:read", "admin:projects:write"]),
    ("Dashboards", ["admin:dashboards:read", "admin:dashboards:write"]),
    ("Data", ["data:read", "data:write"]),
    ("Sources", ["admin:sources:read", "admin:sources:write"]),
    ("Files", ["admin:files:read", "admin:files:upload", "admin:files:delete"]),
    ("Users", ["admin:users:read", "admin:users:write"]),
    ("Keys", ["admin:keys:manage"]),
    ("Policies", ["admin:policies:read", "admin:policies:write"]),
    ("Permissions", ["admin:permissions:read", "admin:permissions:write"]),
    ("Embed", ["embed:session:create"]),
    ("Usage", ["admin:usage:read"]),
    ("Audit", ["admin:audit:read"]),
]


def _pick_scopes() -> list[str]:
    """Interactive scope picker with toggle-style checkboxes."""
    all_scopes: list[str] = []
    for _, group_scopes in _SCOPE_GROUPS:
        all_scopes.extend(group_scopes)

    selected: set[int] = set()

    def _render() -> None:
        print("\033[2J\033[H", end="", file=sys.stderr)  # clear screen
        print("Select scopes (enter number to toggle, 'a' for all, 'd' for done):\n", file=sys.stderr)
        idx = 1
        for group_name, group_scopes in _SCOPE_GROUPS:
            print(f"  {group_name}:", file=sys.stderr)
            for scope in group_scopes:
                flat_idx = all_scopes.index(scope)
                mark = "✓" if flat_idx in selected else " "
                print(f"    [{mark}] {idx:2d}. {scope}", file=sys.stderr)
                idx += 1
            print(file=sys.stderr)

    _render()
    while True:
        try:
            raw = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            raise typer.Exit(code=0)
        if raw == "d" or raw == "done":
            break
        if raw == "a" or raw == "all":
            if len(selected) == len(all_scopes):
                selected.clear()
            else:
                selected = set(range(len(all_scopes)))
            _render()
            continue
        try:
            num = int(raw)
            if 1 <= num <= len(all_scopes):
                idx = num - 1
                if idx in selected:
                    selected.discard(idx)
                else:
                    selected.add(idx)
            _render()
        except ValueError:
            _render()

    return [all_scopes[i] for i in sorted(selected)]


keys_app = typer.Typer(
    name="keys",
    help="Manage API keys for the organization.",
    no_args_is_help=True,
)


@keys_app.command("list")
def list_keys(
    ctx: typer.Context,
) -> None:
    """List API keys."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.keys.list()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json([k.model_dump(mode="json") for k in items])
    elif obj.get("quiet"):
        for k in items:
            print_id(k.id)
    else:
        print_table(
            items,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("key_prefix", "Prefix"),
                ("status", "Status"),
                ("last_used_at", "Last Used"),
                ("expires_at", "Expires"),
            ],
            ctx=ctx,
        )


@keys_app.command("get")
def get_key(
    ctx: typer.Context,
    key_id: str | None = typer.Argument(None, help="API key ID."),
) -> None:
    """Get API key details."""
    obj = ctx.ensure_object(dict)
    if not key_id:
        if sys.stdin.isatty():
            key_id = input("API key ID: ").strip()
            if not key_id:
                print_error("API key ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument KEY_ID. Usage: querri key get KEY_ID")
            raise typer.Exit(code=1)
    client = get_client(ctx)
    try:
        key = client.keys.get(key_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(key)
    elif obj.get("quiet"):
        print_id(key.id)
    else:
        print_detail(
            key,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("key_prefix", "Key Prefix"),
                ("scopes", "Scopes"),
                ("status", "Status"),
                ("rate_limit_per_minute", "Rate Limit"),
                ("bound_user_id", "Bound User"),
                ("ip_allowlist", "IP Allowlist"),
                ("access_policy_ids", "Policies"),
                ("created_by", "Created By"),
                ("created_at", "Created"),
                ("last_used_at", "Last Used"),
                ("expires_at", "Expires"),
            ],
        )


@keys_app.command("new")
def new_key(
    ctx: typer.Context,
    name: str | None = typer.Option(None, "--name", "-n", help="Key name."),
    scopes: str | None = typer.Option(None, "--scopes", "-s", help="Comma-separated scopes."),
    expires_in_days: int | None = typer.Option(None, "--expires-in-days", help="Days until expiry."),
    bound_user_id: str | None = typer.Option(None, "--bound-user-id", help="Bind key to a user ID."),
    rate_limit: int | None = typer.Option(None, "--rate-limit", help="Requests per minute."),
    ip_allowlist: str | None = typer.Option(None, "--ip-allowlist", help="Comma-separated IP allowlist."),
) -> None:
    """Create a new API key.

    The full key value is shown only once — save it immediately.
    """
    obj = ctx.ensure_object(dict)
    if not name:
        if sys.stdin.isatty():
            name = input("Key name: ").strip()
            if not name:
                print_error("Key name is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required option --name. Usage: querri key new --name NAME --scopes SCOPES [options]")
            raise typer.Exit(code=1)
    if not scopes:
        if sys.stdin.isatty():
            scope_list = _pick_scopes()
            if not scope_list:
                print_error("At least one scope is required.")
                raise typer.Exit(code=1)
        else:
            all_scopes = [s for _, group in _SCOPE_GROUPS for s in group]
            print_error(
                "Missing required option --scopes. "
                f"Usage: querri key new --name NAME --scopes SCOPES\n"
                f"Available scopes: {', '.join(all_scopes)}"
            )
            raise typer.Exit(code=1)
    else:
        scope_list = [s.strip() for s in scopes.split(",")]
    client = get_client(ctx)
    ip_list = [ip.strip() for ip in ip_allowlist.split(",")] if ip_allowlist else None

    try:
        key = client.keys.create(
            name=name,
            scopes=scope_list,
            expires_in_days=expires_in_days,
            bound_user_id=bound_user_id,
            rate_limit_per_minute=rate_limit,
            ip_allowlist=ip_list,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(key)
    elif obj.get("quiet"):
        # In quiet mode, output the bare secret for piping
        print(key.secret)
    else:
        from querri.cli._output import IS_INTERACTIVE

        print_success(f"Created API key: {key.name} ({key.id})")
        if IS_INTERACTIVE:
            from rich.console import Console
            from rich.panel import Panel

            console = Console(stderr=True)
            console.print(Panel(
                f"[bold]{key.secret}[/bold]",
                title="API Key Secret",
                subtitle="Save now — cannot be retrieved later",
                border_style="#f15a24",
                padding=(1, 2),
            ))
        else:
            print(f"Secret: {key.secret}", file=sys.stderr)
            print("Save this key now — it cannot be retrieved later.", file=sys.stderr)


@keys_app.command("delete")
def delete_key(
    ctx: typer.Context,
    key_id: str | None = typer.Argument(None, help="API key ID."),
) -> None:
    """Delete an API key."""
    obj = ctx.ensure_object(dict)
    if not key_id:
        if sys.stdin.isatty():
            key_id = input("API key ID: ").strip()
            if not key_id:
                print_error("API key ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument KEY_ID. Usage: querri key delete KEY_ID")
            raise typer.Exit(code=1)
    client = get_client(ctx)
    try:
        client.keys.delete(key_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"id": key_id, "deleted": True})
    else:
        print_success(f"Deleted API key {key_id}")
