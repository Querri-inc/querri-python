"""Dashboard resources for the Querri API.

Dashboards aggregate widgets from multiple projects.  The refresh endpoints
trigger re-execution of the underlying projects and report progress.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from ..types.dashboard import (
    Dashboard,
    DashboardDeleteResponse,
    DashboardRefreshResponse,
    DashboardRefreshStatus,
    DashboardUpdateResponse,
)


# ---------------------------------------------------------------------------
# Dashboards (sync)
# ---------------------------------------------------------------------------


class Dashboards:
    """Resource for dashboard operations.

    Example::

        # List dashboards
        dashboards = client.dashboards.list()

        # Create a dashboard
        dashboard = client.dashboards.create(name="Sales Overview")

        # Trigger a refresh
        client.dashboards.refresh(dashboard.id)
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    # -- CRUD ---------------------------------------------------------------

    def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
    ) -> Dashboard:
        """Create a new dashboard.

        Args:
            name: Dashboard name (1-200 chars).
            description: Optional description (max 1000 chars).

        Returns:
            Created Dashboard object.
        """
        body: Dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        response = self._http.post("/dashboards", json=body)
        return Dashboard.model_validate(response.json())

    def get(self, dashboard_id: str) -> Dashboard:
        """Get dashboard details including widgets.

        Args:
            dashboard_id: The dashboard UUID.

        Returns:
            Dashboard object with widgets and filters.
        """
        response = self._http.get(f"/dashboards/{dashboard_id}")
        return Dashboard.model_validate(response.json())

    def list(
        self,
        *,
        limit: int = 25,
        after: Optional[str] = None,
    ) -> List[Dashboard]:
        """List dashboards for the organization.

        Args:
            limit: Maximum number of dashboards to return.
            after: Cursor for the next page (if supported).

        Returns:
            List of Dashboard objects.
        """
        params: Dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        response = self._http.get("/dashboards", params=params)
        body = response.json()
        return [Dashboard.model_validate(d) for d in body.get("data", [])]

    def update(
        self,
        dashboard_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DashboardUpdateResponse:
        """Update dashboard metadata.

        Args:
            dashboard_id: The dashboard UUID.
            name: New dashboard name.
            description: New description.

        Returns:
            Response with id and updated flag.
        """
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        response = self._http.patch(f"/dashboards/{dashboard_id}", json=body)
        return DashboardUpdateResponse.model_validate(response.json())

    def delete(self, dashboard_id: str) -> None:
        """Delete a dashboard.

        Args:
            dashboard_id: The dashboard UUID.
        """
        self._http.delete(f"/dashboards/{dashboard_id}")

    # -- Refresh ------------------------------------------------------------

    def refresh(self, dashboard_id: str) -> DashboardRefreshResponse:
        """Trigger a refresh of all dashboard widgets.

        Re-executes the underlying projects for each widget.

        Args:
            dashboard_id: The dashboard UUID.

        Returns:
            Response with id, status ("refreshing"), and project_count.
        """
        response = self._http.post(f"/dashboards/{dashboard_id}/refresh")
        return DashboardRefreshResponse.model_validate(response.json())

    def refresh_status(self, dashboard_id: str) -> DashboardRefreshStatus:
        """Check the refresh status of a dashboard.

        Args:
            dashboard_id: The dashboard UUID.

        Returns:
            Status with id, status, and project_count.
        """
        response = self._http.get(f"/dashboards/{dashboard_id}/refresh/status")
        return DashboardRefreshStatus.model_validate(response.json())


# ---------------------------------------------------------------------------
# AsyncDashboards
# ---------------------------------------------------------------------------


class AsyncDashboards:
    """Async resource for dashboard operations.

    Example::

        dashboards = await client.dashboards.list()
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
    ) -> Dashboard:
        """Create a new dashboard."""
        body: Dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        response = await self._http.post("/dashboards", json=body)
        return Dashboard.model_validate(response.json())

    async def get(self, dashboard_id: str) -> Dashboard:
        """Get dashboard details including widgets."""
        response = await self._http.get(f"/dashboards/{dashboard_id}")
        return Dashboard.model_validate(response.json())

    async def list(
        self,
        *,
        limit: int = 25,
        after: Optional[str] = None,
    ) -> List[Dashboard]:
        """List dashboards for the organization."""
        params: Dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        response = await self._http.get("/dashboards", params=params)
        body = response.json()
        return [Dashboard.model_validate(d) for d in body.get("data", [])]

    async def update(
        self,
        dashboard_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DashboardUpdateResponse:
        """Update dashboard metadata."""
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        response = await self._http.patch(f"/dashboards/{dashboard_id}", json=body)
        return DashboardUpdateResponse.model_validate(response.json())

    async def delete(self, dashboard_id: str) -> None:
        """Delete a dashboard."""
        await self._http.delete(f"/dashboards/{dashboard_id}")

    async def refresh(self, dashboard_id: str) -> DashboardRefreshResponse:
        """Trigger a refresh of all dashboard widgets."""
        response = await self._http.post(f"/dashboards/{dashboard_id}/refresh")
        return DashboardRefreshResponse.model_validate(response.json())

    async def refresh_status(self, dashboard_id: str) -> DashboardRefreshStatus:
        """Check the refresh status of a dashboard."""
        response = await self._http.get(f"/dashboards/{dashboard_id}/refresh/status")
        return DashboardRefreshStatus.model_validate(response.json())
