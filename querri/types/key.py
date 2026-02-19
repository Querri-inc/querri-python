"""API key type models for the Querri SDK."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class ApiKey(BaseModel):
    """An API key (never includes the secret except on creation)."""

    id: str
    name: str
    key_prefix: str
    scopes: List[str] = []
    status: str = "active"
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None
    rate_limit_per_minute: int = 60


class ApiKeyCreated(ApiKey):
    """Response from creating an API key. Includes the secret ONCE."""

    secret: str
