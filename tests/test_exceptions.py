"""Tests for the exception hierarchy and raise_for_status."""

from __future__ import annotations

import httpx
import pytest
import respx

from querri._exceptions import (
    MISSING_API_KEY,
    PERMISSION_DENIED,
    RATE_LIMIT_EXCEEDED,
    ROLE_NOT_ALLOWED,
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
    raise_for_status,
)


class TestExceptionHierarchy:
    """Verify the exception class hierarchy."""

    def test_querri_error_is_base(self):
        assert issubclass(APIError, QuerriError)
        assert issubclass(ConfigError, QuerriError)
        assert issubclass(StreamError, QuerriError)

    def test_api_error_subclasses(self):
        for cls in (
            AuthenticationError,
            PermissionError,
            NotFoundError,
            ValidationError,
            ConflictError,
            RateLimitError,
            ServerError,
        ):
            assert issubclass(cls, APIError), f"{cls.__name__} should subclass APIError"

    def test_stream_error_subclasses(self):
        assert issubclass(StreamTimeoutError, StreamError)
        assert issubclass(StreamCancelledError, StreamError)

    def test_api_error_attributes(self):
        err = APIError(
            "test msg",
            status=400,
            type="invalid_request",
            code="missing_field",
            doc_url="https://docs.querri.com/errors/400",
            request_id="req_abc",
        )
        assert err.status == 400
        assert err.type == "invalid_request"
        assert err.code == "missing_field"
        assert err.doc_url == "https://docs.querri.com/errors/400"
        assert err.request_id == "req_abc"
        assert err.message == "test msg"

    def test_api_error_repr(self):
        err = APIError("msg", status=500, type="server_error", code="internal")
        r = repr(err)
        assert "APIError" in r
        assert "status=500" in r
        assert "server_error" in r

    def test_rate_limit_error_retry_after(self):
        err = RateLimitError("slow down", retry_after=30.0)
        assert err.status == 429
        assert err.retry_after == 30.0

    def test_config_error(self):
        err = ConfigError("no api key")
        assert isinstance(err, QuerriError)
        assert err.message == "no api key"


