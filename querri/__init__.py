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
from ._version import __version__

__all__ = [
    "Querri",
    "AsyncQuerri",
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
]
