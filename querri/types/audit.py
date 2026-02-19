"""Audit type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class AuditEvent(BaseModel):
    """A single audit event."""

    id: str
    actor_id: str
    actor_type: str = "user"
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    timestamp: Optional[str] = None
    ip_address: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