class TestRaiseForStatus:
    """Test the raise_for_status() mapping function."""

    def test_400_raises_validation_error(self):
        body = {
            "error": {"type": "invalid_request", "code": "bad_param", "message": "bad"}
        }
        with pytest.raises(ValidationError) as exc_info:
            raise_for_status(400, body)
        assert exc_info.value.status == 400
        assert exc_info.value.type == "invalid_request"

    def test_401_raises_authentication_error(self):
        body = {"error": {"message": "invalid key"}}
        with pytest.raises(AuthenticationError) as exc_info:
            raise_for_status(401, body)
        assert exc_info.value.status == 401

    def test_403_raises_permission_error(self):
        body = {"error": {"message": "forbidden"}}
        with pytest.raises(PermissionError) as exc_info:
            raise_for_status(403, body)
        assert exc_info.value.status == 403

    def test_404_raises_not_found_error(self):
        body = {"error": {"message": "not found"}}
        with pytest.raises(NotFoundError) as exc_info:
            raise_for_status(404, body)
        assert exc_info.value.status == 404

    def test_409_raises_conflict_error(self):
        body = {"error": {"message": "duplicate"}}
        with pytest.raises(ConflictError):
            raise_for_status(409, body)

    def test_429_raises_rate_limit_error(self):
        body = {"error": {"message": "rate limited"}}
        with pytest.raises(RateLimitError) as exc_info:
            raise_for_status(429, body, retry_after=60.0)
        assert exc_info.value.retry_after == 60.0

    def test_500_raises_server_error(self):
        body = {"error": {"message": "internal error"}}
        with pytest.raises(ServerError):
            raise_for_status(500, body)

    def test_502_raises_server_error(self):
        with pytest.raises(ServerError):
            raise_for_status(502, {})

    def test_503_raises_server_error(self):
        with pytest.raises(ServerError):
            raise_for_status(503, {})

    def test_unknown_status_raises_api_error(self):
        """Verify that unmapped status codes fall back to the generic APIError class."""
        with pytest.raises(APIError) as exc_info:
            raise_for_status(418, {"error": {"message": "teapot"}})
        assert exc_info.value.status == 418

    def test_request_id_passed_through(self):
        """Verify that the request_id kwarg is propagated to the raised exception."""
        body = {"error": {"message": "fail"}}
        with pytest.raises(APIError) as exc_info:
            raise_for_status(500, body, request_id="req_xyz")
        assert exc_info.value.request_id == "req_xyz"

    def test_empty_body_uses_fallback_message(self):
        """Verify that a missing error body produces a
        fallback message containing the HTTP status."""
        with pytest.raises(APIError) as exc_info:
            raise_for_status(500, {})
        assert "HTTP 500" in exc_info.value.message

    def test_non_dict_error_field(self):
        """Verify that a non-dict error field (e.g.,
        plain string) is handled without crashing."""
        body = {"error": "string error"}
        with pytest.raises(APIError):
            raise_for_status(500, body)

    def test_fastapi_detail_string_surfaces_to_message(self):
        # FastAPI's `raise HTTPException(detail="...")` produces
        # {"detail": "..."} with no `error` envelope. Before this fix the
        # CLI showed "HTTP 403" instead of the helpful server-side message.
        body = {"detail": "seed-fixture is disabled in this environment. "
                          "Set LIBRARY_SEED_FIXTURE_ENABLED=true."}
        with pytest.raises(APIError) as exc_info:
            raise_for_status(403, body)
        assert "LIBRARY_SEED_FIXTURE_ENABLED" in exc_info.value.message
        assert "HTTP 403" not in exc_info.value.message

    def test_fastapi_detail_nested_error_envelope_extracted(self):
        # Some routes raise HTTPException with a structured detail that
        # itself wraps the Stripe-shape error (e.g., the auth module's
        # 401/403 responses). Verify the nested envelope is unwrapped.
        body = {"detail": {"error": {
            "type": "permission_error",
            "code": "insufficient_scope",
            "message": "missing admin:library:write",
        }}}
        with pytest.raises(APIError) as exc_info:
            raise_for_status(403, body)
        assert exc_info.value.message == "missing admin:library:write"
        assert exc_info.value.code == "insufficient_scope"

    def test_empty_error_dict_falls_through_to_detail(self):
        # body = {"error": {}, "detail": "..."} — the early-return path
        # used to take {"error": {}} as truthy and miss the detail. With
        # the `and error` truthiness check we fall through correctly.
        body = {"error": {}, "detail": "real message here"}
        with pytest.raises(APIError) as exc_info:
            raise_for_status(500, body)
        assert exc_info.value.message == "real message here"


# ---------------------------------------------------------------------------
# Real /v1 envelopes, through the HTTP clients (respx at the boundary)
# ---------------------------------------------------------------------------

_HOST = "https://test.querri.com"
_BASE = f"{_HOST}/api/v1"

# Verbatim bodies captured from the live server (2026-10-21).
_LIVE_401_BODY = {
    "detail": {
        "error": {
            "type": "authentication_error",
            "code": "missing_api_key",
            "message": (
                "Authorization required. Provide a Bearer qk_ API key or a "
                "valid JWT token."
            ),
            "doc_url": "https://docs.querri.com/api/errors#missing_api_key",
        }
    }
}
_LIVE_403_PERMISSION_DENIED_BODY = {
    "detail": {
        "error": {
            "type": "permission_error",
            "code": "permission_denied",
            "message": "This action needs the dashboards.list.view permission.",
            "permission": "dashboards.list.view",
            "reason": "role_denied",
            "doc_url": "https://docs.querri.com/api/errors#permission_denied",
        }
    }
}
_LIVE_422_BODY = {
    "detail": [
        {
            "type": "greater_than_equal",
            "loc": ["body", "ttl"],
            "msg": "Input should be greater than or equal to 900",
            "input": 1,
        }
    ]
}


def _http_config():
    from querri._config import ClientConfig

    return ClientConfig(
        api_key="qk_test",
        org_id="org_test",
        base_url=_BASE,
        timeout=10.0,
        max_retries=0,
    )


