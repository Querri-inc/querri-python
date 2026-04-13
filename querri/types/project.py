"""Project type models for the Querri SDK."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class StepSummary(BaseModel):
    """Summary of a step in a project."""

    id: str  #: Unique step identifier.
    name: str = ""  #: Display name of the step.
    type: str = ""  #: Step type, e.g. ``"duckdb_query"`` or ``"draw_figure"``.
    status: str = ""  #: Execution status, e.g. ``"complete"`` or ``"error"``.
    order: int = 0  #: Zero-based position of the step in the project.
    has_data: bool = False  #: ``True`` if the step produced tabular data.
    has_figure: bool = False  #: ``True`` if the step produced a figure.
    parent: str | None = None  #: Parent step UUID in the DAG.
    children: list[str] | None = None  #: Child step UUIDs.
    dependencies: list[str] | None = None  #: Dependency step UUIDs (data inputs).
    dependents: list[str] | None = None  #: Dependent step UUIDs (who uses this step's output).
    figure_url: str | None = None  #: URL of the step's figure, if any.
    message: str | None = None  #: Result message from step execution.
    num_rows: int | None = None  #: Number of rows in the step's data.
    num_cols: int | None = None  #: Number of columns in the step's data.
    headers: list[str] | None = None  #: Column headers for the step's data.


class Project(BaseModel):
    """A Querri project."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str  #: Unique project identifier.
    name: str  #: Project display name.
    description: str | None = None  #: Optional project description.
    status: str = "idle"  #: Current status, e.g. ``"idle"`` or ``"running"``.
    step_count: int | None = None  #: Number of steps in the project.
    chat_count: int | None = None  #: Number of chats on the project.
    created_by: str | None = None  #: User ID of the project creator.
    created_at: str | None = None  #: ISO-8601 creation timestamp.
    updated_at: str | None = None  #: ISO-8601 last-update timestamp.
    steps: list[StepSummary] | None = None  #: Only on detail responses.
    chats_store: dict[str, Any] | None = None  #: Raw chatsStore stashed from internal API.

    @model_validator(mode="before")
    @classmethod
    def _parse_step_store(cls, data: Any) -> Any:
        """Map the server's ``stepStore`` dict + ``stepOrder`` list into a ``steps`` list.

        The API returns ``stepStore: {uuid: {...}}`` and ``stepOrder: [uuid, ...]``.
        This validator transforms them into a flat ordered list of ``StepSummary``.
        """
        if not isinstance(data, dict):
            return data

        # Handle "uuid" → "id" mapping (server uses "uuid", SDK uses "id")
        if "uuid" in data and "id" not in data:
            data["id"] = data["uuid"]

        step_store: dict[str, Any] | None = data.get("stepStore")
        if step_store is None or not isinstance(step_store, dict):
            # Also populate step_count from num_steps if available
            if "num_steps" in data and "step_count" not in data:
                data["step_count"] = data["num_steps"]
            return data

        step_order: list[str] = data.get("stepOrder", list(step_store.keys()))

        steps: list[dict[str, Any]] = []
        for idx, uid in enumerate(step_order):
            raw = step_store.get(uid)
            if raw is None or not isinstance(raw, dict):
                continue
            # Skip deleted steps
            if raw.get("deleted_at"):
                continue

            result = raw.get("result") or {}
            has_data = bool(result.get("qdf") or result.get("qdf_uuid"))
            has_figure = bool(result.get("figure_url") or result.get("svg_url"))

            steps.append({
                "id": raw.get("uuid", uid),
                "name": raw.get("name", ""),
                "type": raw.get("tool", raw.get("type", "")),
                "status": raw.get("status", ""),
                "order": idx,
                "has_data": has_data,
                "has_figure": has_figure,
                "parent": raw.get("parent"),
                "children": raw.get("children", []),
                "dependencies": raw.get("dependencies", []),
                "dependents": raw.get("dependents", []),
                "figure_url": result.get("figure_url"),
                "message": result.get("message"),
                "num_rows": qdf.get("num_rows") if (qdf := result.get("qdf") or {}) else None,
                "num_cols": qdf.get("num_cols") if qdf else None,
                "headers": qdf.get("headers") if qdf else None,
            })

        data["steps"] = steps
        data["step_count"] = len(steps)

        # Stash chatsStore for chat show to extract messages from
        if "chatsStore" in data and isinstance(data["chatsStore"], dict):
            data["chats_store"] = data["chatsStore"]

        return data


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
