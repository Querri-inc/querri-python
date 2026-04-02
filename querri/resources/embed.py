"""Embed session resources — maps to /embed endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._convenience import async_get_session, sync_get_session
from ..types.embed import (
    EmbedSession,
    EmbedSessionList,
    EmbedSessionRevokeResponse,
)


class Embed:
    """Synchronous embed session management.

    Usage::

        session = client.embed.create_session(user_id="usr_...")
        print(session.session_token)
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def create_session(
        self,
        *,
        user_id: str,
        origin: Optional[str] = None,
        ttl: int = 3600,
        source_scope: Optional[list[str]] = None,
    ) -> EmbedSession:
        """Create an embed session for a user.

        Args:
            user_id: WorkOS user ID or external ID. Required.
            origin: Origin domain for validation.
            ttl: Session TTL in seconds (900-86400, default 3600).
            source_scope: Optional list of source IDs to restrict session access.
        """
        body: dict[str, Any] = {"user_id": user_id, "ttl": ttl}
        if origin is not None:
            body["origin"] = origin
        if source_scope is not None:
            body["source_scope"] = source_scope
        resp = self._http.post("/embed/sessions", json=body)
        return EmbedSession.model_validate(resp.json())

    def refresh_session(self, *, session_token: str) -> EmbedSession:
        """Refresh an expiring embed session.

        Returns a new session token with the same user context.
        The old session is revoked.

        Args:
            session_token: The ``es_`` session token to refresh.
        """
        resp = self._http.post(
            "/embed/sessions/refresh",
            json={"session_token": session_token},
        )
        return EmbedSession.model_validate(resp.json())

    def list_sessions(self, *, limit: int = 100) -> EmbedSessionList:
        """List active embed sessions for the organization.

        Best-effort listing via Redis SCAN. Sessions may expire between
        scan and response.

        Args:
            limit: Max sessions to return (1-200).
        """
        resp = self._http.get("/embed/sessions", params={"limit": limit})
        return EmbedSessionList.model_validate(resp.json())

    def revoke_session(
        self,
        session_id: Optional[str] = None,
        *,
        session_token: Optional[str] = None,
    ) -> EmbedSessionRevokeResponse:
        """Revoke an embed session.

        Accepts either ``session_id`` or ``session_token`` (they are the same
        ``es_`` value).  ``session_token`` is provided for consistency with
        :meth:`refresh_session`.

        Args:
            session_id: The ``es_`` session token to revoke (positional, legacy).
            session_token: Alias for ``session_id`` (keyword, preferred).
        """
        token = session_id or session_token
        if token is None:
            raise ValueError("Either session_id or session_token must be provided")
        resp = self._http.delete(f"/embed/sessions/{token}")
        return EmbedSessionRevokeResponse.model_validate(resp.json())

    def get_session(
        self,
        *,
        user: Union[str, Dict[str, Any]],
        access: Optional[Dict[str, Any]] = None,
        origin: Optional[str] = None,
        ttl: int = 3600,
    ) -> Dict[str, Any]:
        """Flagship convenience method: get-or-create user, apply policy, create session.

        Args:
            user: External ID string, or dict with external_id, email, first_name, etc.
            access: Dict with policy_ids or inline spec (sources, filters).
            origin: Allowed origin for the embed session.
            ttl: Session TTL in seconds.

        Returns:
            Embed session dict with token, expires_in, user_id, etc.
        """
        return sync_get_session(self._http, user=user, access=access, origin=origin, ttl=ttl)

    def revoke_user_sessions(self, user_id: str) -> int:
        """Revoke all embed sessions for a user.

        Args:
            user_id: The user whose sessions to revoke.

        Returns:
            Number of sessions revoked.
        """
        sessions = self.list_sessions()
        count = 0
        for session in sessions.data:
            if session.user_id == user_id:
                self.revoke_session(session.session_token)
                count += 1
        return count


class AsyncEmbed:
    """Asynchronous embed session management.

    Usage::

        session = await client.embed.create_session(user_id="usr_...")
        print(session.session_token)
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create_session(
        self,
        *,
        user_id: str,
        origin: Optional[str] = None,
        ttl: int = 3600,
        source_scope: Optional[List[str]] = None,
    ) -> EmbedSession:
        """Create an embed session for a user.

        Args:
            user_id: WorkOS user ID or external ID. Required.
            origin: Origin domain for validation.
            ttl: Session TTL in seconds (900-86400, default 3600).
        """
        body: dict[str, Any] = {"user_id": user_id, "ttl": ttl}
        if origin is not None:
            body["origin"] = origin
        if source_scope is not None:
            body["source_scope"] = source_scope
        resp = await self._http.post("/embed/sessions", json=body)
        return EmbedSession.model_validate(resp.json())

    async def refresh_session(self, *, session_token: str) -> EmbedSession:
        """Refresh an expiring embed session.

        Returns a new session token with the same user context.
        The old session is revoked.

        Args:
            session_token: The ``es_`` session token to refresh.
        """
        resp = await self._http.post(
            "/embed/sessions/refresh",
            json={"session_token": session_token},
        )
        return EmbedSession.model_validate(resp.json())

    async def list_sessions(self, *, limit: int = 100) -> EmbedSessionList:
        """List active embed sessions for the organization.

        Best-effort listing via Redis SCAN. Sessions may expire between
        scan and response.

        Args:
            limit: Max sessions to return (1-200).
        """
        resp = await self._http.get("/embed/sessions", params={"limit": limit})
        return EmbedSessionList.model_validate(resp.json())

    async def revoke_session(
        self,
        session_id: Optional[str] = None,
        *,
        session_token: Optional[str] = None,
    ) -> EmbedSessionRevokeResponse:
        """Revoke an embed session.

        Accepts either ``session_id`` or ``session_token`` (they are the same
        ``es_`` value).  ``session_token`` is provided for consistency with
        :meth:`refresh_session`.

        Args:
            session_id: The ``es_`` session token to revoke (positional, legacy).
            session_token: Alias for ``session_id`` (keyword, preferred).
        """
        token = session_id or session_token
        if token is None:
            raise ValueError("Either session_id or session_token must be provided")
        resp = await self._http.delete(f"/embed/sessions/{token}")
        return EmbedSessionRevokeResponse.model_validate(resp.json())

    async def get_session(
        self,
        *,
        user: Union[str, Dict[str, Any]],
        access: Optional[Dict[str, Any]] = None,
        origin: Optional[str] = None,
        ttl: int = 3600,
    ) -> Dict[str, Any]:
        """Flagship convenience method: get-or-create user, apply policy, create session.

        Args:
            user: External ID string, or dict with external_id, email, first_name, etc.
            access: Dict with policy_ids or inline spec (sources, filters).
            origin: Allowed origin for the embed session.
            ttl: Session TTL in seconds.

        Returns:
            Embed session dict with token, expires_in, user_id, etc.
        """
        return await async_get_session(self._http, user=user, access=access, origin=origin, ttl=ttl)

    async def revoke_user_sessions(self, user_id: str) -> int:
        """Revoke all embed sessions for a user.

        Args:
            user_id: The user whose sessions to revoke.

        Returns:
            Number of sessions revoked.
        """
        sessions = await self.list_sessions()
        count = 0
        for session in sessions.data:
            if session.user_id == user_id:
                await self.revoke_session(session.session_token)
                count += 1
        return count
