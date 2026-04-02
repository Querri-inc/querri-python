"""Usage type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class DailyUsage(BaseModel):
    """Single day's usage count."""

    date: str  #: Date string (YYYY-MM-DD).
    count: int = 0  #: Number of AI messages on this date.


class OrgUsageReport(BaseModel):
    """Organization-level usage report."""

    org_id: Optional[str] = None  #: Organization ID.
    period: Optional[str] = None  #: Period name (current_month, last_month, last_30_days).
    period_start: Optional[str] = None  #: ISO-8601 start of the reporting period.
    period_end: Optional[str] = None  #: ISO-8601 end of the reporting period.
    total_ai_messages: Optional[int] = None  #: Total AI messages in the period.
    active_user_count: Optional[int] = None  #: Number of active users in the period.
    project_count: Optional[int] = None  #: Number of projects in the organization.


class UserUsageReport(BaseModel):
    """Per-user usage report."""

    user_id: Optional[str] = None  #: User ID.
    period: Optional[str] = None  #: Period name.
    period_start: Optional[str] = None  #: ISO-8601 start of the reporting period.
    period_end: Optional[str] = None  #: ISO-8601 end of the reporting period.
    ai_messages: Optional[int] = None  #: Total AI messages by this user.
    daily_breakdown: Optional[list[DailyUsage]] = None  #: Daily message counts.


# Keep backward compat alias
UsageReport = OrgUsageReport
