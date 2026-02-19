"""Exception hierarchy for the Querri SDK.

Maps Stripe-style API error responses to typed Python exceptions.
"""

from __future__ import annotations

from typing import Optional


class QuerriError(Exception):
    """Base exception for all SDK errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class APIError(QuerriError):
    """HTTP error from the Querri API.

    Attributes:
        status: HTTP status code.
        type: Error type from the API response (e.g., "authentication_error").
        code: Error code from the API response (e.g., "invalid_api_key").
        doc_url: Link to documentation about this error.
        request_id: Unique request identifier for support.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int,
        type: Optional[str] = None,
        code: Optional[str] = None,
        doc_url: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.type = type
        self.code = code
        self.doc_url = doc_url
        self.request_id = request_id

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"status={self.status}, "
            f"type={self.type!r}, "
            f"code={self.code!r}, "
            f"message={self.message!r}"
            f")"
        )


class AuthenticationError(APIError):
    """401 — Invalid or expired API key."""


class PermissionError(APIError):
    """403 — Insufficient scope or access denied."""


class NotFoundError(APIError):
    """404 — Resource not found."""


class ValidationError(APIError):
    """400 — Bad request parameters."""


class ConflictError(APIError):
    """409 — Duplicate resource or conflict."""


class RateLimitError(APIError):
    """429 — Rate limited.

    Attributes:
        retry_after: Seconds to wait before retrying (from Retry-After header).
    """

    def __init__(
        self,
        message: str,
        *,
        status: int = 429,
        retry_after: Optional[float] = None,
        **kwargs: object,
    ) -> None:
        # Extract only the kwargs that APIError accepts
        api_kwargs = {
            k: v for k, v in kwargs.items()
            if k in ("type", "code", "doc_url", "request_id")
        }
        super().__init__(message, status=status, **api_kwargs)  # type: ignore[arg-type]
        self.retry_after = retry_after


class ServerError(APIError):
    """500+ — Internal server error."""


class StreamError(QuerriError):
    """SSE stream issues."""


class StreamTimeoutError(StreamError):
    """Stream didn't produce data within the expected time."""


class StreamCancelledError(StreamError):
    """Stream was cancelled."""


class ConfigError(QuerriError):
    """Missing API key, invalid configuration, etc."""


# Map HTTP status codes to exception classes
_STATUS_MAP: dict[int, type[APIError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: PermissionError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitError,
    500: ServerError,
    502: ServerError,
    503: ServerError,
}


def raise_for_status(
    status: int,
    body: dict[str, object],
    *,
    request_id: Optional[str] = None,
    retry_after: Optional[float] = None,
) -> None:
    """Raise the appropriate exception for an error response.

    Args:
        status: HTTP status code.
        body: Parsed JSON response body (expects Stripe-style {"error": {...}}).
        request_id: Request ID from response headers.
        retry_after: Retry-After value from response headers.
    """
    error = body.get("error", {})
    if isinstance(error, dict):
        err_type = str(error.get("type", ""))
        err_code = str(error.get("code", ""))
        err_message = str(error.get("message", f"HTTP {status}"))
        err_doc_url = error.get("doc_url")
    else:
        err_type = ""
        err_code = ""
        err_message = str(body) if body else f"HTTP {status}"
        err_doc_url = None

    exc_class = _STATUS_MAP.get(status, APIError)

    kwargs: dict[str, object] = {
        "status": status,
        "type": err_type or None,
        "code": err_code or None,
        "doc_url": str(err_doc_url) if err_doc_url else None,
        "request_id": request_id,
    }

    if exc_class is RateLimitError:
        kwargs["retry_after"] = retry_after

    raise exc_class(err_message, **kwargs)  # type: ignore[arg-type]
