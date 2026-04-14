"""querri auth -- Manage authentication."""

from __future__ import annotations

import contextlib
import sys

import typer

from querri._auth import (
    TokenProfile,
    TokenStore,
    needs_refresh,
    refresh_tokens,
    start_oauth_flow,
)
from querri._config import DEFAULT_HOST
from querri.cli._output import (
    print_error,
    print_json,
    print_success,
)

_PICK_ORG_HINT = "Tip: use --organization <org_id> to skip this prompt next time."

auth_app = typer.Typer(
    help="Manage authentication (login, logout, token management).",
    no_args_is_help=True,
    rich_markup_mode="rich",
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
    return bool(obj.get("json", False))


def _pick_organization(
    all_orgs: dict[str, str],
    *,
    current_org_id: str = "",
) -> tuple[str, str]:
    """Show an interactive org picker in the terminal.

    Returns:
        (org_id, org_name) tuple for the selected organization.
    """
    print("\nYou belong to multiple organizations:\n", file=sys.stderr)
    sorted_orgs = sorted(all_orgs.items(), key=lambda x: x[1].lower())
    for i, (org_id, org_name) in enumerate(sorted_orgs, 1):
        marker = " (current)" if org_id == current_org_id else ""
        print(f"  [{i}] {org_name}{marker}", file=sys.stderr)
    print(file=sys.stderr)

    # Find the default (current org's index)
    default_idx = 1
    for i, (org_id, _) in enumerate(sorted_orgs, 1):
        if org_id == current_org_id:
            default_idx = i
            break

    while True:
        try:
            raw = input(f"Select organization [{default_idx}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            raw = ""
        if not raw:
            raw = str(default_idx)
        try:
            choice = int(raw)
            if 1 <= choice <= len(sorted_orgs):
                selected_id, selected_name = sorted_orgs[choice - 1]
                print(f"\n  {_PICK_ORG_HINT}\n", file=sys.stderr)
                return selected_id, selected_name
        except ValueError:
            pass
        print(
            f"  Please enter a number between 1 and {len(sorted_orgs)}.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# querri auth login
# ---------------------------------------------------------------------------


@auth_app.command()
def login(
    ctx: typer.Context,
    host: str | None = typer.Option(
        None,
        "--host",
        "-h",
        help="Querri server URL (default: from global --host or QUERRI_HOST).",
    ),
    organization: str | None = typer.Option(
        None,
        "--organization",
        "--org",
        help="WorkOS organization ID to scope the login to (e.g. org_01J...).",
    ),
) -> None:
    """Authenticate with Querri via browser-based OAuth.

    Opens your browser to sign in, then stores credentials locally
    in ``~/.querri/tokens.json``.

    Use --organization to scope the login to a specific organization,
    e.g. ``querri auth login --host http://localhost``
    ``--organization org_01JBETJ7PYNGXVMXV0BD3CFNA8``
    """
    host = host or _get_host(ctx)
    if not host.startswith(("http://", "https://")):
        print_error(f"--host must include a scheme (e.g. https://{host}).")
        raise typer.Exit(code=2)
    profile_name = _get_profile_name(ctx)
    is_json = _is_json(ctx)

    # Check if already logged in
    store = TokenStore.load()
    existing = store.profiles.get(profile_name)
    if existing and existing.access_token and not needs_refresh(existing):
        if is_json:
            print_json(
                {
                    "status": "already_authenticated",
                    "user_email": existing.user_email,
                    "org_id": existing.org_id,
                    "expires_at": existing.expires_at,
                }
            )
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
        raise typer.Exit(code=2) from None

    all_orgs: dict[str, str] = result.get("all_organizations") or {}
    chosen_org_id = result["org_id"]
    chosen_org_name = result.get("org_name", "")

    # If the user didn't pass --organization and they belong to multiple orgs,
    # show a terminal picker so they can choose which org to work in.
    if not organization and len(all_orgs) > 1 and not is_json:
        chosen_org_id, chosen_org_name = _pick_organization(
            all_orgs,
            current_org_id=result["org_id"],
        )
        # If they picked a different org, refresh tokens scoped to that org
        if chosen_org_id != result["org_id"]:
            try:
                temp_profile = TokenProfile(
                    auth_type="jwt",
                    access_token=result["access_token"],
                    refresh_token=result["refresh_token"],
                    expires_at=result["expires_at"],
                    org_id=chosen_org_id,
                    org_name=chosen_org_name,
                    user_email=result["user_email"],
                    user_id=result["user_id"],
                    user_name=result.get("user_name", ""),
                    host=host,
                )
                temp_profile = refresh_tokens(
                    temp_profile,
                    host,
                    organization_id=chosen_org_id,
                )
                result["access_token"] = temp_profile.access_token
                result["refresh_token"] = temp_profile.refresh_token
                result["expires_at"] = temp_profile.expires_at
            except RuntimeError as exc:
                print_error(f"Failed to switch organization: {exc}")
                raise typer.Exit(code=2) from None

    # Save profile
    profile = TokenProfile(
        auth_type="jwt",
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_at=result["expires_at"],
        org_id=chosen_org_id,
        org_name=chosen_org_name,
        user_email=result["user_email"],
        user_id=result["user_id"],
        user_name=result.get("user_name", ""),
        host=host,
        all_organizations=all_orgs,
    )
    store.active_profile = profile_name
    store.save_profile(profile_name, profile)

    if is_json:
        print_json(
            {
                "user_id": result["user_id"],
                "email": result["user_email"],
                "name": result.get("user_name", ""),
                "org_id": chosen_org_id,
                "org_name": chosen_org_name,
                "expires_at": result["expires_at"],
            }
        )
    else:
        identity = result.get("user_email") or result.get("user_id") or "unknown"
        name = result.get("user_name")
        if name:
            identity = f"{name} ({identity})"
        if chosen_org_name:
            identity = f"{identity} — {chosen_org_name}"
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
        raise typer.Exit(code=0)

    # Attempt server-side revocation (best-effort)
    if profile.refresh_token:
        import httpx

        revoke_url = host.rstrip("/") + "/api/v1/auth/cli/revoke"
        # Best-effort — don't fail logout if revocation fails
        with contextlib.suppress(Exception):
            httpx.post(
                revoke_url,
                json={"refresh_token": profile.refresh_token},
                timeout=10.0,
            )

    # Delete local profile
    with contextlib.suppress(KeyError):
        store.delete_profile(profile_name)

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

            print_detail(
                info,
                [
                    ("profile", "Profile"),
                    ("auth_type", "Auth Type"),
                    ("user_name", "Name"),
                    ("user_email", "Email"),
                    ("org_name", "Organization"),
                    ("org_id", "Org ID"),
                    ("host", "Server"),
                    ("expires_at", "Expires At"),
                    ("refresh_needed", "Refresh Needed"),
                ],
            )
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

            print_detail(
                info,
                [
                    ("source", "Source"),
                    ("auth_type", "Auth Type"),
                    ("api_key", "API Key"),
                    ("org_id", "Organization"),
                ],
            )
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

            print_detail(
                info,
                [
                    ("source", "Source"),
                    ("auth_type", "Auth Type"),
                    ("access_token", "Access Token"),
                ],
            )
        return

    # Not authenticated
    if is_json:
        print_json(
            {
                "status": "not_authenticated",
                "hint": "Run 'querri auth login' or set QUERRI_API_KEY.",
            }
        )
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
        raise typer.Exit(code=2)

    # Auto-refresh if needed
    if needs_refresh(profile):
        try:
            profile = refresh_tokens(profile, host)
            store.save_profile(profile_name, profile)
        except RuntimeError as exc:
            print_error(str(exc))
            raise typer.Exit(code=2) from None

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
        raise typer.Exit(code=1) from None

    if is_json:
        print_json({"active_profile": profile})
    else:
        print_success(f"Switched to profile '{profile}'.")


# ---------------------------------------------------------------------------
# querri auth switch-org
# ---------------------------------------------------------------------------


@auth_app.command("switch-org")
def switch_org(
    ctx: typer.Context,
    org: str | None = typer.Argument(
        None,
        help="Organization ID to switch to (omit for interactive picker).",
    ),
) -> None:
    """Switch to a different organization without re-authenticating.

    Uses the stored refresh token to obtain new credentials scoped to
    the selected organization.
    """
    host = _get_host(ctx)
    profile_name = _get_profile_name(ctx)
    is_json = _is_json(ctx)

    store = TokenStore.load()
    profile = store.profiles.get(profile_name)

    if not profile or not profile.access_token:
        print_error("Not authenticated. Run 'querri auth login' first.")
        raise typer.Exit(code=2)

    if not profile.refresh_token:
        print_error(
            "No refresh token stored. Run 'querri auth login' to re-authenticate."
        )
        raise typer.Exit(code=2)

    all_orgs = profile.all_organizations
    if not all_orgs or len(all_orgs) < 2:
        if is_json:
            print_json(
                {"error": "single_org", "message": "Only one organization available."}
            )
        else:
            print_error("Only one organization available. Nothing to switch to.")
        raise typer.Exit(code=1)

    # Resolve target org
    if org:
        if org not in all_orgs:
            print_error(
                f"Organization '{org}' not found. "
                f"Available: {', '.join(all_orgs.keys())}"
            )
            raise typer.Exit(code=1)
        target_org_id = org
        target_org_name = all_orgs[org]
    else:
        if is_json:
            # Can't do interactive picker in JSON mode — list orgs instead
            print_json(
                {"all_organizations": all_orgs, "current_org_id": profile.org_id}
            )
            return
        target_org_id, target_org_name = _pick_organization(
            all_orgs,
            current_org_id=profile.org_id,
        )

    if target_org_id == profile.org_id:
        if is_json:
            print_json({"status": "no_change", "org_id": target_org_id})
        else:
            print_success(f"Already on {target_org_name}.")
        return

    # Refresh tokens scoped to the new org
    try:
        profile = refresh_tokens(profile, host, organization_id=target_org_id)
        profile.org_id = target_org_id
        profile.org_name = target_org_name
        store.save_profile(profile_name, profile)
    except RuntimeError as exc:
        print_error(f"Failed to switch organization: {exc}")
        raise typer.Exit(code=2) from None

    if is_json:
        print_json(
            {"status": "switched", "org_id": target_org_id, "org_name": target_org_name}
        )
    else:
        print_success(f"Switched to {target_org_name} ({target_org_id})")
