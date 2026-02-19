"""Project type models for the Querri SDK."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class StepSummary(BaseModel):
    """Summary of a step in a project."""

    id: str
    name: str
    type: str
    status: str
    order: int
    has_data: bool = False
    has_figure: bool = False


class Project(BaseModel):
    """A Querri project."""

    id: str
    name: str
    description: Optional[str] = None
    status: str = "idle"
    step_count: Optional[int] = None
    chat_count: Optional[int] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    steps: Optional[List[StepSummary]] = None
    """Only present on detail responses."""


class ProjectDeleteResponse(BaseModel):
    """Response from deleting a project."""

    id: str
    deleted: bool = True


class ProjectRunResponse(BaseModel):
    """Response from submitting a project for execution."""

    id: str
    run_id: str
    status: str = "submitted"


class ProjectRunStatus(BaseModel):
    """Execution status for a project."""

    id: str
    status: str
    is_running: bool = False


class ProjectCancelResponse(BaseModel):
    """Response from cancelling a project execution."""

    id: str
    cancelled: bool = True
