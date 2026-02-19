"""Usage type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class UsageReport(BaseModel):
    """Usage statistics report."""

    period_start: Optional[str] = None
    period_end: Optional[str] = None
    total_queries: Optional[int] = None
    total_tokens: Optional[int] = None
    total_projects: Optional[int] = None
    total_users: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
