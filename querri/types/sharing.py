"""Sharing type models for the Querri SDK."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ShareEntry(BaseModel):
    """A share link entry."""

    id: str  #: Unique share entry identifier.
    resource_type: Optional[str] = None  #: Type of shared resource, e.g. ``"dashboard"``.
    resource_id: Optional[str] = None  #: ID of the shared resource.
    share_key: Optional[str] = None  #: Public key used in the share URL.
    created_by: Optional[str] = None  #: User ID of the share creator.
    created_at: Optional[str] = None  #: ISO-8601 creation timestamp.
    expires_at: Optional[str] = None  #: ISO-8601 expiration timestamp, if set.