class TestLiveEnvelopes:
    """Every /v1 error is ``{"detail": {"error": {...}}}`` on the wire."""

    @respx.mock
    def test_verbatim_live_401(self):
        from querri._base_client import SyncHTTPClient

        respx.get(f"{_BASE}/dashboards").mock(
            return_value=httpx.Response(
                401,
                json=_LIVE_401_BODY,
                headers={"x-request-id": "req_bcd3adccd74d40429159b73182bd6962"},
            )
        )
        with pytest.raises(AuthenticationError) as exc_info:
            SyncHTTPClient(_http_config()).get("/dashboards")
        err = exc_info.value
        assert err.status == 401
        assert err.type == "authentication_error"
        assert err.code == MISSING_API_KEY
        assert err.message == (
            "Authorization required. Provide a Bearer qk_ API key or a valid "
            "JWT token."
        )
        assert err.doc_url == "https://docs.querri.com/api/errors#missing_api_key"
        assert err.request_id == "req_bcd3adccd74d40429159b73182bd6962"
        assert err.permission is None
        assert err.reason is None

    @respx.mock
    def test_permission_denied_body_and_header(self):
        from querri._base_client import SyncHTTPClient

        respx.get(f"{_BASE}/dashboards").mock(
            return_value=httpx.Response(
                403,
                json=_LIVE_403_PERMISSION_DENIED_BODY,
                headers={"x-permission-denied": "dashboards.list.view"},
            )
        )
        with pytest.raises(PermissionError) as exc_info:
            SyncHTTPClient(_http_config()).get("/dashboards")
        err = exc_info.value
        assert err.code == PERMISSION_DENIED
        assert err.type == "permission_error"
        assert err.permission == "dashboards.list.view"
        assert err.reason == "role_denied"
        assert err.message == "This action needs the dashboards.list.view permission."

    @respx.mock
    async def test_async_permission_from_header_when_body_lacks_it(self):
        """``permission`` falls back to the X-Permission-Denied header."""
        from querri._base_client import AsyncHTTPClient

        body = {
            "detail": {
                "error": {
                    "type": "permission_error",
                    "code": "permission_denied",
                    "message": "Denied.",
                }
            }
        }
        respx.get(f"{_BASE}/dashboards").mock(
            return_value=httpx.Response(
                403,
                json=body,
                headers={"x-permission-denied": "dashboards.list.view"},
            )
        )
        with pytest.raises(PermissionError) as exc_info:
            await AsyncHTTPClient(_http_config()).get("/dashboards")
        assert exc_info.value.permission == "dashboards.list.view"
        assert exc_info.value.reason is None

    @respx.mock
    def test_sync_permission_from_header_on_non_json_body(self):
        from querri._base_client import SyncHTTPClient

        respx.get(f"{_BASE}/dashboards").mock(
            return_value=httpx.Response(
                403,
                content=b"Forbidden",
                headers={"x-permission-denied": "dashboards.list.view"},
            )
        )
        with pytest.raises(PermissionError) as exc_info:
            SyncHTTPClient(_http_config()).get("/dashboards")
        assert exc_info.value.permission == "dashboards.list.view"
        assert exc_info.value.message == "HTTP 403"

    @respx.mock
    async def test_async_live_422_validation(self):
        from querri._base_client import AsyncHTTPClient

        respx.post(f"{_BASE}/embed/sessions").mock(
            return_value=httpx.Response(422, json=_LIVE_422_BODY)
        )
        with pytest.raises(ValidationError) as exc_info:
            await AsyncHTTPClient(_http_config()).post(
                "/embed/sessions", json={"user_id": "u", "ttl": 1}
            )
        err = exc_info.value
        assert err.status == 422
        assert err.message == (
            "Validation failed: body.ttl: Input should be greater than or equal to 900"
        )


_SCOPE_EXCEEDS_ROLE_BODY = {
    "detail": {
        "error": {
            "code": "permission_denied",
            "reason": "scope_exceeds_role",
            "scopes": ["*"],
        }
    }
}

_STREAM_403_BODY = {
    "detail": {
        "error": {
            "type": "permission_error",
            "code": "permission_denied",
            "message": "This action needs the projects.chat.use permission.",
            "permission": "projects.chat.use",
            "reason": "role_denied",
        }
    }
}


