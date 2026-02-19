"""Configuration and defaults for the Querri SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from ._exceptions import ConfigError

DEFAULT_HOST = "https://app.querri.com"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3


@dataclass
class ClientConfig:
    """Resolved client configuration.

    Values are resolved in priority order:
    1. Explicit constructor arguments
    2. Environment variables
    3. Defaults
    """

    api_key: str
    org_id: str
    base_url: str = DEFAULT_HOST + "/api/v1"
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    _user_agent: str = field(init=False)

    def __post_init__(self) -> None:
        from ._version import __version__

        self._user_agent = f"querri-python/{__version__}"

    @property
    def user_agent(self) -> str:
        return self._user_agent


def resolve_config(
    *,
    api_key: Optional[str] = None,
    org_id: Optional[str] = None,
    host: Optional[str] = None,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> ClientConfig:
    """Resolve configuration from arguments, env vars, and defaults.

    Args:
        api_key: API key (or set QUERRI_API_KEY env var).
        org_id: Organization ID (or set QUERRI_ORG_ID env var).
        host: Server host (or set QUERRI_HOST env var).
            ``/api/v1`` is appended automatically.
            Example: ``host="http://localhost"`` becomes
            ``http://localhost/api/v1``.
            Defaults to ``https://app.querri.com``.
        timeout: Request timeout in seconds.
        max_retries: Max retry attempts for retryable errors.

    Raises:
        ConfigError: If required values (api_key, org_id) are missing.
    """
    resolved_key = api_key or os.environ.get("QUERRI_API_KEY")
    if not resolved_key:
        raise ConfigError(
            "No API key provided. Pass api_key= to the constructor "
            "or set the QUERRI_API_KEY environment variable."
        )

    resolved_org = org_id or os.environ.get("QUERRI_ORG_ID")
    if not resolved_org:
        raise ConfigError(
            "No organization ID provided. Pass org_id= to the constructor "
            "or set the QUERRI_ORG_ID environment variable."
        )

    resolved_host = host or os.environ.get("QUERRI_HOST") or DEFAULT_HOST
    resolved_url = resolved_host.rstrip("/") + "/api/v1"

    resolved_timeout = timeout
    if resolved_timeout is None:
        env_timeout = os.environ.get("QUERRI_TIMEOUT")
        resolved_timeout = float(env_timeout) if env_timeout else DEFAULT_TIMEOUT

    resolved_retries = max_retries
    if resolved_retries is None:
        env_retries = os.environ.get("QUERRI_MAX_RETRIES")
        resolved_retries = int(env_retries) if env_retries else DEFAULT_MAX_RETRIES

    return ClientConfig(
        api_key=resolved_key,
        org_id=resolved_org,
        base_url=resolved_url,
        timeout=resolved_timeout,
        max_retries=resolved_retries,
    )
