"""querri role — manage custom roles as code (export, edit, apply)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    EXIT_ERROR,
    handle_api_error,
    print_error,
    print_id,
    print_json,
    print_success,
    print_table,
)
from querri.types.role import RoleApplyResult

roles_app = typer.Typer(
    name="role",
    help=(
        "Manage custom roles as code: export a role to a JSON file, edit it,"
        " and apply it back (`apply --watch` re-applies on every save)."
        " Needs the admin:roles:read / admin:roles:write scopes."
    ),
    no_args_is_help=True,
)

#: Seconds between mtime checks in ``apply --watch``.
WATCH_INTERVAL = 1.0

_VALUE_WIDTH = 60


class DefinitionFileError(Exception):
    """The definitions file could not be read or has the wrong shape."""


# ---------------------------------------------------------------------------
# File + summary helpers
# ---------------------------------------------------------------------------


def load_definitions(path: Path) -> list[dict[str, Any]]:
    """Read role definitions from a JSON file.

    The file may hold one definition, a list of definitions, or
    ``{"roles": [...]}`` (what ``querri role export`` writes).

    Raises:
        DefinitionFileError: The file is missing, not JSON, or the wrong shape.
    """
    if path.suffix.lower() in {".yaml", ".yml"}:
        raise DefinitionFileError(
            f"{path}: YAML is not supported; save the role as JSON."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DefinitionFileError(f"{path}: {exc.strerror or exc}") from None
    except json.JSONDecodeError as exc:
        raise DefinitionFileError(f"{path}: invalid JSON: {exc}") from None

    if isinstance(data, dict) and "roles" in data and "key" not in data:
        data = data["roles"]
    items = data if isinstance(data, list) else [data]
    if not items:
        raise DefinitionFileError(f"{path}: no role definitions found.")
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise DefinitionFileError(
                f"{path}: role #{i + 1} is not a JSON object."
            )
        if not isinstance(item.get("key"), str) or not item["key"]:
            raise DefinitionFileError(f"{path}: role #{i + 1} has no 'key'.")
    return items


def _fmt(value: Any) -> str:
    text = json.dumps(value, default=str, sort_keys=True)
    if len(text) > _VALUE_WIDTH:
        text = text[: _VALUE_WIDTH - 3] + "..."
    return text


def _list_delta(before: list[Any], after: list[Any]) -> str:
    added = [f"+{v}" for v in after if v not in before]
    removed = [f"-{v}" for v in before if v not in after]
    return " ".join(added + removed) or "(reordered)"


def summarize_change(field: str, before: Any, after: Any) -> list[str]:
    """Describe one field change as compact human-readable fragments.

    Lists show ``+added -removed``; dicts are compared one key deep
    (``config.home_chat: "chat" -> "project"``); scalars show ``old -> new``.
    """
    if isinstance(before, list) or isinstance(after, list):
        return [f"{field}: {_list_delta(before or [], after or [])}"]
    if isinstance(before, dict) or isinstance(after, dict):
        b = before if isinstance(before, dict) else {}
        a = after if isinstance(after, dict) else {}
        out = []
        for key in sorted(set(b) | set(a), key=str):
            if b.get(key) == a.get(key) and (key in b) == (key in a):
                continue
            if key not in a:
                out.append(f"-{field}.{key}")
            elif key not in b:
                out.append(f"+{field}.{key}={_fmt(a[key])}")
            else:
                out.append(f"{field}.{key}: {_fmt(b[key])} -> {_fmt(a[key])}")
        return out or [f"{field}: changed"]
    return [f"{field}: {_fmt(before)} -> {_fmt(after)}"]


def format_result(result: RoleApplyResult) -> str:
    """One line per applied role: key, action, and what changed."""
    line = f"{result.key}: {result.action}"
    if result.failed and result.error is not None:
        detail = result.error.message or result.error.code
        code = f" [{result.error.code}]" if result.error.code else ""
        return f"{line}{code} {detail}".rstrip()
    parts: list[str] = []
    for change in result.changes:
        parts.extend(summarize_change(change.field, change.before, change.after))
    return f"{line}  {'; '.join(parts)}" if parts else line


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@roles_app.command("list")
def list_roles(ctx: typer.Context) -> None:
    """List every role, system roles included."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        roles = client.roles.list()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json([r.model_dump(mode="json", by_alias=True) for r in roles])
    elif obj.get("quiet"):
        for r in roles:
            print_id(r.key)
    else:
        rows = [
            {
                "key": r.key,
                "name": r.name,
                "base": r.base,
                "enabled": "yes" if r.enabled else "no",
                "users": r.user_count,
                "system": "yes" if r.system else "",
            }
            for r in roles
        ]
        print_table(
            rows,
            [
                ("key", "Key"),
                ("name", "Name"),
                ("base", "Base"),
                ("enabled", "Enabled"),
                ("users", "Users"),
                ("system", "System"),
            ],
            ctx=ctx,
        )


