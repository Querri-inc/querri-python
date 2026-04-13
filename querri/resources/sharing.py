"""Sharing resource — grant and revoke access to projects and dashboards."""

from __future__ import annotations

from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from ..types.sharing import ShareEntry


class Sharing:
    """Synchronous sharing resource.

    Usage::

        client.sharing.share_project(
            "proj_uuid",
            user_id="user_uuid",
            permission="edit",
        )
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
    ) -> dict[str, Any]:
        """Revoke a user's access to a project.

        Args:
            project_id: The project UUID.
            user_id: User ID or external ID to revoke.

        Returns:
            Dict with user_id, resource_type, resource_id, revoked status.
        """
        resp = self._http.delete(f"/projects/{project_id}/shares/{user_id}")
        return resp.json()

    def list_project_shares(self, project_id: str) -> list[ShareEntry]:
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
    ) -> dict[str, Any]:
        """Revoke a user's access to a dashboard.

        Args:
            dashboard_id: The dashboard UUID.
            user_id: User ID or external ID to revoke.

        Returns:
            Dict with user_id, resource_type, resource_id, revoked status.
        """
        resp = self._http.delete(f"/dashboards/{dashboard_id}/shares/{user_id}")
        return resp.json()

    def list_dashboard_shares(self, dashboard_id: str) -> list[ShareEntry]:
        """List who has access to a dashboard.

        Args:
            dashboard_id: The dashboard UUID.

        Returns:
            List of ShareEntry objects with user_id and permission.
        """
        resp = self._http.get(f"/dashboards/{dashboard_id}/shares")
        body = resp.json()
        return [ShareEntry.model_validate(s) for s in body.get("data", [])]

    # ── Source sharing ────────────────────────────────────

    def share_source(
        self, source_id: str, *, user_id: str, permission: str = "view"
    ) -> ShareEntry:
        """Share a data source with a user.

        Args:
            source_id: Source ID to share.
            user_id: User ID to share with.
            permission: ``"view"`` or ``"edit"`` (default: ``"view"``).
        """
        resp = self._http.post(
            f"/sources/{source_id}/shares",
            json={"user_id": user_id, "permission": permission},
        )
        return ShareEntry.model_validate(resp.json())

    def org_share_source(
        self, source_id: str, *, enabled: bool, permission: str = "view"
    ) -> dict[str, Any]:
        """Enable or disable org-wide sharing for a data source.

        Args:
            source_id: Source ID.
            enabled: Whether org-wide sharing is enabled.
            permission: ``"view"`` or ``"edit"`` (default: ``"view"``).
        """
        resp = self._http.post(
            f"/sources/{source_id}/org-share",
            json={"enabled": enabled, "permission": permission},
        )
        return resp.json()


class AsyncSharing:
    """Asynchronous sharing resource.

    Usage::

        await client.sharing.share_project(
            "proj_uuid",
            user_id="user_uuid",
            permission="edit",
        )
        shares = await client.sharing.list_project_shares("proj_uuid")
    """

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
        """Grant a user access to a project.

        Args:
            project_id: The project UUID.
            user_id: User ID or external ID to grant access to.
            permission: "view" or "edit".

        Returns:
            ShareEntry with user_id, permission, resource_type, resource_id, granted_by.
        """
        resp = await self._http.post(
            f"/projects/{project_id}/shares",
            json={"user_id": user_id, "permission": permission},
        )
        return ShareEntry.model_validate(resp.json())

    async def revoke_project_share(
        self,
        project_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Revoke a user's access to a project.

        Args:
            project_id: The project UUID.
            user_id: User ID or external ID to revoke.

        Returns:
            Dict with user_id, resource_type, resource_id, revoked status.
        """
        resp = await self._http.delete(f"/projects/{project_id}/shares/{user_id}")
        return resp.json()

    async def list_project_shares(self, project_id: str) -> list[ShareEntry]:
        """List who has access to a project.

        Args:
            project_id: The project UUID.

        Returns:
            List of ShareEntry objects with user_id and permission.
        """
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
        """Grant a user access to a dashboard.

        Args:
            dashboard_id: The dashboard UUID.
            user_id: User ID or external ID to grant access to.
            permission: "view" or "edit".

        Returns:
            ShareEntry with user_id, permission, resource_type, resource_id, granted_by.
        """
        resp = await self._http.post(
            f"/dashboards/{dashboard_id}/shares",
            json={"user_id": user_id, "permission": permission},
        )
        return ShareEntry.model_validate(resp.json())

    async def revoke_dashboard_share(
        self,
        dashboard_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Revoke a user's access to a dashboard.

        Args:
            dashboard_id: The dashboard UUID.
            user_id: User ID or external ID to revoke.

        Returns:
            Dict with user_id, resource_type, resource_id, revoked status.
        """
        resp = await self._http.delete(f"/dashboards/{dashboard_id}/shares/{user_id}")
        return resp.json()

    async def list_dashboard_shares(self, dashboard_id: str) -> list[ShareEntry]:
        """List who has access to a dashboard.

        Args:
            dashboard_id: The dashboard UUID.

        Returns:
            List of ShareEntry objects with user_id and permission.
        """
        resp = await self._http.get(f"/dashboards/{dashboard_id}/shares")
        body = resp.json()
        return [ShareEntry.model_validate(s) for s in body.get("data", [])]

    # ── Source sharing ────────────────────────────────────

    async def share_source(
        self, source_id: str, *, user_id: str, permission: str = "view"
    ) -> ShareEntry:
        """Share a data source with a user.

        Args:
            source_id: Source ID to share.
            user_id: User ID to share with.
            permission: ``"view"`` or ``"edit"`` (default: ``"view"``).
        """
        resp = await self._http.post(
            f"/sources/{source_id}/shares",
            json={"user_id": user_id, "permission": permission},
        )
        return ShareEntry.model_validate(resp.json())

    async def org_share_source(
        self, source_id: str, *, enabled: bool, permission: str = "view"
    ) -> dict[str, Any]:
        """Enable or disable org-wide sharing for a data source.

        Args:
            source_id: Source ID.
            enabled: Whether org-wide sharing is enabled.
            permission: ``"view"`` or ``"edit"`` (default: ``"view"``).
        """
        resp = await self._http.post(
            f"/sources/{source_id}/org-share",
            json={"enabled": enabled, "permission": permission},
        )
        return resp.json()
