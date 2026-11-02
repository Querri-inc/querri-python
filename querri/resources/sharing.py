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
        return resp.json()  # type: ignore[no-any-return]

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
        return resp.json()  # type: ignore[no-any-return]

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
        return resp.json()  # type: ignore[no-any-return]

    # ── Workspace sharing ────────────────────────────────

    def list_workspace_shares(
        self, resource_type: str, resource_id: str
    ) -> list[dict[str, Any]]:
        """Workspaces an item is shared with.

        Args:
            resource_type: The item's type, as the server names it (e.g.
                ``"source"``, ``"project"``, ``"dashboard"``, ``"collection"``).
                Not checked client-side: the server's list is authoritative.
            resource_id: The item's id.

        Returns:
            ``[{"workspace_id", "relation"}]``.
        """
        resp = self._http.get(
            "/sharing/workspace",
            params={"resource_type": resource_type, "resource_id": resource_id},
        )
        return list(resp.json().get("data", []))

    def share_workspace(
        self,
        resource_type: str,
        resource_id: str,
        workspace_id: str,
        *,
        relation: str = "viewer",
    ) -> dict[str, Any]:
        """Share an item with every member of a workspace. The item stays
        where it is homed.

        Args:
            resource_type: The item's type, as the server names it. A type the
                server does not share raises ``ValidationError`` with its list.
            resource_id: The item's id.
            workspace_id: The workspace to share with.
            relation: ``"viewer"`` (default) or ``"editor"``.

        Returns:
            The server's confirmation.
        """
        resp = self._http.post(
            "/sharing/workspace",
            json={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "workspace_id": workspace_id,
                "relation": relation,
            },
        )
        return dict(resp.json())

    def unshare_workspace(
        self, resource_type: str, resource_id: str, workspace_id: str
    ) -> dict[str, Any]:
        """Stop sharing an item with a workspace.

        Takes no ``relation``: a workspace holds one grant level per item, and
        naming it would only make the revoke fail when the guess is wrong.

        Args:
            resource_type: The item's type, as the server names it.
            resource_id: The item's id.
            workspace_id: The workspace to un-share from.

        Returns:
            The server's confirmation.
        """
        resp = self._http.request(
            "DELETE",
            "/sharing/workspace",
            json={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "workspace_id": workspace_id,
            },
        )
        return dict(resp.json()) if resp.content else {}


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
        return resp.json()  # type: ignore[no-any-return]

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
        return resp.json()  # type: ignore[no-any-return]

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
        return resp.json()  # type: ignore[no-any-return]

    # ── Workspace sharing ────────────────────────────────

    async def list_workspace_shares(
        self, resource_type: str, resource_id: str
    ) -> list[dict[str, Any]]:
        """Workspaces an item is shared with.

        Args:
            resource_type: The item's type, as the server names it (e.g.
                ``"source"``, ``"project"``, ``"dashboard"``, ``"collection"``).
                Not checked client-side: the server's list is authoritative.
            resource_id: The item's id.

        Returns:
            ``[{"workspace_id", "relation"}]``.
        """
        resp = await self._http.get(
            "/sharing/workspace",
            params={"resource_type": resource_type, "resource_id": resource_id},
        )
        return list(resp.json().get("data", []))

    async def share_workspace(
        self,
        resource_type: str,
        resource_id: str,
        workspace_id: str,
        *,
        relation: str = "viewer",
    ) -> dict[str, Any]:
        """Share an item with every member of a workspace. The item stays
        where it is homed.

        Args:
            resource_type: The item's type, as the server names it. A type the
                server does not share raises ``ValidationError`` with its list.
            resource_id: The item's id.
            workspace_id: The workspace to share with.
            relation: ``"viewer"`` (default) or ``"editor"``.

        Returns:
            The server's confirmation.
        """
        resp = await self._http.post(
            "/sharing/workspace",
            json={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "workspace_id": workspace_id,
                "relation": relation,
            },
        )
        return dict(resp.json())

    async def unshare_workspace(
        self, resource_type: str, resource_id: str, workspace_id: str
    ) -> dict[str, Any]:
        """Stop sharing an item with a workspace.

        Takes no ``relation``: a workspace holds one grant level per item, and
        naming it would only make the revoke fail when the guess is wrong.

        Args:
            resource_type: The item's type, as the server names it.
            resource_id: The item's id.
            workspace_id: The workspace to un-share from.

        Returns:
            The server's confirmation.
        """
        resp = await self._http.request(
            "DELETE",
            "/sharing/workspace",
            json={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "workspace_id": workspace_id,
            },
        )
        return dict(resp.json()) if resp.content else {}
