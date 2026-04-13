"""Querri Python SDK — API client for the Querri data analysis platform."""

from ._client import AsyncQuerri, Querri
from ._exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    ConflictError,
    NotFoundError,
    PermissionError,
    QuerriError,
    RateLimitError,
    ServerError,
    StreamCancelledError,
    StreamError,
    StreamTimeoutError,
    ValidationError,
)
from ._pagination import AsyncCursorPage, SyncCursorPage
from ._streaming import AsyncChatStream, ChatStream, ChatStreamEvent
from ._user_client import AsyncUserQuerri, UserQuerri
from ._version import __version__

__all__ = [
    "Querri",
    "AsyncQuerri",
    "UserQuerri",
    "AsyncUserQuerri",
    "__version__",
    # Exceptions
    "QuerriError",
    "APIError",
    "AuthenticationError",
    "PermissionError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    "RateLimitError",
    "ServerError",
    "StreamError",
    "StreamTimeoutError",
    "StreamCancelledError",
    "ConfigError",
    # Streaming
    "ChatStream",
    "AsyncChatStream",
    "ChatStreamEvent",
    # Pagination
    "SyncCursorPage",
    "AsyncCursorPage",
]
