"""User management resources — maps to /users endpoints."""

from __future__ import annotations

from typing import Any, Optional

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._pagination import AsyncCursorPage, SyncCursorPage
from ..types.user import User, UserDeleteResponse


class Users:
    """Synchronous user management.

    Usage::

        user = client.users.create(email="alice@example.com")
        for u in client.users.list():
            print(u.email)
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def create(
        self,
        *,
        email: str,
        external_id: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: str = "member",
    ) -> User:
        """Create a user in the organization.

        Args:
            email: User email address.
            external_id: Optional customer-provided external ID.
            first_name: Optional first name.
            last_name: Optional last name.
            role: ``"admin"`` or ``"member"`` (default).
        """
        body: dict[str, Any] = {"email": email, "role": role}
        if external_id is not None:
            body["external_id"] = external_id
        if first_name is not None:
            body["first_name"] = first_name
        if last_name is not None:
            body["last_name"] = last_name
        resp = self._http.post("/users", json=body)
        return User.model_validate(resp.json())

    def get(self, user_id: str) -> User:
        """Get user by ID (WorkOS user ID or external ID).

        Args:
            user_id: WorkOS user ID or external ID.
        """
        resp = self._http.get(f"/users/{user_id}")
        return User.model_validate(resp.json())

    def list(
        self,
        *,
        limit: int = 50,
        after: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> SyncCursorPage[User]:
        """List organization users with cursor pagination.

        Args:
            limit: Max users per page (1-100).
            after: Cursor for the next page.
            external_id: Filter by external ID (returns at most one user).
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        if external_id is not None:
            params["external_id"] = external_id
        return SyncCursorPage(self._http, "/users", User, params=params)

    def update(
        self,
        user_id: str,
        *,
        role: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        """Update a user's role or profile fields.

        Args:
            user_id: WorkOS user ID or external ID.
            role: New role (``"admin"`` or ``"member"``).
            first_name: New first name.
            last_name: New last name.
        """
        body: dict[str, Any] = {}
        if role is not None:
            body["role"] = role
        if first_name is not None:
            body["first_name"] = first_name
        if last_name is not None:
            body["last_name"] = last_name
        resp = self._http.patch(f"/users/{user_id}", json=body)
        return User.model_validate(resp.json())

    def delete(self, user_id: str) -> UserDeleteResponse:
        """Remove a user from the organization.

        Args:
            user_id: WorkOS user ID or external ID.
        """
        resp = self._http.delete(f"/users/{user_id}")
        return UserDeleteResponse.model_validate(resp.json())

    def get_or_create(
        self,
        *,
        external_id: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: str = "member",
    ) -> User:
        """Idempotent get-or-create by external ID.

        If a user with this ``external_id`` already exists, returns the
        existing user (``created=False``). Otherwise creates a new user
        (``created=True``). Existing users are never updated.

        Args:
            external_id: Customer-provided external ID.
            email: User email. Required when creating a new user; optional
                when retrieving an existing user.
            first_name: First name (used only on creation).
            last_name: Last name (used only on creation).
            role: Role (used only on creation).
        """
        body: dict[str, Any] = {"role": role}
        if email is not None:
            body["email"] = email
        if first_name is not None:
            body["first_name"] = first_name
        if last_name is not None:
            body["last_name"] = last_name
        resp = self._http.put(f"/users/external/{external_id}", json=body)
        return User.model_validate(resp.json())


class AsyncUsers:
    """Asynchronous user management.

    Usage::

        user = await client.users.create(email="alice@example.com")
        async for u in client.users.list():
            print(u.email)
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create(
        self,
        *,
        email: str,
        external_id: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: str = "member",
    ) -> User:
        """Create a user in the organization."""
        body: dict[str, Any] = {"email": email, "role": role}
        if external_id is not None:
            body["external_id"] = external_id
        if first_name is not None:
            body["first_name"] = first_name
        if last_name is not None:
            body["last_name"] = last_name
        resp = await self._http.post("/users", json=body)
        return User.model_validate(resp.json())

    async def get(self, user_id: str) -> User:
        """Get user by ID (WorkOS user ID or external ID)."""
        resp = await self._http.get(f"/users/{user_id}")
        return User.model_validate(resp.json())

    async def list(
        self,
        *,
        limit: int = 50,
        after: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> AsyncCursorPage[User]:
        """List organization users with cursor pagination."""
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        if external_id is not None:
            params["external_id"] = external_id
        return AsyncCursorPage(self._http, "/users", User, params=params)

    async def update(
        self,
        user_id: str,
        *,
        role: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        """Update a user's role or profile fields."""
        body: dict[str, Any] = {}
        if role is not None:
            body["role"] = role
        if first_name is not None:
            body["first_name"] = first_name
        if last_name is not None:
            body["last_name"] = last_name
        resp = await self._http.patch(f"/users/{user_id}", json=body)
        return User.model_validate(resp.json())

    async def delete(self, user_id: str) -> UserDeleteResponse:
        """Remove a user from the organization."""
        resp = await self._http.delete(f"/users/{user_id}")
        return UserDeleteResponse.model_validate(resp.json())

    async def get_or_create(
        self,
        *,
        external_id: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: str = "member",
    ) -> User:
        """Idempotent get-or-create by external ID.

        Args:
            external_id: Customer-provided external ID.
            email: User email. Required when creating a new user; optional
                when retrieving an existing user.
            first_name: First name (used only on creation).
            last_name: Last name (used only on creation).
            role: Role (used only on creation).
        """
        body: dict[str, Any] = {"role": role}
        if email is not None:
            body["email"] = email
        if first_name is not None:
            body["first_name"] = first_name
        if last_name is not None:
            body["last_name"] = last_name
        resp = await self._http.put(f"/users/external/{external_id}", json=body)
        return User.model_validate(resp.json())
