"""Embed session type models for the Querri SDK."""

from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel


class EmbedSession(BaseModel):
    """An embed session token and metadata."""

    session_token: str
    expires_in: int
    user_id: Optional[str] = None


class EmbedSessionListItem(BaseModel):
    """An active embed session as returned by list."""

    session_token: str
    user_id: Optional[str] = None
    origin: Optional[str] = None
    created_at: Optional[Union[str, float]] = None
    auth_method: Optional[str] = None


class EmbedSessionList(BaseModel):
    """Response from listing embed sessions."""

    data: list[EmbedSessionListItem] = []
    count: int = 0


class EmbedSessionRevokeResponse(BaseModel):
    """Response from revoking an embed session."""

    session_id: str
    revoked: bool = True
