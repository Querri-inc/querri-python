"""Sharing type models for the Querri SDK."""

from __future__ import annotations

from pydantic import BaseModel


class ShareEntry(BaseModel):
    """A permission grant on a shared resource.

    Grant responses include resource_type, resource_id, and granted_by.
    List responses include only user_id and permission.
    """

    user_id: str  #: User ID who has access.
    permission: str = "view"  #: Permission level: ``"view"`` or ``"edit"``.
    resource_type: str | None = None  #: Type of shared resource (grant response only).
    resource_id: str | None = None  #: ID of the shared resource (grant response only).
    granted_by: str | None = None  #: User ID who granted access (grant response only).
