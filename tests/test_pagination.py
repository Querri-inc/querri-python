"""Tests for pagination iterators."""

from __future__ import annotations

import json
from typing import Optional

import httpx
import pytest
import respx
from pydantic import BaseModel

from querri._base_client import AsyncHTTPClient, SyncHTTPClient
from querri._config import ClientConfig
from querri._pagination import AsyncCursorPage, SyncCursorPage


class Item(BaseModel):
    id: str
    name: str


def _make_config() -> ClientConfig:
    return ClientConfig(
        api_key="qk_test",
        org_id="org_test",
        base_url="https://test.querri.com/api/v1",
        timeout=10.0,
        max_retries=0,
    )


class TestSyncCursorPage:
    """Test synchronous pagination."""

    @respx.mock
    def test_single_page(self):
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "1", "name": "Alice"},
                        {"id": "2", "name": "Bob"},
                    ],
                    "has_more": False,
                },
            )
        )
        http = SyncHTTPClient(_make_config())
        page = SyncCursorPage(http, "/items", Item)
        items = list(page)
        assert len(items) == 2
        assert items[0].name == "Alice"
        assert items[1].name == "Bob"
        http.close()

    @respx.mock
    def test_multi_page_iteration(self):
        """Verify that the iterator follows next_cursor across multiple pages."""
        respx.get("https://test.querri.com/api/v1/items").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "data": [{"id": "1", "name": "Alice"}],
                        "has_more": True,
                        "next_cursor": "cursor_1",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "data": [{"id": "2", "name": "Bob"}],
                        "has_more": False,
                    },
                ),
            ]
        )
        http = SyncHTTPClient(_make_config())
        page = SyncCursorPage(http, "/items", Item)
        items = list(page)
        assert len(items) == 2
        assert items[0].name == "Alice"
        assert items[1].name == "Bob"
        http.close()

    @respx.mock
    def test_empty_page(self):
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "has_more": False},
            )
        )
        http = SyncHTTPClient(_make_config())
        page = SyncCursorPage(http, "/items", Item)
        items = list(page)
        assert items == []
        http.close()

    @respx.mock
    def test_data_property(self):
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"id": "1", "name": "Alice"}],
                    "has_more": False,
                },
            )
        )
        http = SyncHTTPClient(_make_config())
        page = SyncCursorPage(http, "/items", Item)
        assert len(page.data) == 1
        assert page.data[0].id == "1"
        http.close()

    @respx.mock
    def test_first_method(self):
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}],
                    "has_more": False,
                },
            )
        )
        http = SyncHTTPClient(_make_config())
        page = SyncCursorPage(http, "/items", Item)
        first = page.first()
        assert first is not None
        assert first.name == "Alice"
        http.close()

    @respx.mock
    def test_first_on_empty(self):
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "has_more": False},
            )
        )
        http = SyncHTTPClient(_make_config())
        page = SyncCursorPage(http, "/items", Item)
        assert page.first() is None
        http.close()

    @respx.mock
    def test_has_more_property(self):
        """Verify that accessing has_more triggers a lazy first-page fetch."""
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"id": "1", "name": "Alice"}],
                    "has_more": True,
                    "next_cursor": "c1",
                },
            )
        )
        http = SyncHTTPClient(_make_config())
        page = SyncCursorPage(http, "/items", Item)
        assert page.has_more is True
        http.close()


class TestAsyncCursorPage:
    """Test asynchronous pagination."""

    @respx.mock
    async def test_single_page(self):
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "1", "name": "Alice"},
                        {"id": "2", "name": "Bob"},
                    ],
                    "has_more": False,
                },
            )
        )
        http = AsyncHTTPClient(_make_config())
        page = AsyncCursorPage(http, "/items", Item)
        items = [item async for item in page]
        assert len(items) == 2
        assert items[0].name == "Alice"
        await http.close()

    @respx.mock
    async def test_multi_page(self):
        respx.get("https://test.querri.com/api/v1/items").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "data": [{"id": "1", "name": "A"}],
                        "has_more": True,
                        "next_cursor": "c1",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "data": [{"id": "2", "name": "B"}],
                        "has_more": False,
                    },
                ),
            ]
        )
        http = AsyncHTTPClient(_make_config())
        page = AsyncCursorPage(http, "/items", Item)
        items = [item async for item in page]
        assert len(items) == 2
        await http.close()

    @respx.mock
    async def test_empty_page(self):
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "has_more": False},
            )
        )
        http = AsyncHTTPClient(_make_config())
        page = AsyncCursorPage(http, "/items", Item)
        items = [item async for item in page]
        assert items == []
        await http.close()

    @respx.mock
    async def test_first_method(self):
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"id": "1", "name": "Alice"}],
                    "has_more": False,
                },
            )
        )
        http = AsyncHTTPClient(_make_config())
        page = AsyncCursorPage(http, "/items", Item)
        first = await page.first()
        assert first is not None
        assert first.name == "Alice"
        await http.close()

    @respx.mock
    async def test_first_on_empty(self):
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "has_more": False},
            )
        )
        http = AsyncHTTPClient(_make_config())
        page = AsyncCursorPage(http, "/items", Item)
        assert await page.first() is None
        await http.close()

    @respx.mock
    async def test_get_data_method(self):
        respx.get("https://test.querri.com/api/v1/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"id": "1", "name": "Alice"}],
                    "has_more": False,
                },
            )
        )
        http = AsyncHTTPClient(_make_config())
        page = AsyncCursorPage(http, "/items", Item)
        data = await page.get_data()
        assert len(data) == 1
        assert data[0].id == "1"
        assert data[0].name == "Alice"
        await http.close()
