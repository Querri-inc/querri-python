"""User-scoped client that uses embed session auth and FGA-filtered resources.

Calls the internal API (``/api``) instead of the public API (``/api/v1``).
Resources are automatically filtered by the session user's access policies.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from ._base_client import AsyncHTTPClient, SyncHTTPClient
from ._config import ClientConfig


def _session_config(
    session: Dict[str, Any], parent_config: ClientConfig
) -> ClientConfig:
    """Build a config for session-mode HTTP clients.

    Derives the ``/api`` base URL from the parent's ``/api/v1`` URL and
    sets the session token for ``X-Embed-Session`` auth.
    """
    # Strip /api/v1 suffix to get the host, then append /api
    host = re.sub(r"/api/v1$", "", parent_config.base_url)
    return ClientConfig(
        api_key="",  # Not used in session mode.
        org_id="",  # Not used in session mode.
        base_url=f"{host}/api",
        timeout=parent_config.timeout,
        max_retries=parent_config.max_retries,
        session_token=session["session_token"],
    )


class UserQuerri:
    """User-scoped synchronous client with FGA-filtered resources.

    Calls the internal API (``/api``) using an embed session token.
    Only exposes resources visible to the session user.

    Usage::

        session = client.embed.get_session(user="ext_123")
        user_client = client.as_user(session)
        for project in user_client.projects.list():
            print(project.name)

    Create via :meth:`Querri.as_user`.
    """

    def __init__(self, session: Dict[str, Any], parent_config: ClientConfig) -> None:
        """Initialize with session token and parent client config.

        Args:
            session: Result from ``get_session()`` containing ``session_token``.
            parent_config: Config from the parent ``Querri`` client.
        """
        self._config = _session_config(session, parent_config)
        self._http = SyncHTTPClient(self._config)

        # Resource namespaces — lazily initialized on first access.
        # Deferred imports keep client creation fast and avoid circular imports.
        self._projects: Optional[object] = None
        self._dashboards: Optional[object] = None
        self._sources: Optional[object] = None
        self._chats: Optional[object] = None

    @property
    def projects(self) -> "Projects":
        if self._projects is None:
            from .resources.projects import Projects
            self._projects = Projects(self._http)
        return self._projects  # type: ignore[return-value]

    @property
    def dashboards(self) -> "Dashboards":
        if self._dashboards is None:
            from .resources.dashboards import Dashboards
            self._dashboards = Dashboards(self._http)
        return self._dashboards  # type: ignore[return-value]

    @property
    def sources(self) -> "Sources":
        if self._sources is None:
            from .resources.sources import Sources
            self._sources = Sources(self._http)
        return self._sources  # type: ignore[return-value]

    @property
    def chats(self) -> "Chats":
        if self._chats is None:
            from .resources.projects import Chats
            self._chats = Chats(self._http)
        return self._chats  # type: ignore[return-value]

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> "UserQuerri":
        """Enter context manager for automatic resource cleanup."""
        return self

    def __exit__(self, *args: object) -> None:
        """Close the HTTP client on context manager exit."""
        self.close()


class AsyncUserQuerri:
    """User-scoped asynchronous client with FGA-filtered resources.

    Calls the internal API (``/api``) using an embed session token.
    Only exposes resources visible to the session user.

    Usage::

        session = await client.embed.get_session(user="ext_123")
        user_client = client.as_user(session)
        async for project in user_client.projects.list():
            print(project.name)

    Create via :meth:`AsyncQuerri.as_user`.
    """

    def __init__(self, session: Dict[str, Any], parent_config: ClientConfig) -> None:
        """Initialize with session token and parent client config.

        Args:
            session: Result from ``get_session()`` containing ``session_token``.
            parent_config: Config from the parent ``AsyncQuerri`` client.
        """
        self._config = _session_config(session, parent_config)
        self._http = AsyncHTTPClient(self._config)

        # Resource namespaces — lazily initialized on first access.
        self._projects: Optional[object] = None
        self._dashboards: Optional[object] = None
        self._sources: Optional[object] = None
        self._chats: Optional[object] = None

    @property
    def projects(self) -> "AsyncProjects":
        if self._projects is None:
            from .resources.projects import AsyncProjects
            self._projects = AsyncProjects(self._http)
        return self._projects  # type: ignore[return-value]

    @property
    def dashboards(self) -> "AsyncDashboards":
        if self._dashboards is None:
            from .resources.dashboards import AsyncDashboards
            self._dashboards = AsyncDashboards(self._http)
        return self._dashboards  # type: ignore[return-value]

    @property
    def sources(self) -> "AsyncSources":
        if self._sources is None:
            from .resources.sources import AsyncSources
            self._sources = AsyncSources(self._http)
        return self._sources  # type: ignore[return-value]

    @property
    def chats(self) -> "AsyncChats":
        if self._chats is None:
            from .resources.projects import AsyncChats
            self._chats = AsyncChats(self._http)
        return self._chats  # type: ignore[return-value]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.close()

    async def __aenter__(self) -> "AsyncUserQuerri":
        """Enter async context manager for automatic resource cleanup."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the HTTP client on async context manager exit."""
        await self.close()
