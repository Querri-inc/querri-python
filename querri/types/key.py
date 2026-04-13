"""API key type models for the Querri SDK."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiKey(BaseModel):
    """An API key (never includes the secret except on creation)."""

    id: str  #: Unique API key identifier.
    name: str  #: Human-readable key name.
    key_prefix: str  #: First characters of the key for identification.
    scopes: list[str] = []  #: Permission scopes granted to this key.
    status: str = "active"  #: Key status, e.g. ``"active"`` or ``"revoked"``.
    created_by: str | None = None  #: User ID of the key creator.
    created_at: str | None = None  #: ISO-8601 creation timestamp.
    last_used_at: str | None = None  #: ISO-8601 timestamp of last use.
    expires_at: str | None = None  #: ISO-8601 expiration timestamp, if set.
    rate_limit_per_minute: int = 60  #: Max requests allowed per minute.
    bound_user_id: str | None = None  #: User ID this key is bound to (detail only).
    source_scope: dict[str, Any] | None = None  #: Source access scope config (detail only).
    access_policy_ids: list[str] | None = None  #: Bound access policy IDs (detail only).
    ip_allowlist: list[str] | None = None  #: IP allowlist (detail only).


class ApiKeyCreated(ApiKey):
    """Response from creating an API key. Includes the secret ONCE."""

    secret: str  #: Full API key secret; only returned at creation time.