class TestPermissionHeaderFallback:
    """The ``X-Permission-Denied`` header is a permission only when it has a dot."""

    @respx.mock
    def test_error_code_in_header_is_not_a_permission(self):
        from querri._base_client import SyncHTTPClient

        respx.post(f"{_BASE}/keys").mock(
            return_value=httpx.Response(
                403,
                json=_SCOPE_EXCEEDS_ROLE_BODY,
                headers={"x-permission-denied": "permission_denied"},
            )
        )
        with pytest.raises(PermissionError) as exc_info:
            SyncHTTPClient(_http_config()).post("/keys", json={"scopes": ["*"]})
        err = exc_info.value
        assert err.code == PERMISSION_DENIED
        assert err.reason == "scope_exceeds_role"
        assert err.permission is None

    def test_org_admin_header_is_a_permission(self):
        with pytest.raises(PermissionError) as exc_info:
            raise_for_status(403, {}, permission_denied="org.admin")
        assert exc_info.value.permission == "org.admin"


class TestInAppFlatShape:
    """``{"detail": {"error": "<code>", ...}}`` — the in-app 403 body."""

    def test_string_error_is_the_code(self):
        body = {
            "detail": {
                "error": "permission_denied",
                "permission": "dashboards.list.view",
                "reason": "role_denied",
                "layer": "role",
            }
        }
        with pytest.raises(PermissionError) as exc_info:
            raise_for_status(403, body)
        err = exc_info.value
        assert err.code == PERMISSION_DENIED
        assert err.permission == "dashboards.list.view"
        assert err.reason == "role_denied"
        assert err.message == "permission_denied"

    def test_message_used_when_present(self):
        body = {
            "detail": {
                "error": "permission_denied",
                "message": "Your role cannot do that.",
                "permission": "projects.create",
                "reason": "not_in_plan",
            }
        }
        with pytest.raises(PermissionError) as exc_info:
            raise_for_status(403, body)
        assert exc_info.value.message == "Your role cannot do that."
        assert exc_info.value.code == PERMISSION_DENIED
        assert exc_info.value.reason == "not_in_plan"


class TestStreamingErrorBody:
    """A ``send(stream=True)`` error must still surface the body's details."""

    @respx.mock
    def test_sync_streaming_403_keeps_code_permission_reason(self):
        from querri._base_client import SyncHTTPClient

        respx.post(f"{_BASE}/projects/p1/chats/c1/stream").mock(
            return_value=httpx.Response(403, json=_STREAM_403_BODY)
        )
        with pytest.raises(PermissionError) as exc_info:
            SyncHTTPClient(_http_config()).post(
                "/projects/p1/chats/c1/stream", json={"prompt": "hi"}, stream=True
            )
        err = exc_info.value
        assert err.code == PERMISSION_DENIED
        assert err.permission == "projects.chat.use"
        assert err.reason == "role_denied"
        assert err.message == "This action needs the projects.chat.use permission."

    @respx.mock
    async def test_async_streaming_403_keeps_code_permission_reason(self):
        from querri._base_client import AsyncHTTPClient

        respx.post(f"{_BASE}/projects/p1/chats/c1/stream").mock(
            return_value=httpx.Response(403, json=_STREAM_403_BODY)
        )
        with pytest.raises(PermissionError) as exc_info:
            await AsyncHTTPClient(_http_config()).post(
                "/projects/p1/chats/c1/stream", json={"prompt": "hi"}, stream=True
            )
        err = exc_info.value
        assert err.code == PERMISSION_DENIED
        assert err.permission == "projects.chat.use"
        assert err.reason == "role_denied"
        assert err.message == "This action needs the projects.chat.use permission."

    @respx.mock
    def test_sync_chat_stream_resource_surfaces_permission(self):
        """End to end through ``client.projects.chats.stream()``."""
        from querri import Querri

        respx.post(f"{_BASE}/projects/p1/chats/c1/stream").mock(
            return_value=httpx.Response(403, json=_STREAM_403_BODY)
        )
        client = Querri(api_key="qk_test", org_id="org_test", host=_HOST)
        with pytest.raises(PermissionError) as exc_info:
            client.projects.chats.stream("p1", "c1", prompt="hi", user_id="u1")
        assert exc_info.value.permission == "projects.chat.use"
        assert exc_info.value.reason == "role_denied"


