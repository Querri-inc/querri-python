"""Exception hierarchy for the Querri SDK.

Maps Stripe-style API error responses to typed Python exceptions.
"""

from __future__ import annotations

import re
from typing import Literal

# ---------------------------------------------------------------------------
# Documented API error codes
# ---------------------------------------------------------------------------
# The codes for authentication, access, Custom Roles and embed sessions. The
# API sends other codes too, so treat ``APIError.code`` as a string (``None``
# when the server sent no code). Compare against the constants rather than
# string literals so a typo fails loudly at import time. The class of the
# exception still follows the HTTP status (``PermissionError`` for 403,
# ``NotFoundError`` for 404, …).

MISSING_API_KEY = "missing_api_key"
INVALID_API_KEY = "invalid_api_key"
MISSING_TENANT_ID = "missing_tenant_id"
INVALID_JWT = "invalid_jwt"
INVALID_EMBED_SESSION = "invalid_embed_session"
IP_NOT_ALLOWED = "ip_not_allowed"
ORG_SCHEDULED_FOR_DELETION = "org_scheduled_for_deletion"
RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
INSUFFICIENT_SCOPE = "insufficient_scope"
PERMISSION_DENIED = "permission_denied"
ROLE_NOT_FOUND = "role_not_found"
ROLE_NOT_ALLOWED = "role_not_allowed"
ROLE_DISABLED = "role_disabled"
SEAT_CHANGE_REQUIRED = "seat_change_required"
NOT_ORG_MEMBER = "not_org_member"
USER_NOT_FOUND = "user_not_found"
ORIGIN_REQUIRED = "origin_required"
ORIGIN_NOT_ALLOWED = "origin_not_allowed"
SESSION_NOT_FOUND = "session_not_found"
ORG_MISMATCH = "org_mismatch"
SESSION_CREATION_FAILED = "session_creation_failed"
REFRESH_FAILED = "refresh_failed"
MEMBERSHIP_CHECK_FAILED = "membership_check_failed"
ESCALATION_DENIED = "escalation_denied"
LAST_ADMIN = "last_admin"
INVALID_PARAMETERS = "invalid_parameters"

ErrorCode = Literal[
    "missing_api_key",
    "invalid_api_key",
    "missing_tenant_id",
    "invalid_jwt",
    "invalid_embed_session",
    "ip_not_allowed",
    "org_scheduled_for_deletion",
    "rate_limit_exceeded",
    "insufficient_scope",
    "permission_denied",
    "role_not_found",
    "role_not_allowed",
    "role_disabled",
    "seat_change_required",
    "not_org_member",
    "user_not_found",
    "origin_required",
    "origin_not_allowed",
    "session_not_found",
    "org_mismatch",
    "session_creation_failed",
    "refresh_failed",
    "membership_check_failed",
    "escalation_denied",
    "last_admin",
    "invalid_parameters",
]
"""The ``APIError.code`` values for authentication, access, Custom Roles and
embed sessions (see docs/server-sdk.md, Error codes). The API sends other codes
too, so treat ``APIError.code`` as a string; this Literal is not exhaustive."""

PermissionDeniedReason = Literal[
    "role_denied",
    "not_in_plan",
    "flag_off",
    "embed_disabled",
    "dependency_unmet",
    "forbidden",
    "scope_exceeds_role",
]
"""Known values of ``APIError.reason`` on a ``permission_denied`` error.

The server may add more, so treat ``reason`` as a string."""


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
        request_id: Unique request identifier for support (from the
            ``X-Request-Id`` response header).
        permission: On ``permission_denied``, the permission key the call
            needed (e.g. ``"dashboards.list.view"``), or ``None`` when no
            single permission applies (e.g. reason ``scope_exceeds_role``).
            Read from the error body, falling back to the
            ``X-Permission-Denied`` header when that holds a permission key.
        reason: On ``permission_denied``, why it was refused — one of
            ``role_denied``, ``not_in_plan``, ``flag_off``,
            ``embed_disabled``, ``dependency_unmet``, ``forbidden``,
            ``scope_exceeds_role``. The server may add more.
        body: The parsed JSON response body (any JSON value), or ``None`` when
            the response had no JSON body or the error was raised without
            one. Holds the fields this class does not lift out, e.g.
            ``body["detail"]["error"]["scopes"]`` on a ``scope_exceeds_role``
            refusal or ``body["detail"]["error"]["missing"]`` on
            ``escalation_denied``.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int,
        type: str | None = None,
        code: str | None = None,
        doc_url: str | None = None,
        request_id: str | None = None,
        permission: str | None = None,
        reason: str | None = None,
        body: object = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.type = type
        self.code = code
        self.doc_url = doc_url
        self.request_id = request_id
        self.permission = permission
        self.reason = reason
        self.body = body

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
    """403 — Insufficient scope or access denied.

    Inspect ``code`` to tell the cases apart: ``permission_denied`` (the
    caller's role lacks ``permission``; see ``reason``),
    ``insufficient_scope``, or an embed role refusal (``role_not_allowed``,
    ``role_disabled``, ``seat_change_required``).
    """


