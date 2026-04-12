"""Data access type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Source(BaseModel):
    """A data source."""

    id: str  #: Unique data source identifier.
    name: str  #: Human-readable source name.
    columns: List[str] = []  #: Column names available in this source.
    column_types: Optional[Dict[str, str]] = None  #: Mapping of column name to type string.
    row_count: Optional[int] = None  #: Total number of rows in the source.
    access_controlled: Optional[bool] = None  #: Whether RLS is enabled for this source.
    updated_at: Optional[str] = None  #: ISO-8601 last-update timestamp.


class QueryResult(BaseModel):
    """Result of a SQL query against a source."""

    data: List[Dict[str, Any]] = []  #: Rows returned by the query.
    total_rows: int = 0  #: Total matching rows (may exceed page size).
    page: int = 1  #: Current page number (1-based).
    page_size: int = 100  #: Maximum rows per page.


class DataPage(BaseModel):
    """Paginated data from a source."""

    data: List[Dict[str, Any]] = []  #: Rows of source data.
    total_rows: Optional[int] = Field(default=None, alias="total_count")  #: Total rows available (API returns as total_count).
    page: Optional[int] = None  #: Current page number (1-based).
    page_size: Optional[int] = None  #: Maximum rows per page.
    columns: Optional[List[str]] = None  #: Column names for the data.

    model_config = {"populate_by_name": True}  # Accept both total_rows and total_count


class DataWriteResult(BaseModel):
    """Response from a data write operation (create, append, or replace)."""

    id: str  #: The source that was modified.
    name: str  #: Source name.
    columns: List[str] = []  #: Column names after the write.
    row_count: int  #: Total number of rows after the write.
    updated_at: Optional[str] = None  #: ISO-8601 last-update timestamp.


class DeleteResult(BaseModel):
    """Response from a data source deletion."""

    id: str  #: The source that was deleted.
    deleted: bool  #: Always ``True`` on success.
