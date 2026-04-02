"""Sharing type models for the Querri SDK."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ShareEntry(BaseModel):
    """A permission grant on a shared resource.

    Grant responses include resource_type, resource_id, and granted_by.
    List responses include only user_id and permission.
    """

    user_id: str  #: User ID who has access.
    permission: str = "view"  #: Permission level: ``"view"`` or ``"edit"``.
    resource_type: Optional[str] = None  #: Type of shared resource (grant response only).
    resource_id: Optional[str] = None  #: ID of the shared resource (grant response only).
    granted_by: Optional[str] = None  #: User ID who granted access (grant response only).
