"""API key type models for the Querri SDK."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class ApiKey(BaseModel):
    """An API key (never includes the secret except on creation)."""

    id: str  #: Unique API key identifier.
    name: str  #: Human-readable key name.
    key_prefix: str  #: First characters of the key for identification.
    scopes: List[str] = []  #: Permission scopes granted to this key.
    status: str = "active"  #: Key status, e.g. ``"active"`` or ``"revoked"``.
    created_by: Optional[str] = None  #: User ID of the key creator.
    created_at: Optional[str] = None  #: ISO-8601 creation timestamp.
    last_used_at: Optional[str] = None  #: ISO-8601 timestamp of last use.
    expires_at: Optional[str] = None  #: ISO-8601 expiration timestamp, if set.
    rate_limit_per_minute: int = 60  #: Max requests allowed per minute.


class ApiKeyCreated(ApiKey):
    """Response from creating an API key. Includes the secret ONCE."""

    secret: str  #: Full API key secret; only returned at creation time.
