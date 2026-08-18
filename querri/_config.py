"""Configuration and defaults for the Querri SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ._exceptions import ConfigError

DEFAULT_HOST = "https://app.querri.com"  #: Production API host.
DEFAULT_TIMEOUT = 30.0  #: Request timeout in seconds.
DEFAULT_MAX_RETRIES = 3  #: Max retry attempts for retryable errors.


@dataclass
class ClientConfig:
    """Resolved client configuration.

    Values are resolved in priority order:
    1. Explicit constructor arguments
    2. Environment variables
    3. Defaults
    """

    api_key: str | None = None  #: Querri API key (``qk_`` prefix).
    access_token: str | None = None  #: JWT access token (from OAuth or env).
    org_id: str | None = None  #: Organization ID for tenant isolation.
    base_url: str = DEFAULT_HOST + "/api/v1"  #: Fully resolved API base URL.
    timeout: float = DEFAULT_TIMEOUT  #: Request timeout in seconds.
    max_retries: int = DEFAULT_MAX_RETRIES  #: Max retry attempts for retryable errors.
    session_token: str | None = None  #: Embed session token for user-scoped clients.
    #: Which Querri client is calling: ``"sdk"`` for library use, ``"cli"`` when
    #: the ``querri`` command built the client. Sent as ``X-Querri-Client`` so
    #: the server can tell the two apart (the User-Agent is the same for both).
    client_kind: str = "sdk"
    workspace_id: str | None = None  #: Active workspace, sent as ``X-Querri-Workspace``.
    host: str = DEFAULT_HOST  #: Server root, without the ``/api/v1`` suffix.
    _user_agent: str = field(init=False)  #: Auto-generated User-Agent header value.

    def __post_init__(self) -> None:
        """Build the User-Agent string from the SDK version."""
        from ._version import __version__

        self._user_agent = f"querri-python/{__version__}"

    @property
    def client_header(self) -> str:
        """The ``X-Querri-Client`` header value, e.g. ``cli/2.1.0``."""
        from ._version import __version__

        return f"{self.client_kind}/{__version__}"

    @property
    def user_agent(self) -> str:
        """The User-Agent header value, e.g. ``querri-python/0.1.0``."""
        return self._user_agent

    def __repr__(self) -> str:
        """Redact secrets to prevent accidental exposure in logs/tracebacks."""
        key_repr = f"qk_***...{self.api_key[-4:]}" if self.api_key else None
        token_repr = "ey***" if self.access_token else None
        return (
            f"ClientConfig(base_url={self.base_url!r}, api_key={key_repr!r}, "
            f"access_token={token_repr!r}, org_id={self.org_id!r}, "
            f"workspace_id={self.workspace_id!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def resolve_config(
    *,
    api_key: str | None = None,
    access_token: str | None = None,
    org_id: str | None = None,
    host: str | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    workspace_id: str | None = None,
) -> ClientConfig:
    """Resolve configuration from arguments, env vars, and defaults.

    Args:
        api_key: API key (or set QUERRI_API_KEY env var).
        access_token: JWT access token (or set QUERRI_ACCESS_TOKEN env var).
            When provided, org_id is derived from JWT claims.
        org_id: Organization ID (or set QUERRI_ORG_ID env var).
            Required for API key auth; optional for JWT auth.
        host: Server host (or set QUERRI_HOST env var).
            ``/api/v1`` is appended automatically.
            Example: ``host="http://localhost"`` becomes
            ``http://localhost/api/v1``.
            Defaults to ``https://app.querri.com``.
        timeout: Request timeout in seconds.
        max_retries: Max retry attempts for retryable errors.
        workspace_id: Active workspace (or set QUERRI_WORKSPACE_ID env var).
            Sent as the ``X-Querri-Workspace`` header on every request, which
            (a) homes newly created objects there and (b) scopes list reads and
            agent search to that workspace. ``None`` means "no active
            workspace": creates fall back to the caller's personal workspace
            and reads are unscoped. It is a HINT — the server re-validates it
            against membership and fails closed.

    Raises:
        ConfigError: If no credentials are provided.
    """
    resolved_key = api_key or os.environ.get("QUERRI_API_KEY")
    resolved_token = access_token or os.environ.get("QUERRI_ACCESS_TOKEN")

    # 3rd priority: token store (~/.querri/tokens.json)
    profile_host: str | None = None
    if not resolved_key and not resolved_token:
        try:
            from ._auth import TokenStore

            store = TokenStore.load()
            profile = store.get_active_profile()
            if profile and profile.access_token:
                resolved_token = profile.access_token
                if not org_id and profile.org_id:
                    org_id = profile.org_id
                # The host the token was MINTED against. Without this, `Querri()`
                # after `querri auth login --host http://localhost` sent a
                # localhost JWT to app.querri.com and failed with a bare 403 —
                # a credential leaked to the wrong host, reported as a
                # permissions problem. An explicit host= or QUERRI_HOST still
                # wins; this only fills the blank.
                profile_host = profile.host or None
        except Exception:
            # Token store unavailable — continue to error
            pass

    if not resolved_key and not resolved_token:
        raise ConfigError(
            "No credentials found. Pass api_key= to the constructor, "
            "set the QUERRI_API_KEY environment variable, or run "
            "'querri auth login'."
        )

    resolved_org = org_id or os.environ.get("QUERRI_ORG_ID")

    # org_id is required for API key auth, optional for JWT auth
    if resolved_key and not resolved_token and not resolved_org:
        raise ConfigError(
            "No organization ID provided. Pass org_id= to the constructor "
            "or set the QUERRI_ORG_ID environment variable."
        )

    resolved_host = (
        host or os.environ.get("QUERRI_HOST") or profile_host or DEFAULT_HOST
    )
    resolved_url = resolved_host.rstrip("/") + "/api/v1"

    resolved_timeout = timeout
    if resolved_timeout is None:
        env_timeout = os.environ.get("QUERRI_TIMEOUT")
        resolved_timeout = float(env_timeout) if env_timeout else DEFAULT_TIMEOUT

    resolved_retries = max_retries
    if resolved_retries is None:
        env_retries = os.environ.get("QUERRI_MAX_RETRIES")
        resolved_retries = int(env_retries) if env_retries else DEFAULT_MAX_RETRIES

    # `QUERRI_WORKSPACE_ID` is the documented name; `QUERRI_WORKSPACE` is accepted
    # because that is what people type. Empty string means None — an env var set to
    # "" must not send an empty header the server would then have to interpret.
    resolved_workspace = (
        workspace_id
        or os.environ.get("QUERRI_WORKSPACE_ID")
        or os.environ.get("QUERRI_WORKSPACE")
        or None
    )
    if resolved_workspace is not None:
        resolved_workspace = resolved_workspace.strip() or None

    return ClientConfig(
        api_key=resolved_key,
        access_token=resolved_token,
        org_id=resolved_org,
        base_url=resolved_url,
        timeout=resolved_timeout,
        max_retries=resolved_retries,
        workspace_id=resolved_workspace,
        host=resolved_host.rstrip("/"),
    )