class NotFoundError(APIError):
    """404 — Resource not found (``code`` e.g. ``role_not_found``)."""


class ValidationError(APIError):
    """400 or 422 — Bad request parameters.

    A 422 is FastAPI request validation; its message lists each failing
    field, e.g. ``"Validation failed: body.ttl: Input should be ..."``.
    """


class ConflictError(APIError):
    """409 — Duplicate resource or conflict."""


class OriginRequiredError(ValidationError):
    """400 ``origin_required`` — the organization has an embed-domain allowlist.

    Raised when a session is created without ``origin`` while the org has
    configured allowed embed domains. Pass ``origin`` (the page origin that
    will embed Querri, e.g. ``https://app.customer.com``) to
    ``create_session()`` / ``get_session()``.
    """


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
        retry_after: float | None = None,
        **kwargs: object,
    ) -> None:
        # Extract only the kwargs that APIError accepts
        api_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k
            in (
                "type",
                "code",
                "doc_url",
                "request_id",
                "permission",
                "reason",
                "body",
            )
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


# Maps HTTP status codes to exception subclasses. Codes not listed here
# fall through to the base ``APIError``. Multiple 5xx codes share ``ServerError``.
_STATUS_MAP: dict[int, type[APIError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: PermissionError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
    500: ServerError,
    502: ServerError,
    503: ServerError,
}


#: An error code: lowercase snake_case (no spaces or dots).
_CODE_SHAPE = re.compile(r"[a-z][a-z0-9_]*")


def _format_validation_detail(detail: list[object]) -> str:
    """Render FastAPI's 422 ``detail`` list as one readable line.

    ``[{"loc": ["body", "ttl"], "msg": "Input should be ..."}]`` becomes
    ``"Validation failed: body.ttl: Input should be ..."``; several entries
    are joined with ``"; "``.
    """
    parts: list[str] = []
    for item in detail:
        if isinstance(item, dict):
            loc = item.get("loc")
            msg = str(item.get("msg", "invalid"))
            if isinstance(loc, (list, tuple)) and loc:
                parts.append(f"{'.'.join(str(p) for p in loc)}: {msg}")
            else:
                parts.append(msg)
        else:
            parts.append(str(item))
    return "Validation failed: " + "; ".join(parts) if parts else "Validation failed"


def _optional_str(value: object) -> str | None:
    """Return ``str(value)`` for a non-empty value, else ``None``."""
    return str(value) if value else None


def _header_permission(value: str | None) -> str | None:
    """Return the ``X-Permission-Denied`` header when it holds a permission key.

    The server also sends an error code there (``permission_denied``) when no
    single permission applies. Permission keys always contain a dot
    (``dashboards.list.view``, ``org.admin``); error codes never do.
    """
    return value if value and "." in value else None


def raise_for_status(
    status: int,
    body: object,
    *,
    request_id: str | None = None,
    retry_after: float | None = None,
    permission_denied: str | None = None,
) -> None:
    """Raise the appropriate exception for an error response.

    Understands every error shape the API sends:

    * Stripe-style ``{"error": {"type", "code", "message", "doc_url"}}``.
    * FastAPI's envelope ``{"detail": {"error": {...}}}`` — what every
      ``/api/v1`` error looks like on the wire — and a bare
      ``{"detail": {"type", "code", "message"}}``.
    * The in-app flat shape ``{"detail": {"error": "<code>", "permission",
      "reason", "layer"}}``, whose ``error`` is the code string.
    * ``{"detail": "message"}``.
    * FastAPI request validation, ``422 {"detail": [{"loc", "msg", ...}]}``,
      raised as :class:`ValidationError` with a readable message.

    A ``permission_denied`` error also carries ``permission`` and ``reason``.

    Args:
        status: HTTP status code.
        body: Parsed JSON response body (any JSON value; ``None`` when the
            response had no JSON body). Kept on the exception as ``body``.
        request_id: Request ID from the ``X-Request-Id`` response header.
        retry_after: Retry-After value from response headers.
        permission_denied: The ``X-Permission-Denied`` response header —
            fallback for ``permission`` when the body does not carry it. Used
            only when the error's code is ``permission_denied`` or there is no
            code, and only when the header holds a permission key (contains a
            ``.``); the server puts an error code there when no single
            permission applies.
    """
    err_type = ""
    err_code = ""
    err_doc_url: object = None
    err_permission: object = None
    err_reason: object = None

    raw_body = body
    if not isinstance(body, dict):
        # A JSON array or scalar body carries no error envelope.
        body = {}

    error = body.get("error", {})
    if not (isinstance(error, dict) and error):
        # FastAPI's `HTTPException(detail=...)` produces `{"detail": ...}`.
        # `detail` may be a string, a structured dict (with or without the
        # `error` envelope), or — for request validation — a list.
        detail = body.get("detail")
        error = None
        if isinstance(detail, dict) and detail:
            nested_error = detail.get("error")
            if isinstance(nested_error, dict) and nested_error:
                error = nested_error
            elif isinstance(nested_error, str) and nested_error:
                # In-app flat shape: ``{"detail": {"error": "permission_denied",
                # "permission", "reason", "layer"}}`` — the code is the string,
                # when it is code-shaped (some bodies put a sentence there).
                is_code = _CODE_SHAPE.fullmatch(nested_error) is not None
                error = {
                    **detail,
                    "code": nested_error if is_code else None,
                    "message": detail.get("message") or nested_error,
                }
            elif "code" in detail or "message" in detail:
                error = detail

    if isinstance(error, dict) and error:
        err_type = str(error.get("type") or "")
        err_code = str(error.get("code") or "")
        err_message = str(error.get("message") or f"HTTP {status}")
        err_doc_url = error.get("doc_url")
        err_permission = error.get("permission")
        err_reason = error.get("reason")
    else:
        detail = body.get("detail")
        if isinstance(detail, str) and detail:
            err_message = detail
        elif isinstance(detail, list) and detail:
            err_type = "validation_error"
            err_message = _format_validation_detail(detail)
        elif isinstance(detail, dict) and detail:
            err_message = str(detail)
        else:
            err_message = str(body) if body else f"HTTP {status}"

    exc_class = _STATUS_MAP.get(status, APIError)

    # Error-code refinements: some codes carry a contract worth a dedicated
    # type and a message that says what to do about it.
    if status == 400 and err_code == "origin_required":
        exc_class = OriginRequiredError
        err_message = (
            f"{err_message} This organization has configured an allowlist of "
            "embed domains, so origin is required: pass origin=... (the page "
            "origin that will embed Querri, e.g. 'https://app.customer.com') "
            "to create_session() or get_session()."
        )

    # The header names a permission only on a role denial. Other refusals
    # (``escalation_denied``, …) may still send one, and it is not the
    # permission *their* call needed, so it is not borrowed for them.
    header_permission = (
        _header_permission(permission_denied)
        if err_code in ("", PERMISSION_DENIED)
        else None
    )

    kwargs: dict[str, object] = {
        "status": status,
        "type": err_type or None,
        "code": err_code or None,
        "doc_url": _optional_str(err_doc_url),
        "request_id": request_id,
        "permission": _optional_str(err_permission) or header_permission,
        "reason": _optional_str(err_reason),
        "body": raw_body,
    }

    if exc_class is RateLimitError:
        kwargs["retry_after"] = retry_after

    raise exc_class(err_message, **kwargs)  # type: ignore[arg-type]
