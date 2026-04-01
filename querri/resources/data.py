"""Data access resource — query sources and retrieve data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._pagination import AsyncCursorPage, SyncCursorPage
from ..types.data import DataPage, DataWriteResult, QueryResult, Source


class Data:
    """Synchronous data access resource.

    Usage::

        sources = client.data.sources()
        result = client.data.query(sql="SELECT * FROM data LIMIT 10", source_id="src_...")
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def create_source(
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
            "/data/sources",
            json={"name": name, "rows": rows},
        )
        return Source.model_validate(resp.json())

    def delete_source(self, source_id: str) -> Dict[str, Any]:
        """Delete a data source and its associated data.

        Args:
            source_id: The source UUID.

        Returns:
            Dict with id and deleted status.
        """
        resp = self._http.delete(f"/data/sources/{source_id}")
        return resp.json()

    def sources(
        self,
        *,
        limit: int = 25,
        after: Optional[str] = None,
    ) -> SyncCursorPage[Source]:
        """List available data sources with cursor pagination.

        Args:
            limit: Maximum number of sources per page (1-200).
            after: Cursor for the next page.

        Returns:
            Auto-paginating iterator of Source objects.
        """
        params: Dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        return SyncCursorPage(self._http, "/data/sources", Source, params=params)

    def source(self, source_id: str) -> Source:
        """Get source metadata and schema.

        Args:
            source_id: The source UUID.

        Returns:
            Source object with id, name, columns, row_count, updated_at.
        """
        resp = self._http.get(f"/data/sources/{source_id}")
        return Source.model_validate(resp.json())

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
            "/data/query",
            json={
                "sql": sql,
                "source_id": source_id,
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
            f"/data/sources/{source_id}/data",
            params={"page": page, "page_size": page_size},
        )
        return DataPage.model_validate(resp.json())

    def append_rows(self, source_id: str, *, rows: List[Dict[str, Any]]) -> DataWriteResult:
        """Append rows to an existing data source.

        Args:
            source_id: Data source ID.
            rows: List of row dicts to append.
        """
        resp = self._http.post(f"/data/sources/{source_id}/rows", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())

    def replace_data(self, source_id: str, *, rows: List[Dict[str, Any]]) -> DataWriteResult:
        """Replace all data in a source with new rows.

        Args:
            source_id: Data source ID.
            rows: Complete set of row dicts replacing all existing data.
        """
        resp = self._http.put(f"/data/sources/{source_id}/data", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())


class AsyncData:
    """Asynchronous data access resource.

    Usage::

        sources = await client.data.sources()
        result = await client.data.query(sql="SELECT * FROM data LIMIT 10", source_id="src_...")
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create_source(
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
            "/data/sources",
            json={"name": name, "rows": rows},
        )
        return Source.model_validate(resp.json())

    async def delete_source(self, source_id: str) -> Dict[str, Any]:
        """Delete a data source and its associated data.

        Args:
            source_id: The source UUID.

        Returns:
            Dict with id and deleted status.
        """
        resp = await self._http.delete(f"/data/sources/{source_id}")
        return resp.json()

    def sources(
        self,
        *,
        limit: int = 25,
        after: Optional[str] = None,
    ) -> AsyncCursorPage[Source]:
        """List available data sources with cursor pagination.

        Args:
            limit: Maximum number of sources per page (1-200).
            after: Cursor for the next page.

        Returns:
            Auto-paginating async iterator of Source objects.
        """
        params: Dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        return AsyncCursorPage(self._http, "/data/sources", Source, params=params)

    async def source(self, source_id: str) -> Source:
        """Get source metadata and schema.

        Args:
            source_id: The source UUID.

        Returns:
            Source object with id, name, columns, row_count, updated_at.
        """
        resp = await self._http.get(f"/data/sources/{source_id}")
        return Source.model_validate(resp.json())

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
            "/data/query",
            json={
                "sql": sql,
                "source_id": source_id,
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
            f"/data/sources/{source_id}/data",
            params={"page": page, "page_size": page_size},
        )
        return DataPage.model_validate(resp.json())

    async def append_rows(self, source_id: str, *, rows: List[Dict[str, Any]]) -> DataWriteResult:
        """Append rows to an existing data source.

        Args:
            source_id: Data source ID.
            rows: List of row dicts to append.
        """
        resp = await self._http.post(f"/data/sources/{source_id}/rows", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())

    async def replace_data(self, source_id: str, *, rows: List[Dict[str, Any]]) -> DataWriteResult:
        """Replace all data in a source with new rows.

        Args:
            source_id: Data source ID.
            rows: Complete set of row dicts replacing all existing data.
        """
        resp = await self._http.put(f"/data/sources/{source_id}/data", json={"rows": rows})
        return DataWriteResult.model_validate(resp.json())
