"""Tests for convenience helper functions."""

from __future__ import annotations

import pytest

from querri._convenience import (
    _build_policy_body,
    _hash_access_spec,
    _resolve_user_param,
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
