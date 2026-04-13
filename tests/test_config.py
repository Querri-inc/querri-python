"""Tests for configuration resolution."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from querri._config import (
    DEFAULT_HOST,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    ClientConfig,
    resolve_config,
)
from querri._exceptions import ConfigError


class TestResolveConfig:
    """Test resolve_config() priority: explicit > env > defaults."""

    def test_explicit_args(self):
        cfg = resolve_config(api_key="qk_abc", org_id="org_123")
        assert cfg.api_key == "qk_abc"
        assert cfg.org_id == "org_123"

    def test_env_vars_fallback(self):
        env = {"QUERRI_API_KEY": "qk_env", "QUERRI_ORG_ID": "org_env"}
        with patch.dict(os.environ, env, clear=False):
            cfg = resolve_config()
            assert cfg.api_key == "qk_env"
            assert cfg.org_id == "org_env"

    def test_explicit_overrides_env(self):
        """Verify that explicit args take priority over environment variables."""
        env = {"QUERRI_API_KEY": "qk_env", "QUERRI_ORG_ID": "org_env"}
        with patch.dict(os.environ, env, clear=False):
            cfg = resolve_config(api_key="qk_explicit", org_id="org_explicit")
            assert cfg.api_key == "qk_explicit"
            assert cfg.org_id == "org_explicit"

    def test_missing_credentials_raises(self):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("QUERRI_API_KEY", "QUERRI_ACCESS_TOKEN")
        }
        mock_ts = MagicMock()
        mock_ts.load.return_value.get_active_profile.return_value = None
        with (
            patch.dict(os.environ, env, clear=True),
            patch("querri._auth.TokenStore", mock_ts),
            pytest.raises(ConfigError, match="No credentials found"),
        ):
            resolve_config(org_id="org_123")

    def test_missing_org_id_raises(self):
        env = {k: v for k, v in os.environ.items() if k != "QUERRI_ORG_ID"}
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ConfigError, match="No organization ID"),
        ):
            resolve_config(api_key="qk_abc")

    def test_defaults(self):
        cfg = resolve_config(api_key="qk_abc", org_id="org_123")
        assert cfg.base_url == DEFAULT_HOST + "/api/v1"
        assert cfg.timeout == DEFAULT_TIMEOUT
        assert cfg.max_retries == DEFAULT_MAX_RETRIES

    def test_custom_host(self):
        cfg = resolve_config(
            api_key="qk_abc",
            org_id="org_123",
            host="https://custom.example.com",
        )
        assert cfg.base_url == "https://custom.example.com/api/v1"

    def test_host_trailing_slash_stripped(self):
        """Verify that a trailing slash on the host is
        stripped before appending /api/v1."""
        cfg = resolve_config(
            api_key="qk_abc",
            org_id="org_123",
            host="https://example.com/",
        )
        assert cfg.base_url == "https://example.com/api/v1"

    def test_host_from_env(self):
        env = {
            "QUERRI_API_KEY": "qk_abc",
            "QUERRI_ORG_ID": "org_123",
            "QUERRI_HOST": "https://env.example.com",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = resolve_config()
            assert cfg.base_url == "https://env.example.com/api/v1"

    def test_custom_timeout(self):
        cfg = resolve_config(api_key="qk_abc", org_id="org_123", timeout=60.0)
        assert cfg.timeout == 60.0

    def test_timeout_from_env(self):
        """Verify that QUERRI_TIMEOUT env var is parsed as a float and applied."""
        env = {
            "QUERRI_API_KEY": "qk_abc",
            "QUERRI_ORG_ID": "org_123",
            "QUERRI_TIMEOUT": "45.0",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = resolve_config()
            assert cfg.timeout == 45.0

    def test_custom_max_retries(self):
        cfg = resolve_config(api_key="qk_abc", org_id="org_123", max_retries=5)
        assert cfg.max_retries == 5

    def test_max_retries_from_env(self):
        """Verify that QUERRI_MAX_RETRIES env var is parsed as an int and applied."""
        env = {
            "QUERRI_API_KEY": "qk_abc",
            "QUERRI_ORG_ID": "org_123",
            "QUERRI_MAX_RETRIES": "7",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = resolve_config()
            assert cfg.max_retries == 7


class TestClientConfig:
    """Test ClientConfig dataclass."""

    def test_user_agent(self):
        cfg = ClientConfig(api_key="qk_abc", org_id="org_123")
        assert cfg.user_agent.startswith("querri-python/")
        assert "0.2.0" in cfg.user_agent
