"""Data access type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Source(BaseModel):
    """A data source."""

    id: str
    name: str
    columns: List[str] = []
    row_count: Optional[int] = None
    updated_at: Optional[str] = None


class QueryResult(BaseModel):
    """Result of a SQL query against a source."""

    data: List[Dict[str, Any]] = []
    total_rows: int = 0
    page: int = 1
    page_size: int = 100


class DataPage(BaseModel):
    """Paginated data from a step result."""

    data: List[Dict[str, Any]] = []
    total_rows: Optional[int] = None
    page: Optional[int] = None
    page_size: Optional[int] = None
    columns: Optional[List[str]] = None
