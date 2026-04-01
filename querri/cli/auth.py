"""querri auth -- Manage authentication."""

from __future__ import annotations

import sys
from typing import Optional

import typer

from querri._auth import (
    TokenStore,
    TokenProfile,
    needs_refresh,
    refresh_tokens,
    start_oauth_flow,
)
from querri._config import DEFAULT_HOST
from querri.cli._output import (
    print_error,
    print_json,
    print_success,
    exit_auth_error,
)

auth_app = typer.Typer(
    help="Manage authentication (login, logout, token management).",
    no_args_is_help=True,
)


def _get_host(ctx: typer.Context) -> str:
    """Resolve the host from CLI context or default."""
    obj = ctx.ensure_object(dict)
    return obj.get("host") or DEFAULT_HOST


def _get_profile_name(ctx: typer.Context) -> str:
    """Resolve the profile name from CLI context or default."""
    obj = ctx.ensure_object(dict)
    return obj.get("profile") or "default"


def _is_json(ctx: typer.Context) -> bool:
    obj = ctx.ensure_object(dict)
    return obj.get("json", False)


# ---------------------------------------------------------------------------
# querri auth login
# ---------------------------------------------------------------------------


@auth_app.command()
def login(
    ctx: typer.Context,
    host: Optional[str] = typer.Option(
        None, "--host", "-h",
        help="Querri server URL (default: from global --host or QUERRI_HOST).",
    ),
    organization: Optional[str] = typer.Option(
        None, "--organization", "--org",
        help="WorkOS organization ID to scope the login to (e.g. org_01J...).",
    ),
) -> None:
    """Authenticate with Querri via browser-based OAuth.

    Opens your browser to sign in, then stores credentials locally
    in ``~/.querri/tokens.json``.

    Use --organization to scope the login to a specific organization,
    e.g. ``querri auth login --host http://localhost --organization org_01JBETJ7PYNGXVMXV0BD3CFNA8``
    """
    host = host or _get_host(ctx)
    profile_name = _get_profile_name(ctx)
    is_json = _is_json(ctx)

    # Check if already logged in
    store = TokenStore.load()
    existing = store.profiles.get(profile_name)
    if existing and existing.access_token and not needs_refresh(existing):
        if is_json:
            print_json({
                "status": "already_authenticated",
                "user_email": existing.user_email,
                "org_id": existing.org_id,
                "expires_at": existing.expires_at,
            })
        else:
            print(
                f"Already logged in as {existing.user_email}. "
                "Use 'querri auth logout' first to re-authenticate.",
                file=sys.stderr,
            )
        return

    # Run OAuth flow
    try:
        result = start_oauth_flow(host, organization_id=organization)
    except RuntimeError as exc:
        print_error(str(exc))
        raise typer.Exit(code=2)  # noqa: B904

    # Save profile
    profile = TokenProfile(
        auth_type="jwt",
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_at=result["expires_at"],
        org_id=result["org_id"],
        org_name=result.get("org_name", ""),
        user_email=result["user_email"],
        user_id=result["user_id"],
        user_name=result.get("user_name", ""),
        host=host,
    )
    store.active_profile = profile_name
    store.save_profile(profile_name, profile)

    if is_json:
        print_json({
            "user_id": result["user_id"],
            "email": result["user_email"],
            "name": result.get("user_name", ""),
            "org_id": result["org_id"],
            "org_name": result.get("org_name", ""),
            "expires_at": result["expires_at"],
        })
    else:
        identity = result.get("user_email") or result.get("user_id") or "unknown"
        name = result.get("user_name")
        if name:
            identity = f"{name} ({identity})"
        org_name = result.get("org_name")
        if org_name:
            identity = f"{identity} — {org_name}"
        print_success(f"Logged in as {identity}")


# ---------------------------------------------------------------------------
# querri auth logout
# ---------------------------------------------------------------------------


@auth_app.command()
def logout(ctx: typer.Context) -> None:
    """Log out and revoke stored credentials.

    Attempts server-side token revocation, then removes the local
    profile from the token store.
    """
    host = _get_host(ctx)
    profile_name = _get_profile_name(ctx)
    is_json = _is_json(ctx)

    store = TokenStore.load()
    profile = store.profiles.get(profile_name)

    if not profile:
        if is_json:
            print_json({"status": "not_authenticated"})
        else:
            print_error("Not currently logged in.")
        raise typer.Exit(code=0)  # noqa: B904

    # Attempt server-side revocation (best-effort)
    if profile.refresh_token:
        import httpx

        revoke_url = host.rstrip("/") + "/api/v1/auth/cli/revoke"
        try:
            httpx.post(
                revoke_url,
                json={"refresh_token": profile.refresh_token},
                timeout=10.0,
            )
        except Exception:
            # Best-effort — don't fail logout if revocation fails
            pass

    # Delete local profile
    try:
        store.delete_profile(profile_name)
    except KeyError:
        pass

    if is_json:
        print_json({"status": "logged_out"})
    else:
        print_success("Logged out successfully.")


