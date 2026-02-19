"""Auto-paginating iterators for list endpoints.

Supports both cursor-based (after/has_more) and offset-based (page/page_size)
pagination patterns transparently.
"""

from __future__ import annotations

from typing import Any, Generic, Iterator, List, Optional, TypeVar

from pydantic import BaseModel

from ._base_client import AsyncHTTPClient, SyncHTTPClient

T = TypeVar("T", bound=BaseModel)


class SyncPage(Generic[T]):
    """A single page of results with metadata."""

    def __init__(
        self,
        data: List[T],
        has_more: bool,
        next_cursor: Optional[str] = None,
        total: Optional[int] = None,
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
        params: Optional[dict[str, Any]] = None,
        data_key: str = "data",
    ) -> None:
        self._http = http
        self._path = path
        self._model = model
        self._params = params or {}
        self._data_key = data_key
        self._first_page: Optional[SyncPage[T]] = None

    def _fetch_page(self, params: dict[str, Any]) -> SyncPage[T]:
        response = self._http.get(self._path, params=params)
        body = response.json()

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
        if self._first_page is None:
            self._first_page = self._fetch_page(self._params)
        return self._first_page

    @property
    def data(self) -> List[T]:
        """Items from the first page."""
        return self._ensure_first_page().data

    @property
    def has_more(self) -> bool:
        return self._ensure_first_page().has_more

    @property
    def next_cursor(self) -> Optional[str]:
        return self._ensure_first_page().next_cursor

    def first(self) -> Optional[T]:
        """Get the first item, or None if empty."""
        data = self.data
        return data[0] if data else None

    def __iter__(self) -> Iterator[T]:
        """Auto-paginate through all results."""
        page = self._ensure_first_page()
        yield from page.data

        while page.has_more and page.next_cursor:
            params = {**self._params, "after": page.next_cursor}
            page = self._fetch_page(params)
            yield from page.data


class AsyncPage(Generic[T]):
    """A single async page of results."""

    def __init__(
        self,
        data: List[T],
        has_more: bool,
        next_cursor: Optional[str] = None,
        total: Optional[int] = None,
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
        params: Optional[dict[str, Any]] = None,
        data_key: str = "data",
    ) -> None:
        self._http = http
        self._path = path
        self._model = model
        self._params = params or {}
        self._data_key = data_key
        self._first_page: Optional[AsyncPage[T]] = None

    async def _fetch_page(self, params: dict[str, Any]) -> AsyncPage[T]:
        response = await self._http.get(self._path, params=params)
        body = response.json()

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
        if self._first_page is None:
            self._first_page = await self._fetch_page(self._params)
        return self._first_page

    async def get_data(self) -> List[T]:
        """Items from the first page.

        Unlike ``SyncCursorPage.data`` (a property), this must be awaited::

            data = await page.get_data()
        """
        page = await self._ensure_first_page()
        return page.data

    async def first(self) -> Optional[T]:
        page = await self._ensure_first_page()
        return page.data[0] if page.data else None

    async def __aiter__(self):  # type: ignore[override]
        page = await self._ensure_first_page()
        for item in page.data:
            yield item

        while page.has_more and page.next_cursor:
            params = {**self._params, "after": page.next_cursor}
            page = await self._fetch_page(params)
            for item in page.data:
                yield item
