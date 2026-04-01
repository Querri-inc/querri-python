"""Data access type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Source(BaseModel):
    """A data source."""

    id: str  #: Unique data source identifier.
    name: str  #: Human-readable source name.
    columns: List[str] = []  #: Column names available in this source.
    row_count: Optional[int] = None  #: Total number of rows in the source.
    updated_at: Optional[str] = None  #: ISO-8601 last-update timestamp.


class QueryResult(BaseModel):
    """Result of a SQL query against a source."""

    data: List[Dict[str, Any]] = []  #: Rows returned by the query.
    total_rows: int = 0  #: Total matching rows (may exceed page size).
    page: int = 1  #: Current page number (1-based).
    page_size: int = 100  #: Maximum rows per page.


class DataPage(BaseModel):
    """Paginated data from a step result."""

    data: List[Dict[str, Any]] = []  #: Rows of step output data.
    total_rows: Optional[int] = None  #: Total rows available.
    page: Optional[int] = None  #: Current page number (1-based).
    page_size: Optional[int] = None  #: Maximum rows per page.
    columns: Optional[List[str]] = None  #: Column names for the data.


class DataWriteResult(BaseModel):
    """Response from a data write operation (append or replace)."""

    source_id: str  #: The source that was modified.
    rows_affected: int  #: Number of rows written.
