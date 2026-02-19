"""Tests for configuration resolution."""

from __future__ import annotations

import os
from unittest.mock import patch

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
        env = {"QUERRI_API_KEY": "qk_env", "QUERRI_ORG_ID": "org_env"}
        with patch.dict(os.environ, env, clear=False):
            cfg = resolve_config(api_key="qk_explicit", org_id="org_explicit")
            assert cfg.api_key == "qk_explicit"
            assert cfg.org_id == "org_explicit"

    def test_missing_api_key_raises(self):
        env = {k: v for k, v in os.environ.items() if k != "QUERRI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError, match="No API key"):
                resolve_config(org_id="org_123")

    def test_missing_org_id_raises(self):
        env = {k: v for k, v in os.environ.items() if k != "QUERRI_ORG_ID"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError, match="No organization ID"):
                resolve_config(api_key="qk_abc")

    def test_defaults(self):
        cfg = resolve_config(api_key="qk_abc", org_id="org_123")
        assert cfg.base_url == DEFAULT_HOST + "/api/v1"
        assert cfg.timeout == DEFAULT_TIMEOUT
        assert cfg.max_retries == DEFAULT_MAX_RETRIES

    def test_custom_host(self):
        cfg = resolve_config(
            api_key="qk_abc", org_id="org_123",
            host="https://custom.example.com",
        )
        assert cfg.base_url == "https://custom.example.com/api/v1"

    def test_host_trailing_slash_stripped(self):
        cfg = resolve_config(
            api_key="qk_abc", org_id="org_123",
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
        assert "0.1.0" in cfg.user_agent
