"""querri whoami — show current credential info."""

from __future__ import annotations

import typer

from querri.cli._context import _get_profile, get_client
from querri.cli._output import (
    print_detail,
    print_json,
)

whoami_app = typer.Typer(name="whoami", help="Show authenticated user info.")


@whoami_app.callback(invoke_without_command=True)
def whoami(ctx: typer.Context) -> None:
    """Display current authentication credentials and connection info."""
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)

    client = get_client(ctx)
    config = client._config
    host = config.base_url.replace("/api/v1", "")

    # Determine auth type and credential display
    key = config.api_key
    access_token = getattr(config, "access_token", None)

    if key:
        auth_type = "api_key"
        credential_display = f"{key[:7]}..." if len(key) > 7 else key[:4] + "..."
    elif access_token:
        auth_type = "jwt"
        credential_display = f"{access_token[:20]}..." if len(access_token) > 20 else access_token
    else:
        auth_type = "unknown"
        credential_display = "(none)"

    info = {
        "host": host,
        "auth_type": auth_type,
        "org_id": config.org_id,
        "credential": credential_display,
    }

    # Enrich with profile info if available (JWT auth from `querri auth login`)
    profile = _get_profile(ctx)
    if profile:
        if profile.org_name:
            info["org_name"] = profile.org_name
        if profile.user_email:
            info["user_email"] = profile.user_email
        if profile.user_name:
            info["user_name"] = profile.user_name
        if profile.user_id:
            info["user_id"] = profile.user_id

    if is_json:
        print_json(info)
    else:
        fields = [
            ("host", "Host"),
            ("auth_type", "Auth Type"),
            ("org_id", "Org ID"),
        ]
        if "org_name" in info:
            fields.append(("org_name", "Org Name"))
        if "user_name" in info:
            fields.append(("user_name", "User"))
        if "user_email" in info:
            fields.append(("user_email", "Email"))
        if "user_id" in info:
            fields.append(("user_id", "User ID"))
        fields.append(("credential", "Credential"))
        print_detail(info, fields)
