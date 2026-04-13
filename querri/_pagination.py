"""Auto-paginating iterators for list endpoints.

Supports both cursor-based (after/has_more) and offset-based (page/page_size)
pagination patterns transparently.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from ._base_client import AsyncHTTPClient, SyncHTTPClient

T = TypeVar("T", bound=BaseModel)


class SyncPage(Generic[T]):
    """A single page of results with metadata."""

    def __init__(
        self,
        data: list[T],
        has_more: bool,
        next_cursor: str | None = None,
        total: int | None = None,
    ) -> None:
        self.data = data
        self.has_more = has_more
        self.next_cursor = next_cursor
        self.total = total

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self) -> Iterator[T]:
        return iter(self.data)


class SyncCursorPage(Generic[T]):
    """Auto-paginating cursor-based iterator.

    Usage::

        for user in client.users.list():
            print(user.email)

        # Or get a single page
        page = client.users.list(limit=20)
        users = page.data
    """

    def __init__(
        self,
        http: SyncHTTPClient,
        path: str,
        model: type[T],
        params: dict[str, Any] | None = None,
        data_key: str = "data",
    ) -> None:
        self._http = http
        self._path = path
        self._model = model
        self._params = params or {}
        self._data_key = data_key
        self._first_page: SyncPage[T] | None = None

    def _fetch_page(self, params: dict[str, Any]) -> SyncPage[T]:
        """Fetch one page from the API and parse the response body.

        Handles three response formats:
        1. Paginated envelope: ``{"data": [...], "has_more": bool, "next_cursor": str}``
        2. Offset-based fallback: ``{"data": [...], "page": int, "total_pages": int}``
        3. Plain list: ``[...]`` (internal API returns raw arrays)

        This lets the same iterator work with both the public and internal APIs.
        """
        response = self._http.get(self._path, params=params)
        body = response.json()

        # Internal API may return a plain list instead of a paginated envelope
        if isinstance(body, list):
            items = [self._model.model_validate(item) for item in body]
            return SyncPage(data=items, has_more=False)

        items_raw = body.get(self._data_key, [])
        items = [self._model.model_validate(item) for item in items_raw]

        has_more = body.get("has_more", False)
        next_cursor = body.get("next_cursor")

        # Offset-based fallback
        if next_cursor is None and not has_more:
            page_num = body.get("page")
            total_pages = body.get("total_pages")
            if page_num is not None and total_pages is not None:
                has_more = page_num < total_pages
                if has_more:
                    next_cursor = str(page_num + 1)

        total = body.get("total")

        return SyncPage(
            data=items,
            has_more=has_more,
            next_cursor=next_cursor,
            total=total,
        )

    def _ensure_first_page(self) -> SyncPage[T]:
        """Lazy-fetch and cache the first page.

        Subsequent calls return the cached page.
        """
        if self._first_page is None:
            self._first_page = self._fetch_page(self._params)
        return self._first_page

    @property
    def data(self) -> list[T]:
        """Items from the first page."""
        return self._ensure_first_page().data

    @property
    def has_more(self) -> bool:
        """Whether more pages exist beyond the current one."""
        return self._ensure_first_page().has_more

    @property
    def next_cursor(self) -> str | None:
        """Opaque cursor for fetching the next page, or None."""
        return self._ensure_first_page().next_cursor

    def first(self) -> T | None:
        """Get the first item, or None if empty."""
        data = self.data
        return data[0] if data else None

    def to_list(self) -> list[T]:
        """Consume all pages and return items as a flat list."""
        return list(self)

    def __iter__(self) -> Iterator[T]:
        """Auto-paginate through all results."""
        page = self._ensure_first_page()
        yield from page.data

        while page.has_more and page.next_cursor:
            # "after" is the standard cursor param name across all Querri list endpoints
            params = {**self._params, "after": page.next_cursor}
            page = self._fetch_page(params)
            yield from page.data


class AsyncPage(Generic[T]):
    """A single async page of results."""

    def __init__(
        self,
        data: list[T],
        has_more: bool,
        next_cursor: str | None = None,
        total: int | None = None,
    ) -> None:
        self.data = data
        self.has_more = has_more
        self.next_cursor = next_cursor
        self.total = total


class AsyncCursorPage(Generic[T]):
    """Auto-paginating async cursor-based iterator.

    Usage::

        async for user in client.users.list():
            print(user.email)

        # Or get a single page
        page = client.users.list(limit=20)
        users = await page.get_data()
    """

    def __init__(
        self,
        http: AsyncHTTPClient,
        path: str,
        model: type[T],
        params: dict[str, Any] | None = None,
        data_key: str = "data",
    ) -> None:
        self._http = http
        self._path = path
        self._model = model
        self._params = params or {}
        self._data_key = data_key
        self._first_page: AsyncPage[T] | None = None

    async def _fetch_page(self, params: dict[str, Any]) -> AsyncPage[T]:
        """Fetch one page from the API and parse the response body.

        Handles three response formats:
        1. Paginated envelope: ``{"data": [...], "has_more": bool, "next_cursor": str}``
        2. Offset-based fallback: ``{"data": [...], "page": int, "total_pages": int}``
        3. Plain list: ``[...]`` (internal API returns raw arrays)

        This lets the same iterator work with both the public and internal APIs.
        """
        response = await self._http.get(self._path, params=params)
        body = response.json()

        # Internal API may return a plain list instead of a paginated envelope
        if isinstance(body, list):
            items = [self._model.model_validate(item) for item in body]
            return AsyncPage(data=items, has_more=False)

        items_raw = body.get(self._data_key, [])
        items = [self._model.model_validate(item) for item in items_raw]

        has_more = body.get("has_more", False)
        next_cursor = body.get("next_cursor")

        if next_cursor is None and not has_more:
            page_num = body.get("page")
            total_pages = body.get("total_pages")
            if page_num is not None and total_pages is not None:
                has_more = page_num < total_pages
                if has_more:
                    next_cursor = str(page_num + 1)

        total = body.get("total")

        return AsyncPage(
            data=items,
            has_more=has_more,
            next_cursor=next_cursor,
            total=total,
        )

    async def _ensure_first_page(self) -> AsyncPage[T]:
        """Lazy-fetch and cache the first page.

        Subsequent calls return the cached page.
        """
        if self._first_page is None:
            self._first_page = await self._fetch_page(self._params)
        return self._first_page

    async def get_data(self) -> list[T]:
        """Items from the first page.

        Unlike ``SyncCursorPage.data`` (a property), this must be awaited::

            data = await page.get_data()
        """
        page = await self._ensure_first_page()
        return page.data

    async def first(self) -> T | None:
        page = await self._ensure_first_page()
        return page.data[0] if page.data else None

    async def to_list(self) -> list[T]:
        """Consume all pages and return items as a flat list."""
        return [item async for item in self]

    async def __aiter__(self):  # type: ignore[override]
        page = await self._ensure_first_page()
        for item in page.data:
            yield item

        while page.has_more and page.next_cursor:
            # "after" is the standard cursor param name across all Querri list endpoints
            params = {**self._params, "after": page.next_cursor}
            page = await self._fetch_page(params)
            for item in page.data:
                yield item
