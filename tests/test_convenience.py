"""Tests for convenience helper functions."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from querri._base_client import AsyncHTTPClient, SyncHTTPClient
from querri._config import ClientConfig
from querri._convenience import (
    _build_policy_body,
    _hash_access_spec,
    _resolve_user_param,
    async_get_session,
    sync_get_session,
)

BASE = "https://test.querri.com/api/v1"


def _make_config() -> ClientConfig:
    return ClientConfig(
        api_key="qk_test",
        org_id="org_test",
        base_url=BASE,
        timeout=10.0,
        max_retries=0,
    )


class TestHashAccessSpec:
    """Test _hash_access_spec determinism and correctness."""

    def test_deterministic(self):
        spec = {"sources": ["src_a", "src_b"], "filters": {"region": ["APAC"]}}
        h1 = _hash_access_spec(spec)
        h2 = _hash_access_spec(spec)
        assert h1 == h2

    def test_ignores_key_order(self):
        """Verify that the hash is deterministic regardless of dict key order."""
        spec1 = {"sources": ["src_a"], "filters": {"region": ["APAC"]}}
        spec2 = {"filters": {"region": ["APAC"]}, "sources": ["src_a"]}
        assert _hash_access_spec(spec1) == _hash_access_spec(spec2)

    def test_returns_8_hex_chars(self):
        spec = {"sources": ["src_a"]}
        h = _hash_access_spec(spec)
        assert len(h) == 8
        assert all(c in "0123456789abcdef" for c in h)

    def test_ignores_non_hashable_keys(self):
        """Verify that non-canonical keys like policy_ids are excluded from the hash."""
        spec1 = {"sources": ["src_a"]}
        spec2 = {"sources": ["src_a"], "policy_ids": ["pol_123"]}
        assert _hash_access_spec(spec1) == _hash_access_spec(spec2)

    def test_different_specs_differ(self):
        spec1 = {"sources": ["src_a"]}
        spec2 = {"sources": ["src_b"]}
        assert _hash_access_spec(spec1) != _hash_access_spec(spec2)

    def test_empty_spec(self):
        h = _hash_access_spec({})
        assert len(h) == 8

    def test_filters_only(self):
        spec = {"filters": {"department": "Sales"}}
        h = _hash_access_spec(spec)
        assert len(h) == 8


class TestBuildPolicyBody:
    """Test _build_policy_body mapping."""

    def test_basic_sources(self):
        access = {"sources": ["src_abc", "src_def"]}
        body = _build_policy_body(access, "test_policy")
        assert body["name"] == "test_policy"
        assert body["source_ids"] == ["src_abc", "src_def"]
        assert "row_filters" not in body

    def test_filters_list_values(self):
        access = {"filters": {"region": ["APAC", "EMEA"]}}
        body = _build_policy_body(access, "pol")
        assert body["row_filters"] == [
            {"column": "region", "values": ["APAC", "EMEA"]},
        ]

    def test_filters_single_value_wrapped(self):
        """Verify that a single filter value string is auto-wrapped in a list."""
        access = {"filters": {"department": "Sales"}}
        body = _build_policy_body(access, "pol")
        assert body["row_filters"] == [
            {"column": "department", "values": ["Sales"]},
        ]

    def test_sources_and_filters(self):
        access = {
            "sources": ["src_1"],
            "filters": {"region": ["APAC"], "department": "Sales"},
        }
        body = _build_policy_body(access, "combo")
        assert body["name"] == "combo"
        assert body["source_ids"] == ["src_1"]
        assert len(body["row_filters"]) == 2

    def test_empty_access(self):
        body = _build_policy_body({}, "empty")
        assert body == {"name": "empty"}

    def test_no_sources_key(self):
        body = _build_policy_body({"filters": {}}, "pol")
        # Empty filters dict should not produce row_filters
        assert "row_filters" not in body


class TestResolveUserParam:
    """Test _resolve_user_param with string and dict inputs."""

    def test_string_input(self):
        ext_id, body = _resolve_user_param("customer-42")
        assert ext_id == "customer-42"
        assert body is None

    def test_dict_input_minimal(self):
        ext_id, body = _resolve_user_param(
            {
                "external_id": "cust-42",
                "email": "alice@example.com",
            }
        )
        assert ext_id == "cust-42"
        assert body is not None
        assert body["email"] == "alice@example.com"
        assert body["role"] == "member"

    def test_dict_input_with_optional_fields(self):
        ext_id, body = _resolve_user_param(
            {
                "external_id": "cust-42",
                "email": "alice@example.com",
                "first_name": "Alice",
                "last_name": "Smith",
                "role": "admin",
            }
        )
        assert ext_id == "cust-42"
        assert body["first_name"] == "Alice"
        assert body["last_name"] == "Smith"
        assert body["role"] == "admin"

    def test_dict_missing_external_id_raises(self):
        with pytest.raises(ValueError, match="external_id"):
            _resolve_user_param({"email": "alice@example.com"})

    def test_dict_missing_email_allowed(self):
        """Email is optional — omitting it should not raise."""
        ext_id, body = _resolve_user_param({"external_id": "cust-42"})
        assert ext_id == "cust-42"
        assert body is not None
        assert "email" not in body

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError, match="must be a string"):
            _resolve_user_param(42)  # type: ignore[arg-type]

    def test_dict_default_role_is_member(self):
        """Verify that role defaults to 'member' when not explicitly provided."""
        _, body = _resolve_user_param(
            {
                "external_id": "cust-42",
                "email": "alice@example.com",
            }
        )
        assert body["role"] == "member"

    def test_dict_without_optional_fields(self):
        _, body = _resolve_user_param(
            {
                "external_id": "cust-42",
                "email": "alice@example.com",
            }
        )
        assert "first_name" not in body
        assert "last_name" not in body


# ---------------------------------------------------------------------------
# get_session end to end (respx at the HTTP boundary)
# ---------------------------------------------------------------------------

_USER = {"external_id": "cust-42", "email": "alice@example.com", "role": "member"}


def _mock_get_session_routes(session_json: dict[str, object]) -> respx.Route:
    """Mock the user upsert and the session create; return the session route."""
    respx.put(f"{BASE}/users/external/cust-42").mock(
        return_value=httpx.Response(200, json={"id": "usr_1", "created": False})
    )
    return respx.post(f"{BASE}/embed/sessions").mock(
        return_value=httpx.Response(200, json=session_json)
    )


class TestSyncGetSessionRole:
    """``sync_get_session`` forwards the Custom Role and returns ``role_id``."""

    @respx.mock
    def test_role_sent_and_role_id_returned(self):
        route = _mock_get_session_routes(
            {
                "session_token": "es_1",
                "expires_in": 3600,
                "user_id": "usr_1",
                "role_id": "role_analyst",
            }
        )
        result = sync_get_session(
            SyncHTTPClient(_make_config()), user=_USER, role="analyst", ttl=1800
        )
        body = json.loads(route.calls[0].request.content)
        assert body == {"user_id": "usr_1", "ttl": 1800, "role": "analyst"}
        assert result["role_id"] == "role_analyst"
        assert result["external_id"] == "cust-42"

    @respx.mock
    def test_user_org_role_is_not_the_session_role(self):
        """``user["role"]`` goes to the user upsert, never to the session."""
        route = _mock_get_session_routes(
            {"session_token": "es_1", "expires_in": 3600, "user_id": "usr_1"}
        )
        result = sync_get_session(SyncHTTPClient(_make_config()), user=_USER)
        upsert = json.loads(respx.calls[0].request.content)
        assert upsert["role"] == "member"
        body = json.loads(route.calls[0].request.content)
        assert body == {"user_id": "usr_1", "ttl": 3600}
        assert "role_id" not in result

    @respx.mock
    def test_empty_role_not_sent(self):
        route = _mock_get_session_routes(
            {"session_token": "es_1", "expires_in": 3600, "user_id": "usr_1"}
        )
        sync_get_session(SyncHTTPClient(_make_config()), user=_USER, role="")
        body = json.loads(route.calls[0].request.content)
        assert body == {"user_id": "usr_1", "ttl": 3600}

    @respx.mock
    def test_role_error_surfaces_code(self):
        respx.put(f"{BASE}/users/external/cust-42").mock(
            return_value=httpx.Response(200, json={"id": "usr_1"})
        )
        respx.post(f"{BASE}/embed/sessions").mock(
            return_value=httpx.Response(
                404,
                json={
                    "detail": {
                        "error": {
                            "type": "not_found_error",
                            "code": "role_not_found",
                            "message": "No role with that id or key.",
                            "doc_url": "https://docs.querri.com/api/errors#role_not_found",
                        }
                    }
                },
            )
        )
        from querri._exceptions import ROLE_NOT_FOUND, NotFoundError

        with pytest.raises(NotFoundError) as exc_info:
            sync_get_session(SyncHTTPClient(_make_config()), user=_USER, role="nope")
        assert exc_info.value.code == ROLE_NOT_FOUND
        assert exc_info.value.type == "not_found_error"


class TestAsyncGetSessionRole:
    """``async_get_session`` mirrors the sync behaviour."""

    @respx.mock
    async def test_role_sent_and_role_id_returned(self):
        route = _mock_get_session_routes(
            {
                "session_token": "es_1",
                "expires_in": 3600,
                "user_id": "usr_1",
                "role_id": "role_analyst",
            }
        )
        result = await async_get_session(
            AsyncHTTPClient(_make_config()), user=_USER, role="analyst", ttl=1800
        )
        body = json.loads(route.calls[0].request.content)
        assert body == {"user_id": "usr_1", "ttl": 1800, "role": "analyst"}
        assert result["role_id"] == "role_analyst"
        assert result["external_id"] == "cust-42"

    @respx.mock
    async def test_empty_role_not_sent(self):
        route = _mock_get_session_routes(
            {"session_token": "es_1", "expires_in": 3600, "user_id": "usr_1"}
        )
        await async_get_session(AsyncHTTPClient(_make_config()), user=_USER, role="")
        body = json.loads(route.calls[0].request.content)
        assert body == {"user_id": "usr_1", "ttl": 3600}

    @respx.mock
    async def test_no_role_key_when_unset(self):
        route = _mock_get_session_routes(
            {"session_token": "es_1", "expires_in": 3600, "user_id": "usr_1"}
        )
        result = await async_get_session(AsyncHTTPClient(_make_config()), user=_USER)
        body = json.loads(route.calls[0].request.content)
        assert body == {"user_id": "usr_1", "ttl": 3600}
        assert "role_id" not in result
