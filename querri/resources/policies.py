"""Access policy resources — maps to /access endpoints."""

from __future__ import annotations

import builtins
from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._convenience import async_setup_policy, sync_setup_policy
from .._pagination import AsyncCursorPage, SyncCursorPage
from ..types.policy import (
    Policy,
    PolicyAssignResponse,
    PolicyDeleteResponse,
    PolicyRemoveUserResponse,
    PolicyReplaceResponse,
    PolicyUpdateResponse,
    ResolvedAccess,
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
        description: str | None = None,
        source_ids: builtins.list[str] | None = None,
        row_filters: builtins.list[dict[str, Any]] | None = None,
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

    def list(
        self,
        *,
        name: str | None = None,
        limit: int = 25,
        after: str | None = None,
    ) -> SyncCursorPage[Policy]:
        """List access policies for the organization with cursor pagination.

        Args:
            name: Filter by exact policy name.
            limit: Maximum number of policies per page (1-200).
            after: Cursor for the next page.
        """
        params: dict[str, Any] = {"limit": limit}
        if name is not None:
            params["name"] = name
        if after is not None:
            params["after"] = after
        return SyncCursorPage(self._http, "/access/policies", Policy, params=params)

    def update(
        self,
        policy_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        source_ids: builtins.list[str] | None = None,
        row_filters: builtins.list[dict[str, Any]] | None = None,
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
        user_ids: builtins.list[str],
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
        source_id: str | None = None,
    ) -> builtins.list[SourceColumns]:
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


    def replace_user_policies(
        self, user_id: str, *, policy_ids: builtins.list[str]
    ) -> PolicyReplaceResponse:
        """Atomically replace all policy assignments for a user.

        Removes any existing policy assignments and replaces them with the
        provided set. This prevents policy accumulation from repeated
        ``get_session()`` calls.

        Args:
            user_id: The user ID whose policies to replace.
            policy_ids: Complete set of policy IDs to assign. Pass ``[]`` to
                remove all policies.
        """
        resp = self._http.put(
            f"/access/users/{user_id}/policies",
            json={"policy_ids": policy_ids},
        )
        return PolicyReplaceResponse.model_validate(resp.json())

    def setup(
        self,
        *,
        name: str,
        sources: builtins.list[str] | None = None,
        row_filters: dict[str, Any] | None = None,
        users: builtins.list[str] | None = None,
        description: str | None = None,
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
            row_filters=row_filters, users=users, description=description,
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
        description: str | None = None,
        source_ids: builtins.list[str] | None = None,
        row_filters: builtins.list[dict[str, Any]] | None = None,
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
        resp = await self._http.post("/access/policies", json=body)
        return Policy.model_validate(resp.json())

    async def get(self, policy_id: str) -> Policy:
        """Get policy details including assigned user IDs.

        Args:
            policy_id: The policy UUID.
        """
        resp = await self._http.get(f"/access/policies/{policy_id}")
        return Policy.model_validate(resp.json())

    def list(
        self,
        *,
        name: str | None = None,
        limit: int = 25,
        after: str | None = None,
    ) -> AsyncCursorPage[Policy]:
        """List access policies for the organization with cursor pagination.

        Args:
            name: Filter by exact policy name.
            limit: Maximum number of policies per page (1-200).
            after: Cursor for the next page.
        """
        params: dict[str, Any] = {"limit": limit}
        if name is not None:
            params["name"] = name
        if after is not None:
            params["after"] = after
        return AsyncCursorPage(self._http, "/access/policies", Policy, params=params)

    async def update(
        self,
        policy_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        source_ids: builtins.list[str] | None = None,
        row_filters: builtins.list[dict[str, Any]] | None = None,
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
        resp = await self._http.patch(f"/access/policies/{policy_id}", json=body)
        return PolicyUpdateResponse.model_validate(resp.json())

    async def delete(self, policy_id: str) -> PolicyDeleteResponse:
        """Delete an access policy and all its user assignments.

        Args:
            policy_id: The policy UUID.
        """
        resp = await self._http.delete(f"/access/policies/{policy_id}")
        return PolicyDeleteResponse.model_validate(resp.json())

    async def assign_users(
        self,
        policy_id: str,
        *,
        user_ids: builtins.list[str],
    ) -> PolicyAssignResponse:
        """Assign users to a policy.

        Idempotent: already-assigned users are silently skipped.

        Args:
            policy_id: The policy UUID.
            user_ids: List of WorkOS user IDs to assign.
        """
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
        """Remove a user from a policy.

        Args:
            policy_id: The policy UUID.
            user_id: The WorkOS user ID to remove.
        """
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
        """Preview resolved access for a user+source combination.

        Returns the effective row filters and SQL WHERE clause that would
        be applied when querying the given source as the given user.

        Args:
            user_id: WorkOS user ID.
            source_id: Source UUID.
        """
        resp = await self._http.post(
            "/access/resolve",
            json={"user_id": user_id, "source_id": source_id},
        )
        return ResolvedAccess.model_validate(resp.json())

    async def columns(
        self,
        *,
        source_id: str | None = None,
    ) -> builtins.list[SourceColumns]:
        """Discover filterable columns for RLS rule building.

        Returns column names and types from data sources so you can
        construct valid ``row_filters`` for access policies.

        Args:
            source_id: Optional source ID to filter to a single source.
        """
        params: dict[str, Any] = {}
        if source_id is not None:
            params["source_id"] = source_id
        resp = await self._http.get("/access/columns", params=params)
        body = resp.json()
        return [SourceColumns.model_validate(s) for s in body.get("data", [])]

    async def replace_user_policies(
        self, user_id: str, *, policy_ids: builtins.list[str]
    ) -> PolicyReplaceResponse:
        """Atomically replace all policy assignments for a user.

        Removes any existing policy assignments and replaces them with the
        provided set. This prevents policy accumulation from repeated
        ``get_session()`` calls.

        Args:
            user_id: The user ID whose policies to replace.
            policy_ids: Complete set of policy IDs to assign. Pass ``[]`` to
                remove all policies.
        """
        resp = await self._http.put(
            f"/access/users/{user_id}/policies",
            json={"policy_ids": policy_ids},
        )
        return PolicyReplaceResponse.model_validate(resp.json())

    async def setup(
        self,
        *,
        name: str,
        sources: builtins.list[str] | None = None,
        row_filters: dict[str, Any] | None = None,
        users: builtins.list[str] | None = None,
        description: str | None = None,
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
        return await async_setup_policy(
            self._http, name=name, sources=sources,
            row_filters=row_filters, users=users, description=description,
        )
