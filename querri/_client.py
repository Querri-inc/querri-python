"""Public client classes: Querri (sync) and AsyncQuerri (async)."""

from __future__ import annotations

from typing import Any

from ._base_client import AsyncHTTPClient, SyncHTTPClient
from ._config import resolve_config


class Querri:
    """Synchronous Querri API client.

    Usage::

        from querri import Querri

        client = Querri(api_key="qk_...", org_id="org_...")
        for user in client.users.list():
            print(user.email)

    Or from environment variables::

        client = Querri()  # reads QUERRI_API_KEY, QUERRI_ORG_ID
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        access_token: str | None = None,
        org_id: str | None = None,
        host: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        profile: str | None = None,
    ) -> None:
        """Initialize the synchronous Querri client.

        Args:
            api_key: API key (``qk_`` prefix). Falls back to ``QUERRI_API_KEY`` env var.
            access_token: JWT access token. Falls back to ``QUERRI_ACCESS_TOKEN`` env var.
            org_id: Organization ID. Falls back to ``QUERRI_ORG_ID`` env var.
            host: API host URL. Falls back to ``QUERRI_HOST`` (default: ``https://app.querri.com``).
            timeout: Request timeout in seconds (default: 30.0).
            max_retries: Max retry attempts for failed requests (default: 3).
            profile: Named auth profile for token store selection.
        """
        self._profile = profile
        self._config = resolve_config(
            api_key=api_key,
            access_token=access_token,
            org_id=org_id,
            host=host,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._http = SyncHTTPClient(self._config)

        # Resource namespaces — lazily initialized on first access.
        # Deferred imports keep client creation fast and avoid circular imports.
        self._users: object | None = None
        self._embed: object | None = None
        self._policies: object | None = None
        self._projects: object | None = None
        self._dashboards: object | None = None
        self._files: object | None = None
        self._sources: object | None = None
        self._views: object | None = None
        self._keys: object | None = None
        self._sharing: object | None = None
        self._usage: object | None = None
        self._audit: object | None = None

    @property
    def users(self) -> "Users":
        if self._users is None:
            from .resources.users import Users
            self._users = Users(self._http)
        return self._users  # type: ignore[return-value]

    @property
    def embed(self) -> "Embed":
        if self._embed is None:
            from .resources.embed import Embed
            self._embed = Embed(self._http)
        return self._embed  # type: ignore[return-value]

    @property
    def policies(self) -> "Policies":
        if self._policies is None:
            from .resources.policies import Policies
            self._policies = Policies(self._http)
        return self._policies  # type: ignore[return-value]

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
    def files(self) -> "Files":
        if self._files is None:
            from .resources.files import Files
            self._files = Files(self._http)
        return self._files  # type: ignore[return-value]

    @property
    def sources(self) -> "Sources":
        if self._sources is None:
            from .resources.sources import Sources
            self._sources = Sources(self._http)
        return self._sources  # type: ignore[return-value]

    @property
    def views(self) -> "Views":
        if self._views is None:
            from .resources.views import Views
            self._views = Views(self._http)
        return self._views  # type: ignore[return-value]

    @property
    def keys(self) -> "Keys":
        if self._keys is None:
            from .resources.keys import Keys
            self._keys = Keys(self._http)
        return self._keys  # type: ignore[return-value]

    @property
    def sharing(self) -> "Sharing":
        if self._sharing is None:
            from .resources.sharing import Sharing
            self._sharing = Sharing(self._http)
        return self._sharing  # type: ignore[return-value]

    @property
    def usage(self) -> "Usage":
        if self._usage is None:
            from .resources.usage import Usage
            self._usage = Usage(self._http)
        return self._usage  # type: ignore[return-value]

    @property
    def audit(self) -> "Audit":
        if self._audit is None:
            from .resources.audit import Audit
            self._audit = Audit(self._http)
        return self._audit  # type: ignore[return-value]

    def as_user(self, session: dict[str, Any]) -> "UserQuerri":
        """Create a user-scoped client from a ``get_session()`` result.

        The returned client uses the embed session token for auth and
        only exposes resources visible to the user (projects, dashboards,
        sources, chats). All queries are automatically filtered
        by the user's access policies.

        Args:
            session: Result from ``get_session()`` containing ``session_token``.
        """
        from ._user_client import UserQuerri
        return UserQuerri(session, self._config)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> "Querri":
        """Enter context manager for automatic resource cleanup."""
        return self

    def __exit__(self, *args: object) -> None:
        """Close the HTTP client on context manager exit."""
        self.close()


class AsyncQuerri:
    """Asynchronous Querri API client.

    Usage::

        from querri import AsyncQuerri

        async with AsyncQuerri() as client:
            async for user in client.users.list():
                print(user.email)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        access_token: str | None = None,
        org_id: str | None = None,
        host: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        profile: str | None = None,
    ) -> None:
        """Initialize the asynchronous Querri client.

        Args:
            api_key: API key (``qk_`` prefix). Falls back to ``QUERRI_API_KEY`` env var.
            access_token: JWT access token. Falls back to ``QUERRI_ACCESS_TOKEN`` env var.
            org_id: Organization ID. Falls back to ``QUERRI_ORG_ID`` env var.
            host: API host URL. Falls back to ``QUERRI_HOST`` (default: ``https://app.querri.com``).
            timeout: Request timeout in seconds (default: 30.0).
            max_retries: Max retry attempts for failed requests (default: 3).
            profile: Named auth profile for token store selection.
        """
        self._profile = profile
        self._config = resolve_config(
            api_key=api_key,
            access_token=access_token,
            org_id=org_id,
            host=host,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._http = AsyncHTTPClient(self._config)

        self._users: object | None = None
        self._embed: object | None = None
        self._policies: object | None = None
        self._projects: object | None = None
        self._dashboards: object | None = None
        self._files: object | None = None
        self._sources: object | None = None
        self._views: object | None = None
        self._keys: object | None = None
        self._sharing: object | None = None
        self._usage: object | None = None
        self._audit: object | None = None

    @property
    def users(self) -> "AsyncUsers":
        if self._users is None:
            from .resources.users import AsyncUsers
            self._users = AsyncUsers(self._http)
        return self._users  # type: ignore[return-value]

    @property
    def embed(self) -> "AsyncEmbed":
        if self._embed is None:
            from .resources.embed import AsyncEmbed
            self._embed = AsyncEmbed(self._http)
        return self._embed  # type: ignore[return-value]

    @property
    def policies(self) -> "AsyncPolicies":
        if self._policies is None:
            from .resources.policies import AsyncPolicies
            self._policies = AsyncPolicies(self._http)
        return self._policies  # type: ignore[return-value]

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
    def files(self) -> "AsyncFiles":
        if self._files is None:
            from .resources.files import AsyncFiles
            self._files = AsyncFiles(self._http)
        return self._files  # type: ignore[return-value]

    @property
    def sources(self) -> "AsyncSources":
        if self._sources is None:
            from .resources.sources import AsyncSources
            self._sources = AsyncSources(self._http)
        return self._sources  # type: ignore[return-value]

    @property
    def views(self) -> "AsyncViews":
        if self._views is None:
            from .resources.views import AsyncViews
            self._views = AsyncViews(self._http)
        return self._views  # type: ignore[return-value]

    @property
    def keys(self) -> "AsyncKeys":
        if self._keys is None:
            from .resources.keys import AsyncKeys
            self._keys = AsyncKeys(self._http)
        return self._keys  # type: ignore[return-value]

    @property
    def sharing(self) -> "AsyncSharing":
        if self._sharing is None:
            from .resources.sharing import AsyncSharing
            self._sharing = AsyncSharing(self._http)
        return self._sharing  # type: ignore[return-value]

    @property
    def usage(self) -> "AsyncUsage":
        if self._usage is None:
            from .resources.usage import AsyncUsage
            self._usage = AsyncUsage(self._http)
        return self._usage  # type: ignore[return-value]

    @property
    def audit(self) -> "AsyncAudit":
        if self._audit is None:
            from .resources.audit import AsyncAudit
            self._audit = AsyncAudit(self._http)
        return self._audit  # type: ignore[return-value]

    def as_user(self, session: dict[str, Any]) -> "AsyncUserQuerri":
        """Create a user-scoped async client from a ``get_session()`` result.

        The returned client uses the embed session token for auth and
        only exposes resources visible to the user (projects, dashboards,
        sources, chats). All queries are automatically filtered
        by the user's access policies.

        Args:
            session: Result from ``get_session()`` containing ``session_token``.
        """
        from ._user_client import AsyncUserQuerri
        return AsyncUserQuerri(session, self._config)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.close()

    async def __aenter__(self) -> "AsyncQuerri":
        """Enter async context manager for automatic resource cleanup."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the HTTP client on async context manager exit."""
        await self.close()
