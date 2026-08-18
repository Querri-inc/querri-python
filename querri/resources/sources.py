"""Connector, source management, and data access resource."""

from __future__ import annotations

import builtins
from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._pagination import AsyncCursorPage, SyncCursorPage
from ..types.data import DataPage, DataWriteResult, QueryResult, Source


class Sources:
    """Synchronous connector, source management, and data access resource.

    Usage::

        connectors = client.sources.list_connectors()
        sources = client.sources.list()
        result = client.sources.query(
            sql="SELECT * FROM data LIMIT 10",
            source_id="src_...",
        )
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    # -- Connector management -----------------------------------------------

    def list_connectors(
        self,
        *,
        limit: int = 25,
        after: str | None = None,
    ) -> SyncCursorPage[dict[str, Any]]:
        """List available connector types with connection status.

        Args:
            limit: Maximum connectors per page (1-100).
            after: Cursor for the next page.

        Returns:
            Auto-paginating iterator of connector dicts with id, name, service,
            status.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        return SyncCursorPage(self._http, "/connectors", None, params=params)

    # -- Source CRUD ---------------------------------------------------------

    def create(
        self,
        *,
        name: str,
        connector_id: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a connector-based data source.

        Args:
            name: Display name for the source.
            connector_id: The connector UUID to use.
            config: Source-specific configuration dict.

        Returns:
            Dict with id, name, connector_id, status.
        """
        resp = self._http.post(
            "/sources",
            json={
                "name": name,
                "connector_id": connector_id,
                "config": config or {},
            },
        )
        return resp.json()  # type: ignore[no-any-return]

    def create_data_source(
        self,
        *,
        name: str,
        rows: builtins.list[dict[str, Any]],
    ) -> Source:
        """Create a new data source with inline JSON data.

        Args:
            name: Display name for the source (1-200 chars).
            rows: List of row dicts. All rows should share the same keys.

        Returns:
            Source object with id, name, columns, row_count, updated_at.
        """
        resp = self._http.post(
            "/sources",
            json={"name": name, "rows": rows},
        )
        return Source.model_validate(resp.json())

    def get(self, source_id: str) -> dict[str, Any]:
        """Get source details.

        Args:
            source_id: The source UUID.

        Returns:
            Source detail dict.
        """
        resp = self._http.get(f"/sources/{source_id}")
        return resp.json()  # type: ignore[no-any-return]

    def list(
        self,
        *,
        limit: int = 25,
        after: str | None = None,
    ) -> SyncCursorPage[dict[str, Any]]:
        """List data sources for the organization with cursor pagination.

        Args:
            limit: Maximum sources per page (1-100).
            after: Cursor for the next page.

        Returns:
            Auto-paginating iterator of source summary dicts with id, name,
            service, connector_id, etc.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        return SyncCursorPage(self._http, "/sources", None, params=params)

    # -- Readiness -----------------------------------------------------------

    # An upload returns as soon as the bytes land; parsing happens on a job
    # queue afterwards. Everything downstream — querying, adding to a project,
    # the knowledge graph, an agent finding it — needs the parsed dataframe, so
    # "uploaded" and "usable" are minutes apart on a real load. These two
    # methods are the difference between a script that works and one that
    # races.

    def ready_state(self, source_id: str) -> tuple[str, dict[str, Any]]:
        """``(state, source)`` where state is ``ready`` | ``processing`` |
        ``error`` | ``missing``.

        ``ready`` means a parsed dataframe is attached, which is the condition
        every downstream feature actually needs — not merely that the row exists.
        """
        try:
            src = self.get(source_id)
        except Exception as exc:  # noqa: BLE001 — a 404 is a state, not a crash
            status = getattr(exc, "status", None)
            if status == 404:
                return "missing", {"id": source_id}
            raise
        if src.get("materialized"):
            return "ready", src
        if str(src.get("status", "")).lower() in {"error", "failed"}:
            return "error", src
        return "processing", src

    def wait_until_ready(
        self,
        source_ids: str | builtins.list[str],
        *,
        timeout: float = 900.0,
        interval: float = 3.0,
        on_progress: Any = None,
    ) -> dict[str, dict[str, Any]]:
        """Block until every source finishes processing.

        Returns ``{source_id: {"state": ..., "source": ...}}`` — one entry per id,
        with state ``ready``, ``error``, ``missing`` or ``timeout``. It does NOT
        raise on a failed source: a 400-file load where three tables fail is a
        result to inspect, not an exception that discards the other 397.

        ``on_progress(done, total, state_counts)`` is called after each poll.
        """
        import time

        ids = [source_ids] if isinstance(source_ids, str) else builtins.list(source_ids)
        out: dict[str, dict[str, Any]] = {}
        pending = list(ids)
        deadline = time.monotonic() + timeout

        while pending and time.monotonic() < deadline:
            still: builtins.list[str] = []
            for sid in pending:
                state, src = self.ready_state(sid)
                if state == "processing":
                    still.append(sid)
                else:
                    out[sid] = {"state": state, "source": src}
            pending = still
            if on_progress is not None:
                counts: dict[str, int] = {}
                for rec in out.values():
                    counts[rec["state"]] = counts.get(rec["state"], 0) + 1
                on_progress(len(out), len(ids), counts)
            if pending:
                time.sleep(interval)

        for sid in pending:
            _state, src = self.ready_state(sid)
            out[sid] = {"state": "timeout", "source": src}
        return out

    def pending(self, *, limit: int = 100) -> builtins.list[dict[str, Any]]:
        """Every source in the current scope that is not yet usable.

        Scoped by the client's active workspace, like any other list read — so
        after ``querri workspace use finance`` this answers "is Finance ready",
        not "is the whole org ready".
        """
        out: builtins.list[dict[str, Any]] = []
        for src in self.list(limit=limit):
            if src.get("materialized"):
                continue
            if str(src.get("status", "")).lower() in {"deleted"}:
                continue
            out.append(src)
        return out

    def update(
        self,
        source_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update source configuration.

        Args:
            source_id: The source UUID.
            name: New display name.
            description: User notes about the source.
            config: Updated configuration dict.

        Returns:
            Dict with id and updated status.
        """
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if config is not None:
            payload["config"] = config
        resp = self._http.patch(f"/sources/{source_id}", json=payload)
        return resp.json()  # type: ignore[no-any-return]

    def delete(self, source_id: str) -> None:
        """Delete a data source.

        Args:
            source_id: The source UUID.
        """
        self._http.delete(f"/sources/{source_id}")

    def sync(self, source_id: str) -> dict[str, Any]:
        """Trigger a source sync.

        Args:
            source_id: The source UUID.

        Returns:
            Dict with id and status ("sync_queued").
        """
        resp = self._http.post(f"/sources/{source_id}/sync")
        return resp.json()  # type: ignore[no-any-return]

    # -- Data access (merged from Data resource) ----------------------------

    def query(
        self,
        *,
        sql: str,
        source_id: str,
        page: int = 1,
        page_size: int = 100,
    ) -> QueryResult:
        """Execute a SQL query against a source with RLS enforcement.

        Args:
            sql: SQL query string (max 10,000 characters).
            source_id: The source UUID to query against.
            page: Page number (1-based).
            page_size: Number of rows per page (1-10,000).

        Returns:
            QueryResult with data, total_rows, page, page_size.
        """
        resp = self._http.post(
            f"/sources/{source_id}/query",
            json={
                "sql": sql,
                "page": page,
                "page_size": page_size,
            },
        )
        return QueryResult.model_validate(resp.json())

    def source_data(
        self,
        source_id: str,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> DataPage:
        """Get paginated source data with RLS enforcement.

        Args:
            source_id: The source UUID.
            page: Page number (1-based).
            page_size: Number of rows per page (1-10,000).

        Returns:
            Paginated DataPage object.
        """
        resp = self._http.get(
            f"/sources/{source_id}/data",
            params={"page": page, "page_size": page_size},
        )
        return DataPage.model_validate(resp.json())

    def append_rows(
        self, source_id: str, *, rows: builtins.list[dict[str, Any]]
    ) -> DataWriteResult:
        """Append rows to an existing data source.

        Args:
            source_id: Data source ID.
            rows: List of row dicts to append.
        """
        resp = self._http.post(f"/sources/{source_id}/rows", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())

    def replace_data(
        self, source_id: str, *, rows: builtins.list[dict[str, Any]]
    ) -> DataWriteResult:
        """Replace all data in a source with new rows.

        Args:
            source_id: Data source ID.
            rows: Complete set of row dicts replacing all existing data.
        """
        resp = self._http.put(f"/sources/{source_id}/data", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())

    def ask(self, source_id: str, *, question: str) -> dict[str, Any]:
        """Ask a natural language question about a data source.

        Args:
            source_id: The source UUID.
            question: Natural language question string.

        Returns:
            Dict with answer text and optional data rows.
        """
        resp = self._http.post(
            f"/sources/{source_id}/ask",
            json={"question": question},
        )
        return resp.json()  # type: ignore[no-any-return]


class AsyncSources:
    """Asynchronous connector, source management, and data access resource.

    Usage::

        connectors = await client.sources.list_connectors()
        sources = await client.sources.list()
        result = await client.sources.query(
            sql="SELECT * FROM data LIMIT 10",
            source_id="src_...",
        )
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    # -- Connector management -----------------------------------------------

    async def list_connectors(
        self,
        *,
        limit: int = 25,
        after: str | None = None,
    ) -> AsyncCursorPage[dict[str, Any]]:
        """List available connector types with connection status.

        Args:
            limit: Maximum connectors per page (1-100).
            after: Cursor for the next page.

        Returns:
            Auto-paginating iterator of connector dicts with id, name, service,
            status.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        return AsyncCursorPage(self._http, "/connectors", None, params=params)

    # -- Source CRUD ---------------------------------------------------------

    async def create(
        self,
        *,
        name: str,
        connector_id: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a connector-based data source.

        Args:
            name: Display name for the source.
            connector_id: The connector UUID to use.
            config: Source-specific configuration dict.

        Returns:
            Dict with id, name, connector_id, status.
        """
        resp = await self._http.post(
            "/sources",
            json={
                "name": name,
                "connector_id": connector_id,
                "config": config or {},
            },
        )
        return resp.json()  # type: ignore[no-any-return]

    async def create_data_source(
        self,
        *,
        name: str,
        rows: builtins.list[dict[str, Any]],
    ) -> Source:
        """Create a new data source with inline JSON data.

        Args:
            name: Display name for the source (1-200 chars).
            rows: List of row dicts. All rows should share the same keys.

        Returns:
            Source object with id, name, columns, row_count, updated_at.
        """
        resp = await self._http.post(
            "/sources",
            json={"name": name, "rows": rows},
        )
        return Source.model_validate(resp.json())

    async def get(self, source_id: str) -> dict[str, Any]:
        """Get source details.

        Args:
            source_id: The source UUID.

        Returns:
            Source detail dict.
        """
        resp = await self._http.get(f"/sources/{source_id}")
        return resp.json()  # type: ignore[no-any-return]

    async def list(
        self,
        *,
        limit: int = 25,
        after: str | None = None,
    ) -> AsyncCursorPage[dict[str, Any]]:
        """List data sources for the organization with cursor pagination.

        Args:
            limit: Maximum sources per page (1-100).
            after: Cursor for the next page.

        Returns:
            Auto-paginating iterator of source summary dicts with id, name,
            service, connector_id, etc.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        return AsyncCursorPage(self._http, "/sources", None, params=params)

    # -- Readiness -----------------------------------------------------------

    async def ready_state(self, source_id: str) -> tuple[str, dict[str, Any]]:
        """``(state, source)`` where state is ``ready`` | ``processing`` |
        ``error`` | ``missing``. See :meth:`Sources.ready_state`."""
        try:
            src = await self.get(source_id)
        except Exception as exc:  # noqa: BLE001 — a 404 is a state, not a crash
            status = getattr(exc, "status", None)
            if status == 404:
                return "missing", {"id": source_id}
            raise
        if src.get("materialized"):
            return "ready", src
        if str(src.get("status", "")).lower() in {"error", "failed"}:
            return "error", src
        return "processing", src

    async def wait_until_ready(
        self,
        source_ids: str | builtins.list[str],
        *,
        timeout: float = 900.0,
        interval: float = 3.0,
        on_progress: Any = None,
    ) -> dict[str, dict[str, Any]]:
        """Block until every source finishes processing. See
        :meth:`Sources.wait_until_ready`."""
        import asyncio
        import time

        ids = [source_ids] if isinstance(source_ids, str) else builtins.list(source_ids)
        out: dict[str, dict[str, Any]] = {}
        pending = list(ids)
        deadline = time.monotonic() + timeout

        while pending and time.monotonic() < deadline:
            states = await asyncio.gather(*(self.ready_state(sid) for sid in pending))
            still: builtins.list[str] = []
            for sid, (state, src) in zip(pending, states):
                if state == "processing":
                    still.append(sid)
                else:
                    out[sid] = {"state": state, "source": src}
            pending = still
            if on_progress is not None:
                counts: dict[str, int] = {}
                for rec in out.values():
                    counts[rec["state"]] = counts.get(rec["state"], 0) + 1
                on_progress(len(out), len(ids), counts)
            if pending:
                await asyncio.sleep(interval)

        for sid in pending:
            _state, src = await self.ready_state(sid)
            out[sid] = {"state": "timeout", "source": src}
        return out

    async def pending(self, *, limit: int = 100) -> builtins.list[dict[str, Any]]:
        """Every source in the current scope that is not yet usable."""
        out: builtins.list[dict[str, Any]] = []
        page = await self.list(limit=limit)
        async for src in page:
            if src.get("materialized"):
                continue
            if str(src.get("status", "")).lower() in {"deleted"}:
                continue
            out.append(src)
        return out

    async def update(
        self,
        source_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update source configuration.

        Args:
            source_id: The source UUID.
            name: New display name.
            description: User notes about the source.
            config: Updated configuration dict.

        Returns:
            Dict with id and updated status.
        """
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if config is not None:
            payload["config"] = config
        resp = await self._http.patch(f"/sources/{source_id}", json=payload)
        return resp.json()  # type: ignore[no-any-return]

    async def delete(self, source_id: str) -> None:
        """Delete a data source.

        Args:
            source_id: The source UUID.
        """
        await self._http.delete(f"/sources/{source_id}")

    async def sync(self, source_id: str) -> dict[str, Any]:
        """Trigger a source sync.

        Args:
            source_id: The source UUID.

        Returns:
            Dict with id and status ("sync_queued").
        """
        resp = await self._http.post(f"/sources/{source_id}/sync")
        return resp.json()  # type: ignore[no-any-return]

    # -- Data access (merged from Data resource) ----------------------------

    async def query(
        self,
        *,
        sql: str,
        source_id: str,
        page: int = 1,
        page_size: int = 100,
    ) -> QueryResult:
        """Execute a SQL query against a source with RLS enforcement.

        Args:
            sql: SQL query string (max 10,000 characters).
            source_id: The source UUID to query against.
            page: Page number (1-based).
            page_size: Number of rows per page (1-10,000).

        Returns:
            QueryResult with data, total_rows, page, page_size.
        """
        resp = await self._http.post(
            f"/sources/{source_id}/query",
            json={
                "sql": sql,
                "page": page,
                "page_size": page_size,
            },
        )
        return QueryResult.model_validate(resp.json())

    async def source_data(
        self,
        source_id: str,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> DataPage:
        """Get paginated source data with RLS enforcement.

        Args:
            source_id: The source UUID.
            page: Page number (1-based).
            page_size: Number of rows per page (1-10,000).

        Returns:
            Paginated DataPage object.
        """
        resp = await self._http.get(
            f"/sources/{source_id}/data",
            params={"page": page, "page_size": page_size},
        )
        return DataPage.model_validate(resp.json())

    async def append_rows(
        self, source_id: str, *, rows: builtins.list[dict[str, Any]]
    ) -> DataWriteResult:
        """Append rows to an existing data source.

        Args:
            source_id: Data source ID.
            rows: List of row dicts to append.
        """
        resp = await self._http.post(f"/sources/{source_id}/rows", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())

    async def replace_data(
        self, source_id: str, *, rows: builtins.list[dict[str, Any]]
    ) -> DataWriteResult:
        """Replace all data in a source with new rows.

        Args:
            source_id: Data source ID.
            rows: Complete set of row dicts replacing all existing data.
        """
        resp = await self._http.put(f"/sources/{source_id}/data", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())

    async def ask(self, source_id: str, *, question: str) -> dict[str, Any]:
        """Ask a natural language question about a data source.

        Args:
            source_id: The source UUID.
            question: Natural language question string.

        Returns:
            Dict with answer text and optional data rows.
        """
        resp = await self._http.post(
            f"/sources/{source_id}/ask",
            json={"question": question},
        )
        return resp.json()  # type: ignore[no-any-return]
