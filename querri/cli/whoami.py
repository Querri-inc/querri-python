"""querri whoami — show current credential info."""

from __future__ import annotations

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    EXIT_AUTH_ERROR,
    handle_api_error,
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

    # Build credential info — mask API key per SEC-1
    config = client._config
    host = config.base_url.replace("/api/v1", "")
    key = config.api_key
    key_display = f"{key[:7]}..." if len(key) > 7 else key[:4] + "..."

    info = {
        "host": host,
        "auth_type": "api_key",
        "org_id": config.org_id,
        "api_key_prefix": key_display,
    }

    if is_json:
        print_json(info)
    else:
        print_detail(info, [
            ("host", "Host"),
            ("auth_type", "Auth Type"),
            ("org_id", "Org ID"),
            ("api_key_prefix", "API Key"),
        ])
