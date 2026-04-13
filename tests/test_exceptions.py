"""Tests for the exception hierarchy and raise_for_status."""

from __future__ import annotations

import pytest

from querri._exceptions import (
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
        body = {"error": {"type": "invalid_request", "code": "bad_param", "message": "bad"}}
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
        """Verify that a missing error body produces a fallback message containing the HTTP status."""
        with pytest.raises(APIError) as exc_info:
            raise_for_status(500, {})
        assert "HTTP 500" in exc_info.value.message

    def test_non_dict_error_field(self):
        """Verify that a non-dict error field (e.g., plain string) is handled without crashing."""
        body = {"error": "string error"}
        with pytest.raises(APIError):
            raise_for_status(500, body)
