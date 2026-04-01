"""Project type models for the Querri SDK."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class StepSummary(BaseModel):
    """Summary of a step in a project."""

    id: str  #: Unique step identifier.
    name: str  #: Display name of the step.
    type: str  #: Step type, e.g. ``"sql"`` or ``"python"``.
    status: str  #: Execution status, e.g. ``"completed"`` or ``"error"``.
    order: int  #: Zero-based position of the step in the project.
    has_data: bool = False  #: ``True`` if the step produced tabular data.
    has_figure: bool = False  #: ``True`` if the step produced a figure.


class Project(BaseModel):
    """A Querri project."""

    id: str  #: Unique project identifier.
    name: str  #: Project display name.
    description: Optional[str] = None  #: Optional project description.
    status: str = "idle"  #: Current status, e.g. ``"idle"`` or ``"running"``.
    step_count: Optional[int] = None  #: Number of steps in the project.
    chat_count: Optional[int] = None  #: Number of chats on the project.
    created_by: Optional[str] = None  #: User ID of the project creator.
    created_at: Optional[str] = None  #: ISO-8601 creation timestamp.
    updated_at: Optional[str] = None  #: ISO-8601 last-update timestamp.
    steps: Optional[List[StepSummary]] = None  #: Only on detail responses.


class AddSourceResponse(BaseModel):
    """Response from adding a source to a project."""

    step_id: str
    project_id: str
    status: str = "running"


class ProjectDeleteResponse(BaseModel):
    """Response from deleting a project."""

    id: str  #: ID of the deleted project.
    deleted: bool = True  #: Whether the project was successfully deleted.


class ProjectRunResponse(BaseModel):
    """Response from submitting a project for execution."""

    id: str  #: Project identifier.
    run_id: str  #: Unique identifier for this execution run.
    status: str = "submitted"  #: Run status, e.g. ``"submitted"``.


class ProjectRunStatus(BaseModel):
    """Execution status for a project."""

    id: str  #: Project identifier.
    status: str  #: Current run status, e.g. ``"running"`` or ``"completed"``.
    is_running: bool = False  #: ``True`` if the project is currently executing.


class ProjectCancelResponse(BaseModel):
    """Response from cancelling a project execution."""

    id: str  #: Project identifier.
    cancelled: bool = True  #: Whether the run was successfully cancelled.
