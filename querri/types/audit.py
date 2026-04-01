"""Audit type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class AuditEvent(BaseModel):
    """A single audit event."""

    id: str  #: Unique audit event identifier.
    actor_id: str  #: ID of the user or system that performed the action.
    actor_type: str = "user"  #: Actor kind, e.g. ``"user"`` or ``"system"``.
    action: str  #: Action performed, e.g. ``"create"`` or ``"delete"``.
    target_type: Optional[str] = None  #: Resource type acted on, e.g. ``"project"``.
    target_id: Optional[str] = None  #: ID of the target resource.
    timestamp: Optional[str] = None  #: ISO-8601 timestamp of the event.
    ip_address: Optional[str] = None  #: IP address of the actor, if available.
    details: Optional[Dict[str, Any]] = None  #: Additional event-specific metadata.
