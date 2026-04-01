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
            raise typer.Exit(code=2)  # noqa: B904

    # 2. Environment variables — let resolve_config handle them
    if os.environ.get("QUERRI_API_KEY") or os.environ.get("QUERRI_ACCESS_TOKEN"):
        try:
            return Querri(org_id=org_id, host=host)
        except ConfigError as exc:
            _handle_config_error(obj, exc)
            raise typer.Exit(code=2)  # noqa: B904

    # 3. Token store — load active profile, auto-refresh if needed
    try:
        from querri._auth import TokenStore, needs_refresh, refresh_tokens
        from querri._config import DEFAULT_HOST

        profile_name = obj.get("profile") or "default"
        store = TokenStore.load()
        profile = store.profiles.get(profile_name)

        if profile and profile.access_token:
            # Use the host stored in the profile (from login), CLI flag, env, or default
            resolved_host = host or os.environ.get("QUERRI_HOST") or profile.host or DEFAULT_HOST

            # Auto-refresh if near expiry
            if needs_refresh(profile):
                try:
                    profile = refresh_tokens(profile, resolved_host)
                    store.save_profile(profile_name, profile)
                except RuntimeError:
                    # Refresh failed — clear stale profile and fall through to error
                    pass
                else:
                    return Querri(
                        access_token=profile.access_token,
                        org_id=profile.org_id or org_id,
                        host=resolved_host,
                    )
            else:
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
    _handle_config_error(obj, ConfigError(
        "No credentials found. Run 'querri auth login' or set QUERRI_API_KEY."
    ))
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
