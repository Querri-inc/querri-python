"""SQL-defined views resource."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

from .._base_client import AsyncHTTPClient, SyncHTTPClient


class Views:
    """Synchronous views resource.

    Usage::

        views = client.views.list()
        view = client.views.create(name="Revenue by Region", sql_definition="SELECT ...")
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def create(
        self,
        *,
        name: Optional[str] = None,
        sql_definition: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new SQL-defined view.

        All fields are optional — omit everything to create a draft view
        for NL authoring via ``chat()``.

        Args:
            name: Display name for the view.
            sql_definition: SQL query that defines the view.
            description: Optional description.

        Returns:
            Dict with view details including uuid, name, sql_definition.
        """
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if sql_definition is not None:
            payload["sql_definition"] = sql_definition
        if description is not None:
            payload["description"] = description
        resp = self._http.post("/views", json=payload)
        return resp.json()

    def list(self) -> List[Dict[str, Any]]:
        """List all views.

        Returns:
            List of view summary dicts.
        """
        resp = self._http.get("/views")
        body = resp.json()
        return body.get("data", body) if isinstance(body, dict) else body

    def get(self, view_uuid: str) -> Dict[str, Any]:
        """Get view details.

        Args:
            view_uuid: The view UUID.

        Returns:
            View detail dict.
        """
        resp = self._http.get(f"/views/{view_uuid}")
        return resp.json()

    def update(
        self,
        view_uuid: str,
        *,
        sql_definition: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a view.

        Args:
            view_uuid: The view UUID.
            sql_definition: Updated SQL definition.
            description: Updated description.

        Returns:
            Dict with updated view details.
        """
        payload: Dict[str, Any] = {}
        if sql_definition is not None:
            payload["sql_definition"] = sql_definition
        if description is not None:
            payload["description"] = description
        resp = self._http.patch(f"/views/{view_uuid}", json=payload)
        return resp.json()

    def delete(self, view_uuid: str) -> None:
        """Delete a view.

        Args:
            view_uuid: The view UUID.
        """
        self._http.delete(f"/views/{view_uuid}")

    def run(self, *, view_uuids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run view materialization.

        Args:
            view_uuids: Optional list of specific view UUIDs to materialize.
                If omitted, runs the full DAG.

        Returns:
            Dict with run status and details.
        """
        payload: Dict[str, Any] = {}
        if view_uuids is not None:
            payload["view_uuids"] = view_uuids
        resp = self._http.post("/views/run", json=payload)
        return resp.json()

    def preview(self, view_uuid: str, *, limit: int = 100) -> Dict[str, Any]:
        """Preview view results without materializing.

        Args:
            view_uuid: The view UUID.
            limit: Maximum number of rows to return.

        Returns:
            Dict with preview data rows and column info.
        """
        resp = self._http.post(
            f"/views/{view_uuid}/preview",
            json={"limit": limit},
        )
        return resp.json()

    def chat(self, view_uuid: str, *, message: str) -> Iterator[str]:
        """Send a message to the view authoring agent and stream the response.

        Args:
            view_uuid: The view UUID.
            message: Natural-language message for the agent.

        Yields:
            Raw SSE data lines from the agent response.
        """
        resp = self._http.request(
            "POST",
            f"/views/{view_uuid}/chat",
            json={"message": message},
            stream=True,
        )
        try:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    yield line[6:]
        finally:
            resp.close()

    def generate_metadata(self, view_uuid: str) -> Dict[str, Any]:
        """Generate name and description from the view's SQL and conversation.

        Args:
            view_uuid: The view UUID.

        Returns:
            Dict with generated name and description.
        """
        resp = self._http.post(f"/views/{view_uuid}/generate-metadata")
        return resp.json()


class AsyncViews:
    """Asynchronous views resource.

    Usage::

        views = await client.views.list()
        view = await client.views.create(name="Revenue by Region", sql_definition="SELECT ...")
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create(
        self,
        *,
        name: Optional[str] = None,
        sql_definition: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new SQL-defined view.

        All fields are optional — omit everything to create a draft view
        for NL authoring via ``chat()``.

        Args:
            name: Display name for the view.
            sql_definition: SQL query that defines the view.
            description: Optional description.

        Returns:
            Dict with view details including uuid, name, sql_definition.
        """
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if sql_definition is not None:
            payload["sql_definition"] = sql_definition
        if description is not None:
            payload["description"] = description
        resp = await self._http.post("/views", json=payload)
        return resp.json()

    async def list(self) -> List[Dict[str, Any]]:
        """List all views.

        Returns:
            List of view summary dicts.
        """
        resp = await self._http.get("/views")
        body = resp.json()
        return body.get("data", body) if isinstance(body, dict) else body

    async def get(self, view_uuid: str) -> Dict[str, Any]:
        """Get view details.

        Args:
            view_uuid: The view UUID.

        Returns:
            View detail dict.
        """
        resp = await self._http.get(f"/views/{view_uuid}")
        return resp.json()

    async def update(
        self,
        view_uuid: str,
        *,
        sql_definition: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a view.

        Args:
            view_uuid: The view UUID.
            sql_definition: Updated SQL definition.
            description: Updated description.

        Returns:
            Dict with updated view details.
        """
        payload: Dict[str, Any] = {}
        if sql_definition is not None:
            payload["sql_definition"] = sql_definition
        if description is not None:
            payload["description"] = description
        resp = await self._http.patch(f"/views/{view_uuid}", json=payload)
        return resp.json()

    async def delete(self, view_uuid: str) -> None:
        """Delete a view.

        Args:
            view_uuid: The view UUID.
        """
        await self._http.delete(f"/views/{view_uuid}")

    async def run(self, *, view_uuids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run view materialization.

        Args:
            view_uuids: Optional list of specific view UUIDs to materialize.
                If omitted, runs the full DAG.

        Returns:
            Dict with run status and details.
        """
        payload: Dict[str, Any] = {}
        if view_uuids is not None:
            payload["view_uuids"] = view_uuids
        resp = await self._http.post("/views/run", json=payload)
        return resp.json()

    async def preview(self, view_uuid: str, *, limit: int = 100) -> Dict[str, Any]:
        """Preview view results without materializing.

        Args:
            view_uuid: The view UUID.
            limit: Maximum number of rows to return.

        Returns:
            Dict with preview data rows and column info.
        """
        resp = await self._http.post(
            f"/views/{view_uuid}/preview",
            json={"limit": limit},
        )
        return resp.json()

    async def chat(self, view_uuid: str, *, message: str):
        """Send a message to the view authoring agent and stream the response.

        Args:
            view_uuid: The view UUID.
            message: Natural-language message for the agent.

        Yields:
            Raw SSE data lines from the agent response.
        """
        resp = await self._http.request(
            "POST",
            f"/views/{view_uuid}/chat",
            json={"message": message},
            stream=True,
        )
        try:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]
        finally:
            await resp.aclose()

    async def generate_metadata(self, view_uuid: str) -> Dict[str, Any]:
        """Generate name and description from the view's SQL and conversation.

        Args:
            view_uuid: The view UUID.

        Returns:
            Dict with generated name and description.
        """
        resp = await self._http.post(f"/views/{view_uuid}/generate-metadata")
        return resp.json()
