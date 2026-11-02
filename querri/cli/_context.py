"""CLI context helpers — construct SDK clients from CLI args and env vars."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any

import typer

if TYPE_CHECKING:
    from querri._auth import TokenProfile

from querri._client import Querri
from querri._exceptions import ConfigError


def _as_cli(client: Querri) -> Querri:
    """Mark a client as built by the CLI, so its requests say ``cli/<ver>``.

    The HTTP client already holds its headers by the time ``Querri()`` returns,
    so the header is updated alongside the config it was derived from.
    """
    client._config.client_kind = "cli"
    client._http._client.headers["X-Querri-Client"] = client._config.client_header
    return client


# A workspace id is minted server-side as `workspace_<hex>` (named),
# `workspace_user_<uid>` (personal), or the literal `repo_default` (the org's
# shared Library). Anything else the user typed is a slug or a name, and gets
# looked up rather than sent as-is — an unrecognized claim fails CLOSED to the
# personal workspace on the server, which would silently put your upload
# somewhere you did not ask for.
def _looks_like_workspace_id(value: str) -> bool:
    return value == "repo_default" or value.startswith("workspace_")


def _resolve_workspace(client: Querri, value: str, obj: dict[str, Any]) -> str:
    """Turn a workspace id, slug, or name into an id. Exits 1 if unknown."""
    if _looks_like_workspace_id(value):
        return value
    needle = value.strip().lower()
    try:
        candidates = client.workspaces.list()
    except Exception as exc:  # noqa: BLE001 — report, never guess
        from querri.cli._output import print_error

        print_error(f"Could not look up workspace {value!r}: {exc}")
        raise typer.Exit(code=1) from None
    for ws in candidates:
        if str(ws.get("slug", "")).lower() == needle:
            return str(ws["id"])
    for ws in candidates:
        if str(ws.get("name", "")).lower() == needle:
            return str(ws["id"])

    known = ", ".join(f"{w.get('slug')} ({w.get('name')})" for w in candidates)
    if obj.get("json"):
        from querri.cli._output import print_json_error

        print_json_error(
            "unknown_workspace",
            f"No workspace matches {value!r}. Available: {known}",
            1,
        )
    else:
        from querri.cli._output import print_error

        print_error(
            f"No workspace matches {value!r}.\n"
            f"  Available: {known}\n"
            f"  querri workspace list"
        )
    raise typer.Exit(code=1)


def _active_workspace(ctx: typer.Context) -> str | None:
    """The workspace claim for this invocation: --workspace / env, else the one
    `querri workspace use` stored. Returned verbatim — may be a slug."""
    obj: dict[str, Any] = ctx.ensure_object(dict)
    flag = obj.get("workspace")
    if flag:
        return str(flag)
    try:
        profile = _get_profile(ctx)
    except Exception:
        return None
    if profile is not None and profile.active_workspace_id:
        return str(profile.active_workspace_id)
    return None


def get_client(ctx: typer.Context) -> Querri:
    """Construct a Querri client from CLI context options.

    Credential resolution order:
    1. Explicit ``--api-key`` flag (wins)
    2. Environment variables (``QUERRI_API_KEY``, ``QUERRI_ACCESS_TOKEN``)
    3. Token store (``~/.querri/tokens.json`` — active profile, auto-refresh)
    4. Error with guidance

    The active workspace (``--workspace``, ``QUERRI_WORKSPACE_ID``, or whatever
    ``querri workspace use`` stored) rides along on every request as
    ``X-Querri-Workspace``: it homes what you create and scopes what you read.
    A slug or name is resolved to an id first — one extra call, worth it because
    the server silently ignores a claim it cannot match, so an unresolved slug
    would put your upload somewhere you did not ask for and report success.

    Returns:
        Configured ``Querri`` client instance.

    Raises:
        typer.Exit: With code 2 on authentication/config errors.
    """
    obj: dict[str, Any] = ctx.ensure_object(dict)

    api_key = obj.get("api_key")
    org_id = obj.get("org_id")
    host = obj.get("host")
    workspace = _active_workspace(ctx)

    # Build closures over the credential source we settled on, so the
    # workspace-resolving second pass constructs an identical client.
    build: Any = None
    if api_key:
        def build(ws: str | None) -> Querri:  # noqa: F811
            return Querri(api_key=api_key, org_id=org_id, host=host, workspace_id=ws)
    elif os.environ.get("QUERRI_API_KEY") or os.environ.get("QUERRI_ACCESS_TOKEN"):
        def build(ws: str | None) -> Querri:  # noqa: F811
            return Querri(org_id=org_id, host=host, workspace_id=ws)
    else:
        # Token store — load active profile, auto-refresh if needed
        try:
            from querri._auth import TokenStore, needs_refresh, refresh_tokens
            from querri._config import DEFAULT_HOST

            profile_name = obj.get("profile") or "default"
            store = TokenStore.load()
            profile = store.profiles.get(profile_name)

            if profile and profile.access_token:
                # Host: CLI flag, env, the profile's (from login), or default
                resolved_host = (
                    host
                    or os.environ.get("QUERRI_HOST")
                    or profile.host
                    or DEFAULT_HOST
                )

                # Auto-refresh if near expiry
                if needs_refresh(profile):
                    try:
                        profile = refresh_tokens(profile, resolved_host)
                        store.save_profile(profile_name, profile)
                    except Exception:
                        # Refresh failed (RuntimeError, timeout, network error, etc.)
                        # but the token may still be valid — needs_refresh fires
                        # early as a buffer. Fall through to use it anyway.
                        pass

                _token = profile.access_token
                _org = profile.org_id or org_id

                def build(ws: str | None) -> Querri:  # noqa: F811
                    return Querri(
                        access_token=_token,
                        org_id=_org,
                        host=resolved_host,
                        workspace_id=ws,
                    )
        except Exception as exc:
            # Token store error — print debug info in verbose mode and fall through
            if obj.get("verbose"):
                print(f"Token store error: {exc}", file=sys.stderr)

    if build is None:
        _handle_config_error(
            obj,
            ConfigError(
                "No credentials found. Run 'querri auth login' or set QUERRI_API_KEY."
            ),
        )
        raise typer.Exit(code=2)

    known_id = bool(workspace) and _looks_like_workspace_id(str(workspace))
    try:
        client = build(str(workspace) if known_id else None)
    except ConfigError as exc:
        _handle_config_error(obj, exc)
        raise typer.Exit(code=2) from None

    if workspace and not known_id:
        resolved = _resolve_workspace(client, str(workspace), obj)
        client.close()
        client = build(resolved)
    return _as_cli(client)


def _handle_config_error(obj: dict[str, Any], exc: ConfigError) -> None:
    """Print a user-friendly config error message."""
    is_json = obj.get("json", False)

    if is_json:
        import json

        error_obj = {
            "error": "auth_failed",
            "message": str(exc),
            "hint": "Run 'querri auth login' or set QUERRI_API_KEY and QUERRI_ORG_ID "
            "environment variables.",
            "code": 2,
            "exit_code": 2,
        }
        print(json.dumps(error_obj))
    else:
        from querri.cli._output import print_error

        print_error(str(exc))
        print(
            "\nTo get started:\n"
            "  querri auth login            # Browser-based login\n"
            "  export QUERRI_API_KEY=qk_...  # API key auth\n"
            "  export QUERRI_ORG_ID=org_...\n"
            "\nOr pass them as flags:\n"
            "  querri --api-key qk_... --org-id org_... <command>",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Workspace state helpers
# ---------------------------------------------------------------------------


def _get_profile(ctx: typer.Context) -> TokenProfile | None:
    """Load the active TokenProfile (or None)."""
    from querri._auth import TokenStore

    obj = ctx.ensure_object(dict)
    profile_name = obj.get("profile") or "default"
    store = TokenStore.load()
    return store.profiles.get(profile_name)


def _save_profile(ctx: typer.Context, profile: "TokenProfile") -> None:
    """Persist updates to the active TokenProfile."""
    from querri._auth import TokenStore

    obj = ctx.ensure_object(dict)
    profile_name = obj.get("profile") or "default"
    store = TokenStore.load()
    store.save_profile(profile_name, profile)


def resolve_project_id(ctx: typer.Context) -> str:
    """Resolve project ID from --project flag → stored state → error."""
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    # 1. Explicit --project flag
    project: str | None = obj.get("project")
    if project:
        return project

    # 2. Stored active project
    profile = _get_profile(ctx)
    if profile and profile.active_project_id:
        return str(profile.active_project_id)

    # 3. Error
    from querri.cli._output import print_error

    if is_json:
        from querri.cli._output import print_json_error

        print_json_error(
            "no_project",
            "No active project. Run 'querri project select <name>' or pass --project.",
            1,
        )
    else:
        print_error(
            "No active project.\n"
            "  querri project select <name>   # Set active project\n"
            "  querri project new             # Create a new project\n"
            "  --project <id>                 # Pass explicitly"
        )
    raise typer.Exit(code=1)


def resolve_user_id(ctx: typer.Context) -> str:
    """Resolve user ID from env → stored profile → error."""
    env_user = os.environ.get("QUERRI_USER_ID")
    if env_user:
        return env_user

    profile = _get_profile(ctx)
    if profile and profile.user_id:
        return str(profile.user_id)

    obj = ctx.ensure_object(dict)
    from querri.cli._output import print_error

    if obj.get("json"):
        from querri.cli._output import print_json_error

        print_json_error("no_user_id", "Could not determine user ID.", 1)
    else:
        print_error(
            "Could not determine user ID. "
            "Set QUERRI_USER_ID or log in with "
            "'querri auth login'."
        )
    raise typer.Exit(code=1)
