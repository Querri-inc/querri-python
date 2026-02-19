"""Chat type models for the Querri SDK."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class Message(BaseModel):
    """A single chat message."""

    id: str
    role: str
    content: Optional[str] = None
    created_at: Optional[str] = None


class Chat(BaseModel):
    """A chat on a project."""

    id: str
    project_id: Optional[str] = None
    name: str = ""
    message_count: Optional[int] = None
    messages: Optional[List[Message]] = None
    """Only present on detail responses."""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChatDeleteResponse(BaseModel):
    """Response from deleting a chat."""

    id: str
    deleted: bool = True


class ChatCancelResponse(BaseModel):
    """Response from cancelling a chat stream."""

    id: str
    message_id: str
    cancelled: bool
    reason: Optional[str] = None
