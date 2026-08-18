"""Workspaces — the rooms an organization's data lives in.

A workspace is where an object is *homed*. Homing decides two things: who can
see it by default, and what an agent searches when a question is asked from
inside that workspace. Every create the SDK performs carries the client's active
workspace as the ``X-Querri-Workspace`` header (see
:func:`querri._base_client._default_headers`), and every scoped read is narrowed
by the same header.

Set the active workspace once, on the client::

    client = Querri(workspace_id="ws_finance")
    client.files.upload("q3.csv")          # homed in ws_finance
    client.projects.create(name="Q3")      # homed in ws_finance

or from the CLI::

    querri workspace use finance
    querri file upload q3.csv --wait

**Two caveats worth knowing before you rely on this.**

1. Workspace scoping needs a signed-in user (``querri auth login``). Under API-key
   auth the server has no membership roster to validate the claim against, so the
   header is ignored and creates fall back to the key owner's personal workspace.
2. The header is a *hint*. The server re-validates it against your membership and
   fails closed to your personal workspace if you are not a member — a workspace
   you name but do not belong to never becomes an object's home.

These endpoints live under ``/api/v2/cms``, not ``/api/v1``, so they are built
against the host root rather than the client's base URL.
"""

from __future__ import annotations

from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient


def _cms(http: Any, path: str) -> str:
    """Absolute ``/api/v2/cms`` URL — httpx passes absolute URLs through unmerged."""
    return f"{http._config.host}/api/v2/cms{path}"


class Workspaces:
    """Synchronous workspace resource.

    Usage::

        for ws in client.workspaces.list():
            print(ws["id"], ws["name"])
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def list(self) -> list[dict[str, Any]]:
        """Workspaces you may enter, default (shared) first.

        This is the switcher's list — membership-driven, not "every workspace in
        the org". A workspace you are not a member of is absent here and would
        404 if you named it.
        """
        resp = self._http.get(_cms(self._http, "/workspaces"))
        return list(resp.json().get("workspaces", []))

    def get(self, workspace_id: str) -> dict[str, Any] | None:
        """One workspace summary, or None if you cannot enter it.

        Resolved from :meth:`list` rather than a per-id endpoint, so "not a
        member" and "does not exist" answer identically — the same disclosure
        boundary the server keeps.
        """
        for ws in self.list():
            if ws.get("id") == workspace_id or ws.get("slug") == workspace_id:
                return ws
        return None

    def create(
        self,
        name: str,
        *,
        slug: str | None = None,
        description: str = "",
        member_user_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a workspace. Requires an organization admin.

        A new workspace is PRIVATE until members are added; the creating admin is
        seeded as its first member. Pass ``member_user_ids`` to add others at
        creation.
        """
        body: dict[str, Any] = {"name": name, "description": description}
        if slug:
            body["slug"] = slug
        if member_user_ids:
            body["member_user_ids"] = member_user_ids
        resp = self._http.post(_cms(self._http, "/admin/workspaces"), json=body)
        return dict(resp.json())

    def members(self, workspace_id: str) -> dict[str, Any]:
        """The workspace's roster."""
        resp = self._http.get(_cms(self._http, f"/workspaces/{workspace_id}/members"))
        return dict(resp.json())

    def add_member(
        self, workspace_id: str, user_id: str, *, role: str = "member"
    ) -> dict[str, Any]:
        """Add (or re-role) a member. The default workspace rejects this — its
        membership mirrors organization roles."""
        resp = self._http.post(
            _cms(self._http, f"/workspaces/{workspace_id}/members"),
            json={"user_id": user_id, "role": role},
        )
        return dict(resp.json())

    def move(
        self,
        source_uuid: str,
        workspace_id: str,
        *,
        transfer_ownership: bool = False,
    ) -> dict[str, Any]:
        """Re-home an uploaded file/source into another workspace.

        Moves BOTH copies of the item's home (the DAM asset and the source
        document) in one call, so the object cannot end up in two rooms depending
        on which surface you arrive through.

        ``transfer_ownership`` must be True for a move that would cross an
        ownership boundary; it defaults to False so a move can never silently
        hand your object to someone else.

        Returns ``{item_id, workspace_id, transferred_ownership, changed,
        owner_granted}``. ``changed=False`` means it was already there.
        """
        resp = self._http.post(
            _cms(self._http, f"/items/asset/{source_uuid}/move"),
            json={
                "workspace_id": workspace_id,
                "transfer_ownership": transfer_ownership,
            },
        )
        return dict(resp.json())


class AsyncWorkspaces:
    """Asynchronous workspace resource. Mirrors :class:`Workspaces`."""

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def list(self) -> list[dict[str, Any]]:
        """Workspaces you may enter, default (shared) first."""
        resp = await self._http.get(_cms(self._http, "/workspaces"))
        return list(resp.json().get("workspaces", []))

    async def get(self, workspace_id: str) -> dict[str, Any] | None:
        """One workspace summary, or None if you cannot enter it."""
        for ws in await self.list():
            if ws.get("id") == workspace_id or ws.get("slug") == workspace_id:
                return ws
        return None

    async def create(
        self,
        name: str,
        *,
        slug: str | None = None,
        description: str = "",
        member_user_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a workspace. Requires an organization admin."""
        body: dict[str, Any] = {"name": name, "description": description}
        if slug:
            body["slug"] = slug
        if member_user_ids:
            body["member_user_ids"] = member_user_ids
        resp = await self._http.post(_cms(self._http, "/admin/workspaces"), json=body)
        return dict(resp.json())

    async def members(self, workspace_id: str) -> dict[str, Any]:
        """The workspace's roster."""
        resp = await self._http.get(
            _cms(self._http, f"/workspaces/{workspace_id}/members")
        )
        return dict(resp.json())

    async def add_member(
        self, workspace_id: str, user_id: str, *, role: str = "member"
    ) -> dict[str, Any]:
        """Add (or re-role) a member."""
        resp = await self._http.post(
            _cms(self._http, f"/workspaces/{workspace_id}/members"),
            json={"user_id": user_id, "role": role},
        )
        return dict(resp.json())

    async def move(
        self,
        source_uuid: str,
        workspace_id: str,
        *,
        transfer_ownership: bool = False,
    ) -> dict[str, Any]:
        """Re-home an uploaded file/source into another workspace."""
        resp = await self._http.post(
            _cms(self._http, f"/items/asset/{source_uuid}/move"),
            json={
                "workspace_id": workspace_id,
                "transfer_ownership": transfer_ownership,
            },
        )
        return dict(resp.json())


__all__ = ["Workspaces", "AsyncWorkspaces"]
