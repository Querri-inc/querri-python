"""Chat type models for the Querri SDK."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class Message(BaseModel):
    """A single chat message."""

    id: str  #: Unique message identifier.
    role: str  #: Sender role, e.g. ``"user"`` or ``"assistant"``.
    content: Optional[str] = None  #: Message text content.
    created_at: Optional[str] = None  #: ISO-8601 timestamp of the message.


class Chat(BaseModel):
    """A chat on a project."""

    id: str  #: Unique chat identifier.
    project_id: Optional[str] = None  #: Parent project ID.
    name: str = ""  #: Display name of the chat.
    message_count: Optional[int] = None  #: Total messages in the chat.
    messages: Optional[List[Message]] = None  #: Only on detail responses.
    created_at: Optional[str] = None  #: ISO-8601 creation timestamp.
    updated_at: Optional[str] = None  #: ISO-8601 last-update timestamp.


class ChatDeleteResponse(BaseModel):
    """Response from deleting a chat."""

    id: str  #: ID of the deleted chat.
    deleted: bool = True  #: Whether the chat was successfully deleted.


class ChatCancelResponse(BaseModel):
    """Response from cancelling a chat stream."""

    id: str  #: Chat identifier.
    message_id: str  #: ID of the cancelled message.
    cancelled: bool  #: Whether the cancellation succeeded.
    reason: Optional[str] = None  #: Reason for cancellation, if provided.
