"""Data access type models for the Querri SDK."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Source(BaseModel):
    """A data source."""

    id: str  #: Unique data source identifier.
    name: str  #: Human-readable source name.
    columns: list[str] = []  #: Column names available in this source.
    column_types: dict[str, str] | None = (
        None  #: Mapping of column name to type string.
    )
    row_count: int | None = None  #: Total number of rows in the source.
    access_controlled: bool | None = None  #: Whether RLS is enabled for this source.
    updated_at: str | None = None  #: ISO-8601 last-update timestamp.


class QueryResult(BaseModel):
    """Result of a SQL query against a source."""

    data: list[dict[str, Any]] = []  #: Rows returned by the query.
    total_rows: int = 0  #: Total matching rows (may exceed page size).
    page: int = 1  #: Current page number (1-based).
    page_size: int = 100  #: Maximum rows per page.


class DataPage(BaseModel):
    """Paginated data from a source."""

    data: list[dict[str, Any]] = []  #: Rows of source data.
    total_rows: int | None = Field(
        default=None, alias="total_count"
    )  #: Total rows available (API returns as total_count).
    page: int | None = None  #: Current page number (1-based).
    page_size: int | None = None  #: Maximum rows per page.
    columns: list[str] | None = None  #: Column names for the data.

    model_config = {"populate_by_name": True}  # Accept both total_rows and total_count


class DataWriteResult(BaseModel):
    """Response from a data write operation (create, append, or replace)."""

    id: str  #: The source that was modified.
    name: str  #: Source name.
    columns: list[str] = []  #: Column names after the write.
    row_count: int  #: Total number of rows after the write.
    updated_at: str | None = None  #: ISO-8601 last-update timestamp.


class DeleteResult(BaseModel):
    """Response from a data source deletion."""

    id: str  #: The source that was deleted.
    deleted: bool  #: Always ``True`` on success.
