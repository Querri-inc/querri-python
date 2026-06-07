"""Audit log resource."""

from __future__ import annotations

from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._pagination import AsyncCursorPage, SyncCursorPage
from ..types.audit import AuditEvent


class Audit:
    """Synchronous audit log resource.

    Usage::

        events = client.audit.list()
        events = client.audit.list(action="data.query", limit=10)
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def list(
        self,
        *,
        actor_id: str | None = None,
        target_id: str | None = None,
        action: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
        after: str | None = None,
    ) -> SyncCursorPage[AuditEvent]:
        """Query audit events for the organization with cursor pagination.

        Args:
            actor_id: Filter by actor (user or API key).
            target_id: Filter by target resource ID.
            action: Filter by action type (e.g. "data.query", "file.upload").
            start_date: ISO date string for range start.
            end_date: ISO date string for range end.
            limit: Max results per page (1-100).
            after: Cursor for pagination.

        Returns:
            Auto-paginating iterator of AuditEvent objects.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        if actor_id is not None:
            params["actor_id"] = actor_id
        if target_id is not None:
            params["target_id"] = target_id
        if action is not None:
            params["action"] = action
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        return SyncCursorPage(self._http, "/audit/events", AuditEvent, params=params)


class AsyncAudit:
    """Asynchronous audit log resource.

    Usage::

        events = await client.audit.list()
        events = await client.audit.list(action="data.query", limit=10)
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def list(
        self,
        *,
        actor_id: str | None = None,
        target_id: str | None = None,
        action: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
        after: str | None = None,
    ) -> AsyncCursorPage[AuditEvent]:
        """Query audit events for the organization with cursor pagination.

        Args:
            actor_id: Filter by actor (user or API key).
            target_id: Filter by target resource ID.
            action: Filter by action type (e.g. "data.query", "file.upload").
            start_date: ISO date string for range start.
            end_date: ISO date string for range end.
            limit: Max results per page (1-100).
            after: Cursor for pagination.

        Returns:
            Auto-paginating iterator of AuditEvent objects.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        if actor_id is not None:
            params["actor_id"] = actor_id
        if target_id is not None:
            params["target_id"] = target_id
        if action is not None:
            params["action"] = action
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        return AsyncCursorPage(self._http, "/audit/events", AuditEvent, params=params)
