"""Connector, source management, and data access resource."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._pagination import AsyncCursorPage, SyncCursorPage
from ..types.data import DataPage, DataWriteResult, DeleteResult, QueryResult, Source


class Sources:
    """Synchronous connector, source management, and data access resource.

    Usage::

        connectors = client.sources.list_connectors()
        sources = client.sources.list()
        result = client.sources.query(sql="SELECT * FROM data LIMIT 10", source_id="src_...")
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    # -- Connector management -----------------------------------------------

    def list_connectors(self) -> List[Dict[str, Any]]:
        """List available connector types with connection status.

        Returns:
            List of connector dicts with id, name, service, status.
        """
        resp = self._http.get("/connectors")
        body = resp.json()
        return body.get("data", [])

    # -- Source CRUD ---------------------------------------------------------

    def create(
        self,
        *,
        name: str,
        connector_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        return resp.json()

    def create_data_source(
        self,
        *,
        name: str,
        rows: List[Dict[str, Any]],
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

    def get(self, source_id: str) -> Dict[str, Any]:
        """Get source details.

        Args:
            source_id: The source UUID.

        Returns:
            Source detail dict.
        """
        resp = self._http.get(f"/sources/{source_id}")
        return resp.json()

    def list(self, *, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """List data sources for the organization.

        Args:
            search: Optional name substring filter (client-side).

        Returns:
            List of source summary dicts with id, name, service, connector_id, etc.
        """
        resp = self._http.get("/sources")
        body = resp.json()
        items = body.get("data", [])
        if search:
            search_lower = search.lower()
            items = [s for s in items if search_lower in s.get("name", "").lower()]
        return items

    def update(
        self,
        source_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update source configuration.

        Args:
            source_id: The source UUID.
            name: New display name.
            description: User notes about the source.
            config: Updated configuration dict.

        Returns:
            Dict with id and updated status.
        """
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if config is not None:
            payload["config"] = config
        resp = self._http.patch(f"/sources/{source_id}", json=payload)
        return resp.json()

    def delete(self, source_id: str) -> None:
        """Delete a data source.

        Args:
            source_id: The source UUID.
        """
        self._http.delete(f"/sources/{source_id}")

    def sync(self, source_id: str) -> Dict[str, Any]:
        """Trigger a source sync.

        Args:
            source_id: The source UUID.

        Returns:
            Dict with id and status ("sync_queued").
        """
        resp = self._http.post(f"/sources/{source_id}/sync")
        return resp.json()

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

    def append_rows(self, source_id: str, *, rows: List[Dict[str, Any]]) -> DataWriteResult:
        """Append rows to an existing data source.

        Args:
            source_id: Data source ID.
            rows: List of row dicts to append.
        """
        resp = self._http.post(f"/sources/{source_id}/rows", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())

    def replace_data(self, source_id: str, *, rows: List[Dict[str, Any]]) -> DataWriteResult:
        """Replace all data in a source with new rows.

        Args:
            source_id: Data source ID.
            rows: Complete set of row dicts replacing all existing data.
        """
        resp = self._http.put(f"/sources/{source_id}/data", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())

    def ask(self, source_id: str, *, question: str) -> Dict[str, Any]:
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
        return resp.json()


class AsyncSources:
    """Asynchronous connector, source management, and data access resource.

    Usage::

        connectors = await client.sources.list_connectors()
        sources = await client.sources.list()
        result = await client.sources.query(sql="SELECT * FROM data LIMIT 10", source_id="src_...")
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    # -- Connector management -----------------------------------------------

    async def list_connectors(self) -> List[Dict[str, Any]]:
        """List available connector types with connection status.

        Returns:
            List of connector dicts with id, name, service, status.
        """
        resp = await self._http.get("/connectors")
        body = resp.json()
        return body.get("data", [])

    # -- Source CRUD ---------------------------------------------------------

    async def create(
        self,
        *,
        name: str,
        connector_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        return resp.json()

    async def create_data_source(
        self,
        *,
        name: str,
        rows: List[Dict[str, Any]],
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

    async def get(self, source_id: str) -> Dict[str, Any]:
        """Get source details.

        Args:
            source_id: The source UUID.

        Returns:
            Source detail dict.
        """
        resp = await self._http.get(f"/sources/{source_id}")
        return resp.json()

    async def list(self, *, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """List data sources for the organization.

        Args:
            search: Optional name substring filter (client-side).

        Returns:
            List of source summary dicts with id, name, service, connector_id, etc.
        """
        resp = await self._http.get("/sources")
        body = resp.json()
        items = body.get("data", [])
        if search:
            search_lower = search.lower()
            items = [s for s in items if search_lower in s.get("name", "").lower()]
        return items

    async def update(
        self,
        source_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update source configuration.

        Args:
            source_id: The source UUID.
            name: New display name.
            description: User notes about the source.
            config: Updated configuration dict.

        Returns:
            Dict with id and updated status.
        """
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if config is not None:
            payload["config"] = config
        resp = await self._http.patch(f"/sources/{source_id}", json=payload)
        return resp.json()

    async def delete(self, source_id: str) -> None:
        """Delete a data source.

        Args:
            source_id: The source UUID.
        """
        await self._http.delete(f"/sources/{source_id}")

    async def sync(self, source_id: str) -> Dict[str, Any]:
        """Trigger a source sync.

        Args:
            source_id: The source UUID.

        Returns:
            Dict with id and status ("sync_queued").
        """
        resp = await self._http.post(f"/sources/{source_id}/sync")
        return resp.json()

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

    async def append_rows(self, source_id: str, *, rows: List[Dict[str, Any]]) -> DataWriteResult:
        """Append rows to an existing data source.

        Args:
            source_id: Data source ID.
            rows: List of row dicts to append.
        """
        resp = await self._http.post(f"/sources/{source_id}/rows", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())

    async def replace_data(self, source_id: str, *, rows: List[Dict[str, Any]]) -> DataWriteResult:
        """Replace all data in a source with new rows.

        Args:
            source_id: Data source ID.
            rows: Complete set of row dicts replacing all existing data.
        """
        resp = await self._http.put(f"/sources/{source_id}/data", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())

    async def ask(self, source_id: str, *, question: str) -> Dict[str, Any]:
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
        return resp.json()
