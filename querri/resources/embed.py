"""Embed session resources — maps to /embed endpoints."""

from __future__ import annotations

import re
from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._convenience import async_get_session, sync_get_session, validate_ttl
from ..types.embed import (
    EmbedSession,
    EmbedSessionList,
    EmbedSessionRevokeResponse,
)

# The server clamps session listings at 200 per request and offers no cursor,
# so revoke_user_sessions pages by revoke-and-relist. This bounds the loop for
# pathological cases (e.g. sessions recreated concurrently faster than we
# revoke them).
_REVOKE_MAX_PASSES = 50
_LIST_SESSIONS_MAX_LIMIT = 200


def _ui_config_url(base_url: str) -> str:
    """Derive the main-app ui-config URL from the /api/v1 base URL.

    ``GET /api/embed/ui-config`` lives on the main app path, not the public
    ``/api/v1`` API — it is public, unauthenticated, and rate-limited.
    """
    host = re.sub(r"/api/v1/?$", "", base_url)
    return f"{host}/api/embed/ui-config"


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
        origin: str | None = None,
        ttl: int = 3600,
    ) -> EmbedSession:
        """Create an embed session for a user.

        Args:
            user_id: WorkOS user ID or external ID. Required.
            origin: Origin domain for validation. Required when the org
                configures an embed-domain allowlist (else the server
                responds ``400 origin_required``).
            ttl: Session TTL in seconds (900-86400, default 3600).

        Raises:
            ValueError: If ``ttl`` is outside [900, 86400].
            OriginRequiredError: If the org has a domain allowlist and no
                ``origin`` was passed.
        """
        validate_ttl(ttl)
        body: dict[str, Any] = {"user_id": user_id, "ttl": ttl}
        if origin is not None:
            body["origin"] = origin
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
            limit: Max sessions to return (1-200; the server clamps).
        """
        resp = self._http.get("/embed/sessions", params={"limit": limit})
        return EmbedSessionList.model_validate(resp.json())

    def revoke_session(
        self,
        session_id: str | None = None,
        *,
        session_token: str | None = None,
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
        user: str | dict[str, Any],
        access: dict[str, Any] | None = None,
        origin: str | None = None,
        ttl: int = 3600,
    ) -> dict[str, Any]:
        """Flagship convenience method.

        Get-or-create user, apply policy, create session.

        Args:
            user: External ID string, or dict with external_id, email, first_name, etc.
            access: Dict with policy_ids or inline spec (sources, filters).
            origin: Allowed origin for the embed session.
            ttl: Session TTL in seconds (900-86400).

        Returns:
            Embed session dict with token, expires_in, user_id, etc.
        """
        return sync_get_session(
            self._http, user=user, access=access, origin=origin, ttl=ttl
        )

    def get_ui_config(self, org: str) -> dict[str, Any]:
        """Fetch the operator-configured embed UI config for an org.

        Calls ``GET {host}/api/embed/ui-config?org=...`` on the **main app
        path** (not ``/api/v1``). The endpoint is public, unauthenticated,
        and rate-limited per IP; embeds fetch it on load and merge their own
        ``QuerriEmbed.create()`` config on top (customer config wins).

        Args:
            org: Querri org UUID or WorkOS org ID.

        Returns:
            Raw config dict — ``{"chrome": ..., "theme": ..., "privacy": ...}``.
            The schema evolves server-side; unknown orgs return empty groups.
        """
        resp = self._http.get(
            _ui_config_url(self._http._config.base_url), params={"org": org}
        )
        return resp.json()  # type: ignore[no-any-return]

    def revoke_user_sessions(self, user_id: str) -> int:
        """Revoke all embed sessions for a user.

        The server lists at most 200 sessions per request and offers no
        cursor, so this loops revoke-and-relist until a listing contains no
        sessions for the user. Best-effort: with more than 200 concurrent
        sessions org-wide the listing is a sample, and sessions created
        while the loop runs may survive it.

        Args:
            user_id: The user whose sessions to revoke.

        Returns:
            Number of sessions revoked.
        """
        count = 0
        for _ in range(_REVOKE_MAX_PASSES):
            sessions = self.list_sessions(limit=_LIST_SESSIONS_MAX_LIMIT)
            matches = [s for s in sessions.data if s.user_id == user_id]
            if not matches:
                break
            for session in matches:
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
        origin: str | None = None,
        ttl: int = 3600,
    ) -> EmbedSession:
        """Create an embed session for a user.

        Args:
            user_id: WorkOS user ID or external ID. Required.
            origin: Origin domain for validation. Required when the org
                configures an embed-domain allowlist (else the server
                responds ``400 origin_required``).
            ttl: Session TTL in seconds (900-86400, default 3600).

        Raises:
            ValueError: If ``ttl`` is outside [900, 86400].
            OriginRequiredError: If the org has a domain allowlist and no
                ``origin`` was passed.
        """
        validate_ttl(ttl)
        body: dict[str, Any] = {"user_id": user_id, "ttl": ttl}
        if origin is not None:
            body["origin"] = origin
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
            limit: Max sessions to return (1-200; the server clamps).
        """
        resp = await self._http.get("/embed/sessions", params={"limit": limit})
        return EmbedSessionList.model_validate(resp.json())

    async def revoke_session(
        self,
        session_id: str | None = None,
        *,
        session_token: str | None = None,
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
        user: str | dict[str, Any],
        access: dict[str, Any] | None = None,
        origin: str | None = None,
        ttl: int = 3600,
    ) -> dict[str, Any]:
        """Flagship convenience method.

        Get-or-create user, apply policy, create session.

        Args:
            user: External ID string, or dict with external_id, email, first_name, etc.
            access: Dict with policy_ids or inline spec (sources, filters).
            origin: Allowed origin for the embed session.
            ttl: Session TTL in seconds (900-86400).

        Returns:
            Embed session dict with token, expires_in, user_id, etc.
        """
        return await async_get_session(
            self._http, user=user, access=access, origin=origin, ttl=ttl
        )

    async def get_ui_config(self, org: str) -> dict[str, Any]:
        """Fetch the operator-configured embed UI config for an org.

        Calls ``GET {host}/api/embed/ui-config?org=...`` on the **main app
        path** (not ``/api/v1``). The endpoint is public, unauthenticated,
        and rate-limited per IP; embeds fetch it on load and merge their own
        ``QuerriEmbed.create()`` config on top (customer config wins).

        Args:
            org: Querri org UUID or WorkOS org ID.

        Returns:
            Raw config dict — ``{"chrome": ..., "theme": ..., "privacy": ...}``.
            The schema evolves server-side; unknown orgs return empty groups.
        """
        resp = await self._http.get(
            _ui_config_url(self._http._config.base_url), params={"org": org}
        )
        return resp.json()  # type: ignore[no-any-return]

    async def revoke_user_sessions(self, user_id: str) -> int:
        """Revoke all embed sessions for a user.

        The server lists at most 200 sessions per request and offers no
        cursor, so this loops revoke-and-relist until a listing contains no
        sessions for the user. Best-effort: with more than 200 concurrent
        sessions org-wide the listing is a sample, and sessions created
        while the loop runs may survive it.

        Args:
            user_id: The user whose sessions to revoke.

        Returns:
            Number of sessions revoked.
        """
        count = 0
        for _ in range(_REVOKE_MAX_PASSES):
            sessions = await self.list_sessions(limit=_LIST_SESSIONS_MAX_LIMIT)
            matches = [s for s in sessions.data if s.user_id == user_id]
            if not matches:
                break
            for session in matches:
                await self.revoke_session(session.session_token)
                count += 1
        return count
