"""File type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class File(BaseModel):
    """An uploaded file."""

    id: str  #: Unique file identifier.
    name: str  #: Original file name including extension.
    size: Optional[int] = None  #: File size in bytes.
    content_type: Optional[str] = None  #: MIME type, e.g. ``"text/csv"``.
    created_by: Optional[str] = None  #: User ID of the uploader.
    created_at: Optional[str] = None  #: ISO-8601 upload timestamp.
    columns: Optional[List[str]] = None  #: Column names (for tabular files).
    row_count: Optional[int] = None  #: Number of data rows.
