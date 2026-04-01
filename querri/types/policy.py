"""Access policy type models for the Querri SDK."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RowFilter(BaseModel):
    """A single row-level filter condition."""

    column: str  #: Column name to filter on.
    values: List[str]  #: Allowed values for the column.


class Policy(BaseModel):
    """An access policy (RLS rule set)."""

    id: str  #: Unique policy identifier.
    name: str  #: Human-readable policy name.
    description: Optional[str] = None  #: Optional description of the policy.
    source_ids: List[str] = []  #: Data source IDs this policy applies to.
    row_filters: List[RowFilter] = []  #: Row-level filter conditions.
    user_count: int = 0  #: Number of users assigned to this policy.
    assigned_user_ids: Optional[List[str]] = Field(default=None, alias="user_ids")
    """Only present on get (detail) responses.

    Accepts both ``assigned_user_ids`` and ``user_ids`` from the API.
    """
    created_at: Optional[str] = None  #: ISO-8601 creation timestamp.
    updated_at: Optional[str] = None  #: ISO-8601 last-update timestamp.

    model_config = {"populate_by_name": True}


class PolicyDeleteResponse(BaseModel):
    """Response from deleting a policy."""

    id: str  #: ID of the deleted policy.
    deleted: bool = True  #: Whether the policy was successfully deleted.


class PolicyUpdateResponse(BaseModel):
    """Response from updating a policy."""

    id: str  #: ID of the updated policy.
    updated: bool = True  #: Whether the policy was successfully updated.


class PolicyAssignResponse(BaseModel):
    """Response from assigning users to a policy."""

    policy_id: str  #: ID of the policy users were assigned to.
    assigned_user_ids: List[str] = []  #: IDs of the newly assigned users.


class PolicyRemoveUserResponse(BaseModel):
    """Response from removing a user from a policy."""

    policy_id: str  #: ID of the policy the user was removed from.
    user_id: str  #: ID of the removed user.
    removed: bool = True  #: Whether the user was successfully removed.


class ResolvedFilters(BaseModel):
    """The effective filters resolved for a user+source pair."""

    row_filters: Dict[str, Any] = {}  #: Merged row-level filters keyed by column.
    has_any_policy: bool = False  #: ``True`` if at least one policy applies.


class ResolvedAccess(BaseModel):
    """Resolved access for a user+source combination."""

    user_id: str  #: The user whose access was resolved.
    source_id: str  #: The data source evaluated.
    source_is_access_controlled: bool = False  #: ``True`` if the source has RLS.
    effective_access: str = ""  #: Access level, e.g. ``"full"`` or ``"filtered"``.
    resolved_filters: ResolvedFilters = ResolvedFilters()  #: Effective filter set.
    where_clause: str = ""  #: SQL WHERE clause for the resolved filters.


class ColumnInfo(BaseModel):
    """Column metadata for a data source."""

    name: str  #: Column name.
    type: str = "string"  #: Column data type, e.g. ``"string"`` or ``"number"``.


class SourceColumns(BaseModel):
    """Columns available on a data source for RLS rule building."""

    source_id: str  #: Data source identifier.
    source_name: str = ""  #: Human-readable source name.
    columns: List[ColumnInfo] = []  #: Available columns on this source.


class PolicyReplaceResponse(BaseModel):
    """Response from atomically replacing a user's policy assignments."""

    user_id: str  #: The user whose policies were replaced.
    policy_ids: List[str]  #: Final set of policy IDs now assigned.
    added: List[str]  #: Policy IDs that were newly assigned.
    removed: List[str]  #: Policy IDs that were removed.
