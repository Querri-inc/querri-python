"""Connector and source management resource."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._base_client import AsyncHTTPClient, SyncHTTPClient


class Sources:
    """Synchronous connector and source management resource.

    Usage::

        connectors = client.sources.list_connectors()
        sources = client.sources.list()
        new_source = client.sources.create(name="My Source", connector_id="...", config={})
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def list_connectors(self) -> List[Dict[str, Any]]:
        """List available connector types with connection status.

        Returns:
            List of connector dicts with id, name, service, status.
        """
        resp = self._http.get("/connectors")
        body = resp.json()
        return body.get("data", [])

    def create(
        self,
        *,
        name: str,
        connector_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a data source.

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

    def get(self, source_id: str) -> Dict[str, Any]:
        """Get source details.

        Args:
            source_id: The source UUID.

        Returns:
            Source detail dict.
        """
        # Source detail is part of the list; use the sources list endpoint
        # with filtering, or the data resource. The sources route has
        # individual source in the list. We fetch the full list and filter.
        # Actually, looking at the API routes, there's no GET /sources/{id}
        # but there is PATCH and DELETE. We use list + filter.
        resp = self._http.get("/sources")
        body = resp.json()
        for s in body.get("data", []):
            if s.get("id") == source_id:
                return s
        from .._exceptions import NotFoundError

        raise NotFoundError(
            f"Source {source_id} not found.",
            status=404,
            type="not_found_error",
            code="source_not_found",
        )

    def list(self) -> List[Dict[str, Any]]:
        """List data sources for the organization.

        Returns:
            List of source summary dicts with id, name, service, connector_id, etc.
        """
        resp = self._http.get("/sources")
        body = resp.json()
        return body.get("data", [])

    def update(
        self,
        source_id: str,
        *,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update source configuration.

        Args:
            source_id: The source UUID.
            name: New display name.
            config: Updated configuration dict.

        Returns:
            Dict with id and updated status.
        """
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
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


class AsyncSources:
    """Asynchronous connector and source management resource.

    Usage::

        connectors = await client.sources.list_connectors()
        sources = await client.sources.list()
        new_source = await client.sources.create(name="My Source", connector_id="...", config={})
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def list_connectors(self) -> List[Dict[str, Any]]:
        """List available connector types with connection status.

        Returns:
            List of connector dicts with id, name, service, status.
        """
        resp = await self._http.get("/connectors")
        body = resp.json()
        return body.get("data", [])

    async def create(
        self,
        *,
        name: str,
        connector_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a data source.

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

    async def get(self, source_id: str) -> Dict[str, Any]:
        """Get source details.

        Args:
            source_id: The source UUID.

        Returns:
            Source detail dict.
        """
        resp = await self._http.get("/sources")
        body = resp.json()
        for s in body.get("data", []):
            if s.get("id") == source_id:
                return s
        from .._exceptions import NotFoundError

        raise NotFoundError(
            f"Source {source_id} not found.",
            status=404,
            type="not_found_error",
            code="source_not_found",
        )

    async def list(self) -> List[Dict[str, Any]]:
        """List data sources for the organization.

        Returns:
            List of source summary dicts with id, name, service, connector_id, etc.
        """
        resp = await self._http.get("/sources")
        body = resp.json()
        return body.get("data", [])

    async def update(
        self,
        source_id: str,
        *,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update source configuration.

        Args:
            source_id: The source UUID.
            name: New display name.
            config: Updated configuration dict.

        Returns:
            Dict with id and updated status.
        """
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
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
