"""Public client classes: Querri (sync) and AsyncQuerri (async)."""

from __future__ import annotations

from typing import Optional

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
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        host: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self._config = resolve_config(
            api_key=api_key,
            org_id=org_id,
            host=host,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._http = SyncHTTPClient(self._config)

        # Resource namespaces — lazily initialized on first access
        self._users: Optional[object] = None
        self._embed: Optional[object] = None
        self._policies: Optional[object] = None
        self._projects: Optional[object] = None
        self._dashboards: Optional[object] = None
        self._data: Optional[object] = None
        self._files: Optional[object] = None
        self._sources: Optional[object] = None
        self._keys: Optional[object] = None
        self._sharing: Optional[object] = None
        self._usage: Optional[object] = None
        self._audit: Optional[object] = None

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
    def data(self) -> "Data":
        if self._data is None:
            from .resources.data import Data
            self._data = Data(self._http)
        return self._data  # type: ignore[return-value]

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

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> "Querri":
        return self

    def __exit__(self, *args: object) -> None:
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
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        host: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self._config = resolve_config(
            api_key=api_key,
            org_id=org_id,
            host=host,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._http = AsyncHTTPClient(self._config)

        self._users: Optional[object] = None
        self._embed: Optional[object] = None
        self._policies: Optional[object] = None
        self._projects: Optional[object] = None
        self._dashboards: Optional[object] = None
        self._data: Optional[object] = None
        self._files: Optional[object] = None
        self._sources: Optional[object] = None
        self._keys: Optional[object] = None
        self._sharing: Optional[object] = None
        self._usage: Optional[object] = None
        self._audit: Optional[object] = None

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
    def data(self) -> "AsyncData":
        if self._data is None:
            from .resources.data import AsyncData
            self._data = AsyncData(self._http)
        return self._data  # type: ignore[return-value]

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

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.close()

    async def __aenter__(self) -> "AsyncQuerri":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
