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

**Reads** (:meth:`Workspaces.list`, :meth:`Workspaces.get`,
:meth:`Workspaces.members`) use the public ``/api/v1/workspaces`` routes and work
with an API key as well as a signed-in user. A user token sees the workspaces
its user can enter; an API key sees every workspace in the organization. Each
workspace carries ``kind`` — ``personal``, ``named`` or ``company`` (the org's
shared one).

**Writes** (:meth:`Workspaces.create`, :meth:`Workspaces.add_member`,
:meth:`Workspaces.move`) have no public route yet and still call the app's
``/api/v2/cms`` routes, which need a signed-in user (``querri auth login``).

The header is a *hint*: the server re-validates it against the caller's
membership and fails closed to the personal workspace when it cannot.
"""

from __future__ import annotations

import builtins
from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._exceptions import NotFoundError


def _looks_like_id(value: str) -> bool:
    return value == "repo_default" or value.startswith("workspace_")


def _match(
    workspaces: builtins.list[dict[str, Any]], ref: str
) -> dict[str, Any] | None:
    """A workspace by id, then slug, then exact name (case-insensitive)."""
    needle = ref.strip().lower()
    for key in ("id", "slug", "name"):
        for ws in workspaces:
            if str(ws.get(key, "")).lower() == needle:
                return ws
    return None


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

    def list(self) -> builtins.list[dict[str, Any]]:
        """Workspaces visible to the caller.

        A user token lists the workspaces its user can enter; an API key lists
        every workspace in the organization.

        Returns:
            Dicts with ``id``, ``name``, ``slug``, ``kind`` (``personal`` |
            ``named`` | ``company``) and ``member_count``.
        """
        resp = self._http.get("/workspaces")
        return builtins.list(resp.json().get("data", []))

    def get(self, workspace_id: str) -> dict[str, Any] | None:
        """One workspace, by id, slug or exact name; None if not visible.

        "Not a member" and "does not exist" answer identically (None), the same
        disclosure boundary the server keeps.

        Args:
            workspace_id: A workspace id (``workspace_…`` / ``repo_default``),
                slug, or exact name.

        Returns:
            The workspace dict, or None.
        """
        if not _looks_like_id(workspace_id):
            return _match(self.list(), workspace_id)
        try:
            resp = self._http.get(f"/workspaces/{workspace_id}")
        except NotFoundError:
            return None
        return dict(resp.json())

    def members(self, workspace_id: str) -> builtins.list[dict[str, Any]]:
        """The workspace's roster.

        Args:
            workspace_id: The workspace id.

        Returns:
            Dicts with ``user_id``, ``email``, ``name`` and ``role``.
        """
        resp = self._http.get(f"/workspaces/{workspace_id}/members")
        return builtins.list(resp.json().get("data", []))

    def create(
        self,
        name: str,
        *,
        slug: str | None = None,
        description: str = "",
        member_user_ids: builtins.list[str] | None = None,
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

    async def list(self) -> builtins.list[dict[str, Any]]:
        """Workspaces visible to the caller.

        A user token lists the workspaces its user can enter; an API key lists
        every workspace in the organization.

        Returns:
            Dicts with ``id``, ``name``, ``slug``, ``kind`` (``personal`` |
            ``named`` | ``company``) and ``member_count``.
        """
        resp = await self._http.get("/workspaces")
        return builtins.list(resp.json().get("data", []))

    async def get(self, workspace_id: str) -> dict[str, Any] | None:
        """One workspace, by id, slug or exact name; None if not visible.

        Args:
            workspace_id: A workspace id (``workspace_…`` / ``repo_default``),
                slug, or exact name.

        Returns:
            The workspace dict, or None.
        """
        if not _looks_like_id(workspace_id):
            return _match(await self.list(), workspace_id)
        try:
            resp = await self._http.get(f"/workspaces/{workspace_id}")
        except NotFoundError:
            return None
        return dict(resp.json())

    async def members(self, workspace_id: str) -> builtins.list[dict[str, Any]]:
        """The workspace's roster.

        Args:
            workspace_id: The workspace id.

        Returns:
            Dicts with ``user_id``, ``email``, ``name`` and ``role``.
        """
        resp = await self._http.get(f"/workspaces/{workspace_id}/members")
        return builtins.list(resp.json().get("data", []))

    async def create(
        self,
        name: str,
        *,
        slug: str | None = None,
        description: str = "",
        member_user_ids: builtins.list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a workspace. Requires an organization admin."""
        body: dict[str, Any] = {"name": name, "description": description}
        if slug:
            body["slug"] = slug
        if member_user_ids:
            body["member_user_ids"] = member_user_ids
        resp = await self._http.post(_cms(self._http, "/admin/workspaces"), json=body)
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
