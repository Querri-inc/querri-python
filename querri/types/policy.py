"""Access policy type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RowFilter(BaseModel):
    """A single row-level filter condition."""

    column: str
    values: List[str]


class Policy(BaseModel):
    """An access policy (RLS rule set)."""

    id: str
    name: str
    description: Optional[str] = None
    source_ids: List[str] = []
    row_filters: List[RowFilter] = []
    user_count: int = 0
    assigned_user_ids: Optional[List[str]] = None
    """Only present on get (detail) responses."""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PolicyDeleteResponse(BaseModel):
    """Response from deleting a policy."""

    id: str
    deleted: bool = True


class PolicyUpdateResponse(BaseModel):
    """Response from updating a policy."""

    id: str
    updated: bool = True


class PolicyAssignResponse(BaseModel):
    """Response from assigning users to a policy."""

    policy_id: str
    assigned_user_ids: List[str] = []


class PolicyRemoveUserResponse(BaseModel):
    """Response from removing a user from a policy."""

    policy_id: str
    user_id: str
    removed: bool = True


class ResolvedAccess(BaseModel):
    """Resolved access for a user+source combination."""

    user_id: str
    source_id: str
    resolved_filters: List[Dict[str, Any]] = []
    where_clause: str = ""


class ColumnInfo(BaseModel):
    """Column metadata for a data source."""

    name: str
    type: str = "string"


class SourceColumns(BaseModel):
    """Columns available on a data source for RLS rule building."""

    source_id: str
    source_name: str = ""
    columns: List[ColumnInfo] = []