class TestPermissionFields:
    """``permission`` / ``reason`` parsing in ``raise_for_status``."""

    def test_stripe_style_body_carries_permission_and_reason(self):
        body = {
            "error": {
                "type": "permission_error",
                "code": "permission_denied",
                "message": "nope",
                "permission": "projects.create",
                "reason": "not_in_plan",
            }
        }
        with pytest.raises(PermissionError) as exc_info:
            raise_for_status(403, body)
        assert exc_info.value.permission == "projects.create"
        assert exc_info.value.reason == "not_in_plan"

    def test_body_permission_wins_over_header(self):
        with pytest.raises(PermissionError) as exc_info:
            raise_for_status(
                403,
                _LIVE_403_PERMISSION_DENIED_BODY,
                permission_denied="something.else",
            )
        assert exc_info.value.permission == "dashboards.list.view"

    def test_bare_detail_dict_without_error_envelope(self):
        body = {"detail": {"type": "permission_error", "code": "role_not_allowed",
                           "message": "That role cannot be granted."}}
        with pytest.raises(PermissionError) as exc_info:
            raise_for_status(403, body)
        assert exc_info.value.code == ROLE_NOT_ALLOWED
        assert exc_info.value.message == "That role cannot be granted."

    def test_rate_limit_error_keeps_permission_and_reason(self):
        body = {
            "detail": {
                "error": {
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded",
                    "message": "slow down",
                    "permission": "p.k",
                    "reason": "forbidden",
                }
            }
        }
        with pytest.raises(RateLimitError) as exc_info:
            raise_for_status(429, body, retry_after=7.0)
        err = exc_info.value
        assert err.retry_after == 7.0
        assert err.code == RATE_LIMIT_EXCEEDED
        assert err.permission == "p.k"
        assert err.reason == "forbidden"

    def test_rate_limit_error_constructor_accepts_new_kwargs(self):
        err = RateLimitError("x", permission="a.b", reason="flag_off")
        assert err.permission == "a.b"
        assert err.reason == "flag_off"


class TestValidationDetail:
    """FastAPI 422 ``detail`` lists become readable ValidationErrors."""

    def test_422_maps_to_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            raise_for_status(422, _LIVE_422_BODY)
        assert exc_info.value.message == (
            "Validation failed: body.ttl: Input should be greater than or equal to 900"
        )
        assert exc_info.value.type == "validation_error"

    def test_multiple_entries_joined(self):
        body = {
            "detail": [
                {"loc": ["body", "ttl"], "msg": "too small", "type": "x"},
                {"loc": ["body", "role"], "msg": "too long", "type": "y"},
            ]
        }
        with pytest.raises(ValidationError) as exc_info:
            raise_for_status(422, body)
        assert exc_info.value.message == (
            "Validation failed: body.ttl: too small; body.role: too long"
        )

    def test_non_dict_body_does_not_crash(self):
        with pytest.raises(ServerError) as exc_info:
            raise_for_status(500, ["unexpected"])  # type: ignore[arg-type]
        assert exc_info.value.message == "HTTP 500"


class TestErrorCodeConstants:
    """The exported constants and the ``ErrorCode`` Literal agree."""

    def test_constants_match_literal(self):
        import typing

        import querri
        from querri import _exceptions

        literal_values = set(typing.get_args(_exceptions.ErrorCode))
        assert len(literal_values) == 23
        for value in literal_values:
            name = value.upper()
            assert getattr(_exceptions, name) == value
            assert getattr(querri, name) == value
            assert name in querri.__all__


def test_a_sentence_in_detail_error_is_a_message_not_a_code():
    body = {"detail": {"error": "Something went wrong here"}}
    with pytest.raises(APIError) as exc_info:
        raise_for_status(403, body)
    assert exc_info.value.code is None
    assert exc_info.value.message == "Something went wrong here"
