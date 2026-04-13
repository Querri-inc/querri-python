"""Embed session type models for the Querri SDK."""

from __future__ import annotations

from pydantic import BaseModel


class EmbedSession(BaseModel):
    """An embed session token and metadata."""

    session_token: str  #: The ``es_``-prefixed token for iframe embedding.
    expires_in: int  #: Seconds until the session expires.
    user_id: str | None = None  #: Querri user ID, if the session is user-scoped.


class EmbedSessionListItem(BaseModel):
    """An active embed session as returned by list."""

    session_token: str  #: The ``es_``-prefixed session token.
    user_id: str | None = None  #: Querri user ID bound to this session.
    origin: str | None = None  #: Allowed origin URL for the embedded iframe.
    created_at: str | float | None = None  #: When the session was created.
    auth_method: str | None = None  #: Auth method used, e.g. ``"api_key"``.


class EmbedSessionList(BaseModel):
    """Response from listing embed sessions."""

    data: list[EmbedSessionListItem] = []  #: List of active embed sessions.
    has_more: bool = False  #: Whether more sessions exist beyond this page.
    next_cursor: str | None = None  #: Cursor for fetching the next page.


class EmbedSessionRevokeResponse(BaseModel):
    """Response from revoking an embed session."""

    id: str  #: ID of the revoked session.
    revoked: bool = True  #: Whether the session was successfully revoked.