# ---------------------------------------------------------------------------
# querri auth status
# ---------------------------------------------------------------------------


@auth_app.command()
def status(ctx: typer.Context) -> None:
    """Show current authentication status."""
    import os

    profile_name = _get_profile_name(ctx)
    is_json = _is_json(ctx)

    store = TokenStore.load()
    profile = store.profiles.get(profile_name)

    # Check stored tokens first
    if profile and profile.access_token:
        refresh_needed = needs_refresh(profile)
        org_display = profile.org_name or profile.org_id
        if profile.org_name and profile.org_id:
            org_display = f"{profile.org_name} ({profile.org_id})"

        info = {
            "source": "token_store",
            "profile": profile_name,
            "auth_type": profile.auth_type,
            "user_name": profile.user_name,
            "user_email": profile.user_email,
            "user_id": profile.user_id,
            "org_name": profile.org_name,
            "org_id": profile.org_id,
            "host": profile.host,
            "expires_at": profile.expires_at,
            "refresh_needed": refresh_needed,
        }
        if is_json:
            print_json(info)
        else:
            from querri.cli._output import print_detail

            print_detail(info, [
                ("profile", "Profile"),
                ("auth_type", "Auth Type"),
                ("user_name", "Name"),
                ("user_email", "Email"),
                ("org_name", "Organization"),
                ("org_id", "Org ID"),
                ("host", "Server"),
                ("expires_at", "Expires At"),
                ("refresh_needed", "Refresh Needed"),
            ])
        return

    # Check environment variables
    env_key = os.environ.get("QUERRI_API_KEY")
    env_token = os.environ.get("QUERRI_ACCESS_TOKEN")

    if env_key:
        # Redact key for display
        redacted = f"qk_***...{env_key[-4:]}" if len(env_key) > 4 else "qk_***"
        info = {
            "source": "environment",
            "auth_type": "api_key",
            "api_key": redacted,
            "org_id": os.environ.get("QUERRI_ORG_ID", ""),
        }
        if is_json:
            print_json(info)
        else:
            from querri.cli._output import print_detail

            print_detail(info, [
                ("source", "Source"),
                ("auth_type", "Auth Type"),
                ("api_key", "API Key"),
                ("org_id", "Organization"),
            ])
        return

    if env_token:
        info = {
            "source": "environment",
            "auth_type": "jwt",
            "access_token": "ey***",
        }
        if is_json:
            print_json(info)
        else:
            from querri.cli._output import print_detail

            print_detail(info, [
                ("source", "Source"),
                ("auth_type", "Auth Type"),
                ("access_token", "Access Token"),
            ])
        return

    # Not authenticated
    if is_json:
        print_json({
            "status": "not_authenticated",
            "hint": "Run 'querri auth login' or set QUERRI_API_KEY.",
        })
    else:
        print_error("Not authenticated.")
        print(
            "\nTo authenticate:\n"
            "  querri auth login          # Browser-based OAuth login\n"
            "  export QUERRI_API_KEY=qk_...  # API key auth",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# querri auth token
# ---------------------------------------------------------------------------


@auth_app.command()
def token(ctx: typer.Context) -> None:
    """Print the current access token to stdout.

    Refreshes the token automatically if it is near expiry.
    Intended for piping, e.g. ``querri auth token | pbcopy``.
    """
    host = _get_host(ctx)
    profile_name = _get_profile_name(ctx)

    store = TokenStore.load()
    profile = store.profiles.get(profile_name)

    if not profile or not profile.access_token:
        print_error("Not authenticated. Run 'querri auth login' first.")
        raise typer.Exit(code=2)  # noqa: B904

    # Auto-refresh if needed
    if needs_refresh(profile):
        try:
            profile = refresh_tokens(profile, host)
            store.save_profile(profile_name, profile)
        except RuntimeError as exc:
            print_error(str(exc))
            raise typer.Exit(code=2)  # noqa: B904

    # Print raw token — no formatting, no newline prefix
    sys.stdout.write(profile.access_token)
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# querri auth switch
# ---------------------------------------------------------------------------


@auth_app.command()
def switch(
    ctx: typer.Context,
    profile: str = typer.Argument(help="Profile name to switch to."),
) -> None:
    """Switch the active authentication profile."""
    is_json = _is_json(ctx)

    store = TokenStore.load()
    try:
        store.switch_profile(profile)
    except KeyError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)  # noqa: B904

    if is_json:
        print_json({"active_profile": profile})
    else:
        print_success(f"Switched to profile '{profile}'.")
