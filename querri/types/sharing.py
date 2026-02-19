"""Sharing type models for the Querri SDK."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ShareEntry(BaseModel):
    """A share link entry."""

    id: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    share_key: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
