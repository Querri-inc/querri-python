"""CLI context helpers — construct SDK clients from CLI args and env vars."""

from __future__ import annotations

import os
import sys
from typing import Any

import typer

from querri._client import Querri
from querri._exceptions import ConfigError


def get_client(ctx: typer.Context) -> Querri:
    """Construct a Querri client from CLI context options.

    Resolution order:
    1. Explicit ``--api-key`` flag (wins)
    2. Environment variables (``QUERRI_API_KEY``, ``QUERRI_ACCESS_TOKEN``)
    3. Token store (``~/.querri/tokens.json`` — active profile, auto-refresh)
    4. Error with guidance

    Returns:
        Configured ``Querri`` client instance.

    Raises:
        typer.Exit: With code 2 on authentication/config errors.
    """
    obj: dict[str, Any] = ctx.ensure_object(dict)

    # 1. Explicit --api-key wins
    api_key = obj.get("api_key")
    org_id = obj.get("org_id")
    host = obj.get("host")

    if api_key:
        try:
            return Querri(api_key=api_key, org_id=org_id, host=host)
        except ConfigError as exc:
            _handle_config_error(obj, exc)
            raise typer.Exit(code=2) from None

    # 2. Environment variables — let resolve_config handle them
    if os.environ.get("QUERRI_API_KEY") or os.environ.get("QUERRI_ACCESS_TOKEN"):
        try:
            return Querri(org_id=org_id, host=host)
        except ConfigError as exc:
            _handle_config_error(obj, exc)
            raise typer.Exit(code=2) from None

    # 3. Token store — load active profile, auto-refresh if needed
    try:
        from querri._auth import TokenStore, needs_refresh, refresh_tokens
        from querri._config import DEFAULT_HOST

        profile_name = obj.get("profile") or "default"
        store = TokenStore.load()
        profile = store.profiles.get(profile_name)

        if profile and profile.access_token:
            # Use the host stored in the profile (from login), CLI flag, env, or default
            resolved_host = (
                host or os.environ.get("QUERRI_HOST") or profile.host or DEFAULT_HOST
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

            return Querri(
                access_token=profile.access_token,
                org_id=profile.org_id or org_id,
                host=resolved_host,
            )
    except Exception as exc:
        # Token store error — print debug info in verbose mode and fall through
        if obj.get("verbose"):
            print(f"Token store error: {exc}", file=sys.stderr)
        pass

    # 4. Nothing worked
    _handle_config_error(
        obj,
        ConfigError(
            "No credentials found. Run 'querri auth login' or set QUERRI_API_KEY."
        ),
    )
    raise typer.Exit(code=2)


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


def _get_profile(ctx: typer.Context) -> TokenProfile | None:  # noqa: F821
    """Load the active TokenProfile (or None)."""
    from querri._auth import TokenStore

    obj = ctx.ensure_object(dict)
    profile_name = obj.get("profile") or "default"
    store = TokenStore.load()
    return store.profiles.get(profile_name)


def _save_profile(ctx: typer.Context, profile: TokenProfile) -> None:  # noqa: F821
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
    project = obj.get("project")
    if project:
        return project

    # 2. Stored active project
    profile = _get_profile(ctx)
    if profile and profile.active_project_id:
        return profile.active_project_id

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
        return profile.user_id

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
