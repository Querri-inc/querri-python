"""User type models for the Querri SDK."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class User(BaseModel):
    """A user in the Querri organization."""

    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "member"
    external_id: Optional[str] = None
    created_at: Optional[str] = None
    created: Optional[bool] = None
    """Only present on get_or_create responses. True if a new user was created."""


class UserDeleteResponse(BaseModel):
    """Response from deleting a user."""

    id: str
    deleted: bool = True
