"""Usage type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class UsageReport(BaseModel):
    """Usage statistics report."""

    period_start: Optional[str] = None  #: ISO-8601 start of the reporting period.
    period_end: Optional[str] = None  #: ISO-8601 end of the reporting period.
    total_queries: Optional[int] = None  #: Number of queries executed in the period.
    total_tokens: Optional[int] = None  #: Total LLM tokens consumed in the period.
    total_projects: Optional[int] = None  #: Number of projects used in the period.
    total_users: Optional[int] = None  #: Number of active users in the period.
    details: Optional[Dict[str, Any]] = None  #: Breakdown of usage by category.
