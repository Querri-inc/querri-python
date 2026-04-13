"""Dashboard type models for the Querri SDK."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Dashboard(BaseModel):
    """A Querri dashboard."""

    id: str  #: Unique dashboard identifier.
    name: str  #: Dashboard display name.
    description: str | None = None  #: Optional dashboard description.
    widget_count: int = 0  #: Number of widgets on the dashboard.
    widgets: list[dict[str, Any]] | None = None  #: Only on detail responses.
    filters: list[dict[str, Any]] | None = None  #: Only on detail responses.
    created_by: str | None = None  #: User ID of the dashboard creator.
    created_at: str | None = None  #: ISO-8601 creation timestamp.
    updated_at: str | None = None  #: ISO-8601 last-update timestamp.


class DashboardUpdateResponse(BaseModel):
    """Response from updating a dashboard."""

    id: str  #: ID of the updated dashboard.
    updated: bool = True  #: Whether the dashboard was successfully updated.


class DashboardDeleteResponse(BaseModel):
    """Response from deleting a dashboard."""

    id: str  #: ID of the deleted dashboard.
    deleted: bool = True  #: Whether the dashboard was successfully deleted.


class DashboardRefreshResponse(BaseModel):
    """Response from triggering a dashboard refresh."""

    id: str  #: Dashboard identifier.
    status: str = "refreshing"  #: Refresh status, e.g. ``"refreshing"``.
    project_count: int = 0  #: Number of projects being refreshed.


class DashboardRefreshStatus(BaseModel):
    """Status of a dashboard refresh."""

    id: str  #: Dashboard identifier.
    status: str = "idle"  #: Current status, e.g. ``"idle"`` or ``"refreshing"``.
    project_count: int | None = None  #: Number of projects in the refresh.
