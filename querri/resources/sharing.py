"""Sharing resource — grant and revoke access to projects and dashboards."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from ..types.sharing import ShareEntry


class Sharing:
    """Synchronous sharing resource.

    Usage::

        client.sharing.share_project("proj_uuid", user_id="user_uuid", permission="edit")
        shares = client.sharing.list_project_shares("proj_uuid")
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    # ── Project sharing ──────────────────────────────────

    def share_project(
        self,
        project_id: str,
        *,
        user_id: str,
        permission: str = "view",
    ) -> ShareEntry:
        """Grant a user access to a project.

        Args:
            project_id: The project UUID.
            user_id: User ID or external ID to grant access to.
            permission: "view" or "edit".

        Returns:
            ShareEntry with user_id, permission, resource_type, resource_id, granted_by.
        """
        resp = self._http.post(
            f"/projects/{project_id}/shares",
            json={"user_id": user_id, "permission": permission},
        )
        return ShareEntry.model_validate(resp.json())

    def revoke_project_share(
        self,
        project_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Revoke a user's access to a project.

        Args:
            project_id: The project UUID.
            user_id: User ID or external ID to revoke.

        Returns:
            Dict with user_id, resource_type, resource_id, revoked status.
        """
        resp = self._http.delete(f"/projects/{project_id}/shares/{user_id}")
        return resp.json()

    def list_project_shares(self, project_id: str) -> List[ShareEntry]:
        """List who has access to a project.

        Args:
            project_id: The project UUID.

        Returns:
            List of ShareEntry objects with user_id and permission.
        """
        resp = self._http.get(f"/projects/{project_id}/shares")
        body = resp.json()
        return [ShareEntry.model_validate(s) for s in body.get("data", [])]

    # ── Dashboard sharing ────────────────────────────────

    def share_dashboard(
        self,
        dashboard_id: str,
        *,
        user_id: str,
        permission: str = "view",
    ) -> ShareEntry:
        """Grant a user access to a dashboard.

        Args:
            dashboard_id: The dashboard UUID.
            user_id: User ID or external ID to grant access to.
            permission: "view" or "edit".

        Returns:
            ShareEntry with user_id, permission, resource_type, resource_id, granted_by.
        """
        resp = self._http.post(
            f"/dashboards/{dashboard_id}/shares",
            json={"user_id": user_id, "permission": permission},
        )
        return ShareEntry.model_validate(resp.json())

    def revoke_dashboard_share(
        self,
        dashboard_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Revoke a user's access to a dashboard.

        Args:
            dashboard_id: The dashboard UUID.
            user_id: User ID or external ID to revoke.

        Returns:
            Dict with user_id, resource_type, resource_id, revoked status.
        """
        resp = self._http.delete(f"/dashboards/{dashboard_id}/shares/{user_id}")
        return resp.json()

    def list_dashboard_shares(self, dashboard_id: str) -> List[ShareEntry]:
        """List who has access to a dashboard.

        Args:
            dashboard_id: The dashboard UUID.

        Returns:
            List of ShareEntry objects with user_id and permission.
        """
        resp = self._http.get(f"/dashboards/{dashboard_id}/shares")
        body = resp.json()
        return [ShareEntry.model_validate(s) for s in body.get("data", [])]


class AsyncSharing:
    """Asynchronous sharing resource."""

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    # ── Project sharing ──────────────────────────────────

    async def share_project(
        self,
        project_id: str,
        *,
        user_id: str,
        permission: str = "view",
    ) -> ShareEntry:
        """Grant a user access to a project."""
        resp = await self._http.post(
            f"/projects/{project_id}/shares",
            json={"user_id": user_id, "permission": permission},
        )
        return ShareEntry.model_validate(resp.json())

    async def revoke_project_share(
        self,
        project_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Revoke a user's access to a project."""
        resp = await self._http.delete(f"/projects/{project_id}/shares/{user_id}")
        return resp.json()

    async def list_project_shares(self, project_id: str) -> List[ShareEntry]:
        """List who has access to a project."""
        resp = await self._http.get(f"/projects/{project_id}/shares")
        body = resp.json()
        return [ShareEntry.model_validate(s) for s in body.get("data", [])]

    # ── Dashboard sharing ────────────────────────────────

    async def share_dashboard(
        self,
        dashboard_id: str,
        *,
        user_id: str,
        permission: str = "view",
    ) -> ShareEntry:
        """Grant a user access to a dashboard."""
        resp = await self._http.post(
            f"/dashboards/{dashboard_id}/shares",
            json={"user_id": user_id, "permission": permission},
        )
        return ShareEntry.model_validate(resp.json())

    async def revoke_dashboard_share(
        self,
        dashboard_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Revoke a user's access to a dashboard."""
        resp = await self._http.delete(f"/dashboards/{dashboard_id}/shares/{user_id}")
        return resp.json()

    async def list_dashboard_shares(self, dashboard_id: str) -> List[ShareEntry]:
        """List who has access to a dashboard."""
        resp = await self._http.get(f"/dashboards/{dashboard_id}/shares")
        body = resp.json()
        return [ShareEntry.model_validate(s) for s in body.get("data", [])]
