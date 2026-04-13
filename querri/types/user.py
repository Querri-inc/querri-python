"""User type models for the Querri SDK."""

from __future__ import annotations

from pydantic import BaseModel


class User(BaseModel):
    """A user in the Querri organization."""

    id: str  #: Unique user identifier.
    email: str  #: User's email address.
    first_name: str | None = None  #: User's first name.
    last_name: str | None = None  #: User's last name.
    role: str = "member"  #: Role, e.g. ``"admin"`` or ``"member"``.
    external_id: str | None = None  #: Caller-supplied external identifier.
    created_at: str | None = None  #: ISO-8601 timestamp of creation.
    created: bool | None = None  #: Only on get_or_create; ``True`` if newly created.


class UserDeleteResponse(BaseModel):
    """Response from deleting a user."""

    id: str  #: ID of the deleted user.
    deleted: bool = True  #: Whether the user was successfully deleted.


class ExternalIdDeleteResponse(BaseModel):
    """Response from removing an external ID mapping."""

    external_id: str  #: The external ID that was removed.
    user_id: str  #: The user ID that was unlinked.
    deleted: bool  #: Whether the mapping was deleted.
