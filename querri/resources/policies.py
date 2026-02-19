"""Access policy resources — maps to /access endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._convenience import async_setup_policy, sync_setup_policy
from ..types.policy import (
    ColumnInfo,
    Policy,
    PolicyAssignResponse,
    PolicyDeleteResponse,
    PolicyRemoveUserResponse,
    PolicyUpdateResponse,
    ResolvedAccess,
    RowFilter,
    SourceColumns,
)


class Policies:
    """Synchronous access policy management.

    Usage::

        policy = client.policies.create(
            name="Sales Team",
            source_ids=["src_..."],
            row_filters=[{"column": "region", "values": ["US"]}],
        )
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
        row_filters: Optional[List[Dict[str, Any]]] = None,
    ) -> Policy:
        """Create an access policy.

        Args:
            name: Policy name.
            description: Optional description.
            source_ids: List of source IDs this policy applies to.
            row_filters: List of row filter dicts with ``column`` and ``values`` keys.
        """
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        if source_ids is not None:
            body["source_ids"] = source_ids
        if row_filters is not None:
            body["row_filters"] = row_filters
        resp = self._http.post("/access/policies", json=body)
        return Policy.model_validate(resp.json())

    def get(self, policy_id: str) -> Policy:
        """Get policy details including assigned user IDs.

        Args:
            policy_id: The policy UUID.
        """
        resp = self._http.get(f"/access/policies/{policy_id}")
        return Policy.model_validate(resp.json())

    def list(self, *, name: Optional[str] = None) -> List[Policy]:
        """List access policies for the organization.

        Note: This endpoint returns all policies (not cursor-paginated).
        The response is wrapped in ``{"data": [...]}``.

        Args:
            name: Filter by exact policy name.
        """
        params: dict[str, Any] = {}
        if name is not None:
            params["name"] = name
        resp = self._http.get("/access/policies", params=params)
        body = resp.json()
        return [Policy.model_validate(p) for p in body.get("data", [])]

    def update(
        self,
        policy_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
        row_filters: Optional[List[Dict[str, Any]]] = None,
    ) -> PolicyUpdateResponse:
        """Update an access policy.

        Args:
            policy_id: The policy UUID.
            name: New name.
            description: New description.
            source_ids: New source IDs.
            row_filters: New row filters.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if source_ids is not None:
            body["source_ids"] = source_ids
        if row_filters is not None:
            body["row_filters"] = row_filters
        resp = self._http.patch(f"/access/policies/{policy_id}", json=body)
        return PolicyUpdateResponse.model_validate(resp.json())

    def delete(self, policy_id: str) -> PolicyDeleteResponse:
        """Delete an access policy and all its user assignments.

        Args:
            policy_id: The policy UUID.
        """
        resp = self._http.delete(f"/access/policies/{policy_id}")
        return PolicyDeleteResponse.model_validate(resp.json())

    def assign_users(
        self,
        policy_id: str,
        *,
        user_ids: List[str],
    ) -> PolicyAssignResponse:
        """Assign users to a policy.

        Idempotent: already-assigned users are silently skipped.

        Args:
            policy_id: The policy UUID.
            user_ids: List of WorkOS user IDs to assign.
        """
        resp = self._http.post(
            f"/access/policies/{policy_id}/users",
            json={"user_ids": user_ids},
        )
        return PolicyAssignResponse.model_validate(resp.json())

    def remove_user(
        self,
        policy_id: str,
        user_id: str,
    ) -> PolicyRemoveUserResponse:
        """Remove a user from a policy.

        Args:
            policy_id: The policy UUID.
            user_id: The WorkOS user ID to remove.
        """
        resp = self._http.delete(
            f"/access/policies/{policy_id}/users/{user_id}"
        )
        return PolicyRemoveUserResponse.model_validate(resp.json())

    def resolve(
        self,
        *,
        user_id: str,
        source_id: str,
    ) -> ResolvedAccess:
        """Preview resolved access for a user+source combination.

        Returns the effective row filters and SQL WHERE clause that would
        be applied when querying the given source as the given user.

        Args:
            user_id: WorkOS user ID.
            source_id: Source UUID.
        """
        resp = self._http.post(
            "/access/resolve",
            json={"user_id": user_id, "source_id": source_id},
        )
        return ResolvedAccess.model_validate(resp.json())

    def columns(
        self,
        *,
        source_id: Optional[str] = None,
    ) -> List[SourceColumns]:
        """Discover filterable columns for RLS rule building.

        Returns column names and types from data sources so you can
        construct valid ``row_filters`` for access policies.

        Args:
            source_id: Optional source ID to filter to a single source.
        """
        params: dict[str, Any] = {}
        if source_id is not None:
            params["source_id"] = source_id
        resp = self._http.get("/access/columns", params=params)
        body = resp.json()
        return [SourceColumns.model_validate(s) for s in body.get("data", [])]


    def setup(
        self,
        *,
        name: str,
        sources: Optional[List[str]] = None,
        row_filters: Optional[Dict[str, Any]] = None,
        users: Optional[List[str]] = None,
        description: Optional[str] = None,
    ) -> Policy:
        """Create a policy and assign users in one call.

        Args:
            name: Policy name.
            sources: Source IDs this policy applies to.
            row_filters: Dict of column -> values for row filtering.
            users: User IDs to assign to the policy.
            description: Optional policy description.

        Returns:
            Created Policy object.
        """
        return sync_setup_policy(
            self._http, name=name, sources=sources,
            row_filters=row_filters, users=users,
        )


class AsyncPolicies:
    """Asynchronous access policy management.

    Usage::

        policy = await client.policies.create(
            name="Sales Team",
            source_ids=["src_..."],
            row_filters=[{"column": "region", "values": ["US"]}],
        )
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
        row_filters: Optional[List[Dict[str, Any]]] = None,
    ) -> Policy:
        """Create an access policy."""
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        if source_ids is not None:
            body["source_ids"] = source_ids
        if row_filters is not None:
            body["row_filters"] = row_filters
        resp = await self._http.post("/access/policies", json=body)
        return Policy.model_validate(resp.json())

    async def get(self, policy_id: str) -> Policy:
        """Get policy details including assigned user IDs."""
        resp = await self._http.get(f"/access/policies/{policy_id}")
        return Policy.model_validate(resp.json())

    async def list(self, *, name: Optional[str] = None) -> List[Policy]:
        """List access policies for the organization."""
        params: dict[str, Any] = {}
        if name is not None:
            params["name"] = name
        resp = await self._http.get("/access/policies", params=params)
        body = resp.json()
        return [Policy.model_validate(p) for p in body.get("data", [])]

    async def update(
        self,
        policy_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
        row_filters: Optional[List[Dict[str, Any]]] = None,
    ) -> PolicyUpdateResponse:
        """Update an access policy."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if source_ids is not None:
            body["source_ids"] = source_ids
        if row_filters is not None:
            body["row_filters"] = row_filters
        resp = await self._http.patch(f"/access/policies/{policy_id}", json=body)
        return PolicyUpdateResponse.model_validate(resp.json())

    async def delete(self, policy_id: str) -> PolicyDeleteResponse:
        """Delete an access policy and all its user assignments."""
        resp = await self._http.delete(f"/access/policies/{policy_id}")
        return PolicyDeleteResponse.model_validate(resp.json())

    async def assign_users(
        self,
        policy_id: str,
        *,
        user_ids: List[str],
    ) -> PolicyAssignResponse:
        """Assign users to a policy."""
        resp = await self._http.post(
            f"/access/policies/{policy_id}/users",
            json={"user_ids": user_ids},
        )
        return PolicyAssignResponse.model_validate(resp.json())

    async def remove_user(
        self,
        policy_id: str,
        user_id: str,
    ) -> PolicyRemoveUserResponse:
        """Remove a user from a policy."""
        resp = await self._http.delete(
            f"/access/policies/{policy_id}/users/{user_id}"
        )
        return PolicyRemoveUserResponse.model_validate(resp.json())

    async def resolve(
        self,
        *,
        user_id: str,
        source_id: str,
    ) -> ResolvedAccess:
        """Preview resolved access for a user+source combination."""
        resp = await self._http.post(
            "/access/resolve",
            json={"user_id": user_id, "source_id": source_id},
        )
        return ResolvedAccess.model_validate(resp.json())

    async def columns(
        self,
        *,
        source_id: Optional[str] = None,
    ) -> List[SourceColumns]:
        """Discover filterable columns for RLS rule building."""
        params: dict[str, Any] = {}
        if source_id is not None:
            params["source_id"] = source_id
        resp = await self._http.get("/access/columns", params=params)
        body = resp.json()
        return [SourceColumns.model_validate(s) for s in body.get("data", [])]

    async def setup(
        self,
        *,
        name: str,
        sources: Optional[List[str]] = None,
        row_filters: Optional[Dict[str, Any]] = None,
        users: Optional[List[str]] = None,
        description: Optional[str] = None,
    ) -> Policy:
        """Create a policy and assign users in one call."""
        return await async_setup_policy(
            self._http, name=name, sources=sources,
            row_filters=row_filters, users=users,
        )
