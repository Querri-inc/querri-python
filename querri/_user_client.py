"""User-scoped client that uses embed session auth and FGA-filtered resources.

Calls the public API (``/api/v1``) with the session token in the
``X-Embed-Session`` header — embed sessions are the public API's priority-0
credential. Resources are automatically filtered by the session user's
access policies, and the scope set excludes ``embed:session:create`` (a
session cannot mint sessions) and ``admin:dashboards:write`` (dashboards
are read-only under an embed session).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._base_client import AsyncHTTPClient, SyncHTTPClient
from ._config import ClientConfig

if TYPE_CHECKING:
    from .resources.projects import AsyncChats, AsyncProjects, Chats, Projects
    from .resources.sources import AsyncSources, Sources


def _session_config(
    session: dict[str, Any], parent_config: ClientConfig
) -> ClientConfig:
    """Build a config for session-mode HTTP clients.

    Same ``/api/v1`` base URL as the parent; auth switches from the API key
    to the session token (sent as ``X-Embed-Session``).
    """
    return ClientConfig(
        api_key="",  # Not used in session mode.
        org_id="",  # Not used in session mode.
        base_url=parent_config.base_url,
        timeout=parent_config.timeout,
        max_retries=parent_config.max_retries,
        session_token=session["session_token"],
    )


class UserDashboards:
    """Read-only dashboards surface for user-scoped clients.

    Embed sessions exclude the ``admin:dashboards:write`` scope, so only
    the read endpoints exist here — write calls would 403 server-side, and
    this surface makes that contract explicit client-side.
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        from .resources.dashboards import Dashboards

        self._full = Dashboards(http)
        self.list = self._full.list
        self.get = self._full.get
        self.refresh_status = self._full.refresh_status


class AsyncUserDashboards:
    """Read-only dashboards surface for user-scoped clients (async).

    See :class:`UserDashboards`.
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        from .resources.dashboards import AsyncDashboards

        self._full = AsyncDashboards(http)
        self.list = self._full.list
        self.get = self._full.get
        self.refresh_status = self._full.refresh_status


class UserQuerri:
    """User-scoped synchronous client with FGA-filtered resources.

    Calls the public API (``/api/v1``) using an embed session token.
    Only exposes resources visible to the session user; dashboards are
    read-only, and there is no ``embed`` accessor (a session cannot mint
    or manage sessions — that is the admin client's job).

    Usage::

        session = client.embed.get_session(user="ext_123")
        user_client = client.as_user(session)
        for project in user_client.projects.list():
            print(project.name)

    Create via :meth:`Querri.as_user`.
    """

    def __init__(self, session: dict[str, Any], parent_config: ClientConfig) -> None:
        """Initialize with session token and parent client config.

        Args:
            session: Result from ``get_session()`` containing ``session_token``.
            parent_config: Config from the parent ``Querri`` client.
        """
        self._config = _session_config(session, parent_config)
        self._http = SyncHTTPClient(self._config)

        # Resource namespaces — lazily initialized on first access.
        # Deferred imports keep client creation fast and avoid circular imports.
        self._projects: object | None = None
        self._dashboards: object | None = None
        self._sources: object | None = None
        self._chats: object | None = None

    @property
    def projects(self) -> Projects:
        if self._projects is None:
            from .resources.projects import Projects

            self._projects = Projects(self._http)
        return self._projects  # type: ignore[return-value]

    @property
    def dashboards(self) -> UserDashboards:
        if self._dashboards is None:
            self._dashboards = UserDashboards(self._http)
        return self._dashboards  # type: ignore[return-value]

    @property
    def sources(self) -> Sources:
        if self._sources is None:
            from .resources.sources import Sources

            self._sources = Sources(self._http)
        return self._sources  # type: ignore[return-value]

    @property
    def chats(self) -> Chats:
        if self._chats is None:
            from .resources.projects import Chats

            self._chats = Chats(self._http)
        return self._chats  # type: ignore[return-value]

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> UserQuerri:
        """Enter context manager for automatic resource cleanup."""
        return self

    def __exit__(self, *args: object) -> None:
        """Close the HTTP client on context manager exit."""
        self.close()


class AsyncUserQuerri:
    """User-scoped asynchronous client with FGA-filtered resources.

    Calls the public API (``/api/v1``) using an embed session token.
    Only exposes resources visible to the session user; dashboards are
    read-only, and there is no ``embed`` accessor.

    Usage::

        session = await client.embed.get_session(user="ext_123")
        user_client = client.as_user(session)
        async for project in user_client.projects.list():
            print(project.name)

    Create via :meth:`AsyncQuerri.as_user`.
    """

    def __init__(self, session: dict[str, Any], parent_config: ClientConfig) -> None:
        """Initialize with session token and parent client config.

        Args:
            session: Result from ``get_session()`` containing ``session_token``.
            parent_config: Config from the parent ``AsyncQuerri`` client.
        """
        self._config = _session_config(session, parent_config)
        self._http = AsyncHTTPClient(self._config)

        # Resource namespaces — lazily initialized on first access.
        self._projects: object | None = None
        self._dashboards: object | None = None
        self._sources: object | None = None
        self._chats: object | None = None

    @property
    def projects(self) -> AsyncProjects:
        if self._projects is None:
            from .resources.projects import AsyncProjects

            self._projects = AsyncProjects(self._http)
        return self._projects  # type: ignore[return-value]

    @property
    def dashboards(self) -> AsyncUserDashboards:
        if self._dashboards is None:
            self._dashboards = AsyncUserDashboards(self._http)
        return self._dashboards  # type: ignore[return-value]

    @property
    def sources(self) -> AsyncSources:
        if self._sources is None:
            from .resources.sources import AsyncSources

            self._sources = AsyncSources(self._http)
        return self._sources  # type: ignore[return-value]

    @property
    def chats(self) -> AsyncChats:
        if self._chats is None:
            from .resources.projects import AsyncChats

            self._chats = AsyncChats(self._http)
        return self._chats  # type: ignore[return-value]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.close()

    async def __aenter__(self) -> AsyncUserQuerri:
        """Enter async context manager for automatic resource cleanup."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the HTTP client on async context manager exit."""
        await self.close()