@roles_app.command("get")
def get_role(
    ctx: typer.Context,
    ref: str = typer.Argument(..., help="Role key or ID."),
) -> None:
    """Print a role's definition as JSON, ready to redirect to a file.

    Output-only fields (id, user count, ...) are left out, so the output
    re-applies cleanly with `querri role apply -f`.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        role = client.roles.get(ref)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    print_json(role.to_definition())


@roles_app.command("export")
def export_roles(
    ctx: typer.Context,
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write to this file instead of stdout."
    ),
    include_system: bool = typer.Option(
        False,
        "--include-system",
        help="Include the built-in roles (they cannot be applied).",
    ),
) -> None:
    """Export roles as {"roles": [...]} JSON (custom roles only by default).

    JSON only: YAML is not supported, since the SDK does not depend on PyYAML.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        definitions = client.roles.export(include_system=include_system)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    document = {"roles": definitions}
    if output is None:
        print_json(document)
        return
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print_success(f"Exported {len(definitions)} role(s) to {output}")


def _apply_once(
    ctx: typer.Context, path: Path, *, dry_run: bool
) -> int:
    """Apply the file once and print the results. Returns an exit code."""
    obj = ctx.ensure_object(dict)
    try:
        definitions = load_definitions(path)
    except DefinitionFileError as exc:
        print_error(str(exc))
        return EXIT_ERROR

    client = get_client(ctx)
    try:
        if len(definitions) == 1:
            results = [client.roles.apply(definitions[0], dry_run=dry_run)]
        else:
            results = client.roles.import_roles(definitions, dry_run=dry_run).results
    except Exception as exc:
        return handle_api_error(exc, is_json=obj.get("json"))

    if obj.get("json"):
        print_json([r.model_dump(mode="json", by_alias=True) for r in results])
    else:
        for result in results:
            print(format_result(result))
    return EXIT_ERROR if any(r.failed for r in results) else 0


def watch_file(
    path: Path,
    on_change: Callable[[], object],
    *,
    interval: float = WATCH_INTERVAL,
    sleep: Callable[[float], None] | None = None,
) -> None:
    """Call ``on_change`` whenever ``path``'s mtime changes, until Ctrl-C.

    A missing file (mid-save by some editors) is waited out, not an error.
    """

    def _mtime() -> int | None:
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return None

    pause = sleep or time.sleep
    last = _mtime()
    while True:
        pause(interval)
        current = _mtime()
        if current is not None and current != last:
            last = current
            on_change()


@roles_app.command("apply")
def apply_roles(
    ctx: typer.Context,
    file: Path = typer.Option(
        ...,
        "--file",
        "-f",
        help=(
            "JSON file with one definition, a list, or {\"roles\": [...]}."
            " YAML is not supported."
        ),
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would change; write nothing."
    ),
    watch: bool = typer.Option(
        False,
        "--watch",
        "-w",
        help="Re-apply every time the file is saved (Ctrl-C to stop).",
    ),
) -> None:
    """Create or update roles from a definition file (idempotent).

    One definition is applied with PUT /roles/{key}; several with one import
    call, where each role succeeds or fails on its own. Exits non-zero when
    any role failed.
    """
    code = _apply_once(ctx, file, dry_run=dry_run)
    if not watch:
        raise typer.Exit(code=code)

    print_success(f"Watching {file} for changes (Ctrl-C to stop)")

    def _reapply() -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {file} changed")
        _apply_once(ctx, file, dry_run=dry_run)

    try:
        watch_file(file, _reapply)
    except KeyboardInterrupt:
        raise typer.Exit(code=0) from None


@roles_app.command("delete")
def delete_role(
    ctx: typer.Context,
    ref: str = typer.Argument(..., help="Role key or ID."),
    reassign_to: str | None = typer.Option(
        None,
        "--reassign-to",
        help="Role key to give people who hold this role as their only role.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation."),
) -> None:
    """Delete a custom role."""
    obj = ctx.ensure_object(dict)
    if not yes and not typer.confirm(f"Delete role {ref}?", default=False):
        print_error("Aborted.")
        raise typer.Exit(code=EXIT_ERROR)
    client = get_client(ctx)
    try:
        resp = client.roles.delete(ref, reassign_to=reassign_to)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json(resp)
    else:
        print_success(f"Deleted role {resp.deleted}")


@roles_app.command("catalog")
def catalog(
    ctx: typer.Context,
    area: str | None = typer.Option(None, "--area", help="Only this area."),
) -> None:
    """List the permission keys roles can grant or deny."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        cat = client.roles.catalog()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    perms = [p for p in cat.permissions if area is None or p.area == area]
    if obj.get("json"):
        print_json([p.model_dump(mode="json") for p in perms])
        return
    if obj.get("quiet"):
        for p in perms:
            print_id(p.key)
        return

    def _default(value: Any) -> str:
        if isinstance(value, bool):
            return "yes" if value else "no"
        return "" if value is None else str(value)

    rows = [
        {
            "key": p.key,
            "area": p.area,
            "kind": p.kind,
            "guest": _default(p.defaults.get("guest")),
            "creator": _default(p.defaults.get("creator")),
            "admin": _default(p.defaults.get("admin")),
            "requires": p.requires,
        }
        for p in perms
    ]
    print_table(
        rows,
        [
            ("key", "Key"),
            ("area", "Area"),
            ("kind", "Kind"),
            ("guest", "Guest"),
            ("creator", "Creator"),
            ("admin", "Admin"),
            ("requires", "Requires"),
        ],
        ctx=ctx,
    )
