"""File type models for the Querri SDK."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class File(BaseModel):
    """An uploaded file."""

    id: str
    name: str
    size: Optional[int] = None
    content_type: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
