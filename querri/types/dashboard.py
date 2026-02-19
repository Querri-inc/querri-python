"""Dashboard type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Dashboard(BaseModel):
    """A Querri dashboard."""

    id: str
    name: str
    description: Optional[str] = None
    widget_count: int = 0
    widgets: Optional[List[Dict[str, Any]]] = None
    """Only present on detail responses."""
    filters: Optional[List[Dict[str, Any]]] = None
    """Only present on detail responses."""
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DashboardUpdateResponse(BaseModel):
    """Response from updating a dashboard."""

    id: str
    updated: bool = True


class DashboardDeleteResponse(BaseModel):
    """Response from deleting a dashboard."""

    id: str
    deleted: bool = True


class DashboardRefreshResponse(BaseModel):
    """Response from triggering a dashboard refresh."""

    id: str
    status: str = "refreshing"
    project_count: int = 0


class DashboardRefreshStatus(BaseModel):
    """Status of a dashboard refresh."""

    id: str
    status: str = "idle"
    project_count: Optional[int] = None
