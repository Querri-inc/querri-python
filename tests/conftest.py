"""Shared fixtures for querri SDK tests."""

from __future__ import annotations

import pytest

from querri._config import ClientConfig


@pytest.fixture()
def config() -> ClientConfig:
    """A minimal valid ClientConfig for testing."""
    return ClientConfig(
        api_key="qk_test_key_123",
        org_id="org_test_456",
        base_url="https://test.querri.com/api/v1",
        timeout=10.0,
        max_retries=2,
    )
