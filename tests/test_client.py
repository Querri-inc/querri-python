"""Tests for Querri and AsyncQuerri client classes."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from querri import AsyncQuerri, Querri
from querri._config import DEFAULT_HOST
from querri._exceptions import ConfigError


class TestQuerriInit:
    """Test synchronous client initialization."""

    def test_init_with_explicit_args(self):
        client = Querri(api_key="qk_abc", org_id="org_xyz")
        assert client._config.api_key == "qk_abc"
        assert client._config.org_id == "org_xyz"
        client.close()

    def test_init_from_env_vars(self):
        env = {"QUERRI_API_KEY": "qk_env", "QUERRI_ORG_ID": "org_env"}
        with patch.dict(os.environ, env, clear=False):
            client = Querri()
            assert client._config.api_key == "qk_env"
            assert client._config.org_id == "org_env"
            client.close()

    def test_init_explicit_overrides_env(self):
        env = {"QUERRI_API_KEY": "qk_env", "QUERRI_ORG_ID": "org_env"}
        with patch.dict(os.environ, env, clear=False):
            client = Querri(api_key="qk_explicit", org_id="org_explicit")
            assert client._config.api_key == "qk_explicit"
            assert client._config.org_id == "org_explicit"
            client.close()

    def test_init_raises_without_api_key(self):
        env = {k: v for k, v in os.environ.items() if k != "QUERRI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError, match="No API key"):
                Querri(org_id="org_123")

    def test_init_raises_without_org_id(self):
        env = {k: v for k, v in os.environ.items() if k != "QUERRI_ORG_ID"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError, match="No organization ID"):
                Querri(api_key="qk_123")

    def test_custom_host(self):
        client = Querri(
            api_key="qk_abc", org_id="org_xyz",
            host="https://custom.example.com",
        )
        assert client._config.base_url == "https://custom.example.com/api/v1"
        client.close()

    def test_default_host(self):
        client = Querri(api_key="qk_abc", org_id="org_xyz")
        assert client._config.base_url == DEFAULT_HOST + "/api/v1"
        client.close()

    def test_context_manager(self):
        with Querri(api_key="qk_abc", org_id="org_xyz") as client:
            assert client._config.api_key == "qk_abc"


class TestQuerriResources:
    """Test that resource attributes exist and are lazily initialized."""

    RESOURCE_NAMES = [
        "users", "embed", "policies", "projects", "dashboards",
        "data", "files", "sources", "keys", "sharing", "usage", "audit",
    ]

    def test_all_resource_properties_exist(self):
        client = Querri(api_key="qk_abc", org_id="org_xyz")
        for name in self.RESOURCE_NAMES:
            assert hasattr(client, name), f"Missing resource property: {name}"
        client.close()

    def test_resources_are_none_before_access(self):
        client = Querri(api_key="qk_abc", org_id="org_xyz")
        for name in self.RESOURCE_NAMES:
            assert client.__dict__.get(f"_{name}") is None
        client.close()

    def test_resource_is_cached_after_access(self):
        client = Querri(api_key="qk_abc", org_id="org_xyz")
        users1 = client.users
        users2 = client.users
        assert users1 is users2
        client.close()


class TestAsyncQuerriInit:
    """Test async client initialization."""

    def test_init_with_explicit_args(self):
        client = AsyncQuerri(api_key="qk_abc", org_id="org_xyz")
        assert client._config.api_key == "qk_abc"
        assert client._config.org_id == "org_xyz"

    def test_init_from_env_vars(self):
        env = {"QUERRI_API_KEY": "qk_env", "QUERRI_ORG_ID": "org_env"}
        with patch.dict(os.environ, env, clear=False):
            client = AsyncQuerri()
            assert client._config.api_key == "qk_env"
            assert client._config.org_id == "org_env"

    def test_init_raises_without_api_key(self):
        env = {k: v for k, v in os.environ.items() if k != "QUERRI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError, match="No API key"):
                AsyncQuerri(org_id="org_123")

    def test_async_resource_properties_exist(self):
        client = AsyncQuerri(api_key="qk_abc", org_id="org_xyz")
        for name in TestQuerriResources.RESOURCE_NAMES:
            assert hasattr(client, name), f"Missing async resource: {name}"

    async def test_async_context_manager(self):
        async with AsyncQuerri(api_key="qk_abc", org_id="org_xyz") as client:
            assert client._config.api_key == "qk_abc"
