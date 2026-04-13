"""File type models for the Querri SDK."""

from __future__ import annotations

from pydantic import BaseModel


class File(BaseModel):
    """An uploaded file."""

    id: str  #: Unique file identifier.
    name: str  #: Original file name including extension.
    size: int | None = None  #: File size in bytes.
    content_type: str | None = None  #: MIME type, e.g. ``"text/csv"``.
    created_by: str | None = None  #: User ID of the uploader.
    created_at: str | None = None  #: ISO-8601 upload timestamp.
    columns: list[str] | None = None  #: Column names (for tabular files).
    row_count: int | None = None  #: Number of data rows.
