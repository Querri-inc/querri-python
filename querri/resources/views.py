"""SQL-defined views resource."""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import time
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._pagination import AsyncCursorPage, SyncCursorPage

# Status vocabulary mirrors querri_core.views.run_state.TERMINAL_STATUSES.
# A polling client must stop when the server reports a status in this set —
# anything else is still in-flight. Kept as a tuple-with-frozenset wrapper so
# both ``in`` checks and serialization are cheap.
_TERMINAL_RUN_STATUSES: frozenset[str] = frozenset(
    {"completed", "partial", "failed"}
)


def _is_terminal_run_status(status: Any) -> bool:
    return isinstance(status, str) and status in _TERMINAL_RUN_STATUSES


class Views:
    """Synchronous views resource.

    Usage::

        views = client.views.list()
        view = client.views.create(
            name="Revenue by Region",
            sql_definition="SELECT ...",
        )
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def create(
        self,
        *,
        name: str | None = None,
        sql_definition: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a new SQL-defined view.

        All fields are optional — omit everything to create a draft view
        for NL authoring via ``chat()``.

        Args:
            name: Display name for the view.
            sql_definition: SQL query that defines the view.
            description: Optional description.

        Returns:
            Dict with view details including uuid, name, sql_definition.
        """
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if sql_definition is not None:
            payload["sql_definition"] = sql_definition
        if description is not None:
            payload["description"] = description
        resp = self._http.post("/views", json=payload)
        return resp.json()  # type: ignore[no-any-return]

    def list(
        self,
        *,
        limit: int = 25,
        after: str | None = None,
    ) -> SyncCursorPage[dict[str, Any]]:
        """List all views with cursor pagination.

        Args:
            limit: Maximum views per page (1-100).
            after: Cursor for the next page.

        Returns:
            Auto-paginating iterator of view summary dicts.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        return SyncCursorPage(self._http, "/views", None, params=params)

    def get(self, view_uuid: str) -> dict[str, Any]:
        """Get view details.

        Args:
            view_uuid: The view UUID.

        Returns:
            View detail dict.
        """
        resp = self._http.get(f"/views/{view_uuid}")
        return resp.json()  # type: ignore[no-any-return]

    def update(
        self,
        view_uuid: str,
        *,
        sql_definition: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Update a view.

        Args:
            view_uuid: The view UUID.
            sql_definition: Updated SQL definition.
            description: Updated description.

        Returns:
            Dict with updated view details.
        """
        payload: dict[str, Any] = {}
        if sql_definition is not None:
            payload["sql_definition"] = sql_definition
        if description is not None:
            payload["description"] = description
        resp = self._http.patch(f"/views/{view_uuid}", json=payload)
        return resp.json()  # type: ignore[no-any-return]

    def delete(self, view_uuid: str) -> None:
        """Delete a view.

        Args:
            view_uuid: The view UUID.
        """
        self._http.delete(f"/views/{view_uuid}")

    def run(
        self,
        *,
        view_uuids: builtins.list[str] | None = None,
        wait: bool = True,
        timeout: float | None = 1800.0,
        poll_interval: float = 2.0,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Run view materialization. Polls until completion by default.

        The server returns 202 with a ``run_id`` immediately; this method
        polls ``GET /views/runs/{run_id}`` until the run reaches a terminal
        status (``completed`` | ``partial`` | ``failed``). Pass ``wait=False``
        to get back the initial 202 envelope and poll yourself via
        :meth:`get_run`.

        The default ``timeout=1800`` (30 min) covers every materialization we
        have seen in production while bounding pathological hangs. Set to
        ``None`` to wait forever; pass a smaller value for chatty CLI use.

        Args:
            view_uuids: Optional list of specific view UUIDs. ``None`` ⇒ DAG.
            wait: If True (default) blocks until terminal status. If False
                returns the initial 202 envelope immediately.
            timeout: Max seconds to wait when ``wait=True``. Raises
                ``TimeoutError`` if the run is still in flight when it
                elapses. ``None`` disables the bound.
            poll_interval: Seconds between status polls.
            on_progress: Optional callback fired once per **distinct** status
                value (so ``queued`` → ``running`` produces two calls, not N).
                Exceptions in the callback are swallowed so a broken consumer
                cannot strand the poll loop.

        Returns:
            Terminal run record (``wait=True``) or the initial 202 envelope
            (``wait=False``).
        """
        payload: dict[str, Any] = {}
        if view_uuids is not None:
            payload["view_uuids"] = view_uuids
        resp = self._http.post("/views/run", json=payload)
        envelope: dict[str, Any] = resp.json()

        if not wait:
            return envelope

        run_id = envelope.get("run_id")
        if not run_id:
            # Fallback for older servers that haven't shipped the 202
            # contract yet — pre-async-poll responses had succeeded/failed
            # inline and never produced a run_id. Returning the envelope
            # unchanged keeps the SDK compatible with both server versions.
            return envelope

        return self.wait_for_run(
            run_id,
            timeout=timeout,
            poll_interval=poll_interval,
            on_progress=on_progress,
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Fetch the current state of a view run.

        Status is one of ``queued`` | ``running`` | ``completed`` |
        ``partial`` | ``failed``. Returns 404 once the server's TTL elapses.
        """
        resp = self._http.get(f"/views/runs/{run_id}")
        return resp.json()  # type: ignore[no-any-return]

    def wait_for_run(
        self,
        run_id: str,
        *,
        timeout: float | None = 1800.0,
        poll_interval: float = 2.0,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Block until ``run_id`` reaches a terminal status, then return it.

        Polls ``GET /views/runs/{run_id}`` every ``poll_interval`` seconds.
        See :meth:`run` for argument semantics.
        """
        deadline = (
            time.monotonic() + timeout if timeout is not None else None
        )
        last_seen: str | None = None

        while True:
            record = self.get_run(run_id)
            status = record.get("status")

            if on_progress is not None and status != last_seen:
                # Broken callback should not strand the polling loop.
                with contextlib.suppress(Exception):
                    on_progress(record)
                last_seen = status

            if _is_terminal_run_status(status):
                return record

            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(
                    f"View run {run_id} did not finish within "
                    f"{timeout}s (last status={status!r})."
                )

            time.sleep(poll_interval)

    def preview(self, view_uuid: str, *, limit: int = 100) -> dict[str, Any]:
        """Preview view results without materializing.

        Args:
            view_uuid: The view UUID.
            limit: Maximum number of rows to return.

        Returns:
            Dict with preview data rows and column info.
        """
        resp = self._http.post(
            f"/views/{view_uuid}/preview",
            json={"limit": limit},
        )
        return resp.json()  # type: ignore[no-any-return]

    def chat(self, view_uuid: str, *, message: str) -> Iterator[str]:
        """Send a message to the view authoring agent and stream the response.

        Args:
            view_uuid: The view UUID.
            message: Natural-language message for the agent.

        Yields:
            Raw SSE data lines from the agent response.
        """
        resp = self._http.request(
            "POST",
            f"/views/{view_uuid}/chat",
            json={"message": message},
            stream=True,
        )
        try:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    yield line[6:]
        finally:
            resp.close()

    def generate_metadata(self, view_uuid: str) -> dict[str, Any]:
        """Generate name and description from the view's SQL and conversation.

        Args:
            view_uuid: The view UUID.

        Returns:
            Dict with generated name and description.
        """
        resp = self._http.post(f"/views/{view_uuid}/generate-metadata")
        return resp.json()  # type: ignore[no-any-return]


class AsyncViews:
    """Asynchronous views resource.

    Usage::

        views = await client.views.list()
        view = await client.views.create(
            name="Revenue by Region",
            sql_definition="SELECT ...",
        )
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create(
        self,
        *,
        name: str | None = None,
        sql_definition: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a new SQL-defined view.

        All fields are optional — omit everything to create a draft view
        for NL authoring via ``chat()``.

        Args:
            name: Display name for the view.
            sql_definition: SQL query that defines the view.
            description: Optional description.

        Returns:
            Dict with view details including uuid, name, sql_definition.
        """
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if sql_definition is not None:
            payload["sql_definition"] = sql_definition
        if description is not None:
            payload["description"] = description
        resp = await self._http.post("/views", json=payload)
        return resp.json()  # type: ignore[no-any-return]

    async def list(
        self,
        *,
        limit: int = 25,
        after: str | None = None,
    ) -> AsyncCursorPage[dict[str, Any]]:
        """List all views with cursor pagination.

        Args:
            limit: Maximum views per page (1-100).
            after: Cursor for the next page.

        Returns:
            Auto-paginating iterator of view summary dicts.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        return AsyncCursorPage(self._http, "/views", None, params=params)

    async def get(self, view_uuid: str) -> dict[str, Any]:
        """Get view details.

        Args:
            view_uuid: The view UUID.

        Returns:
            View detail dict.
        """
        resp = await self._http.get(f"/views/{view_uuid}")
        return resp.json()  # type: ignore[no-any-return]

    async def update(
        self,
        view_uuid: str,
        *,
        sql_definition: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Update a view.

        Args:
            view_uuid: The view UUID.
            sql_definition: Updated SQL definition.
            description: Updated description.

        Returns:
            Dict with updated view details.
        """
        payload: dict[str, Any] = {}
        if sql_definition is not None:
            payload["sql_definition"] = sql_definition
        if description is not None:
            payload["description"] = description
        resp = await self._http.patch(f"/views/{view_uuid}", json=payload)
        return resp.json()  # type: ignore[no-any-return]

    async def delete(self, view_uuid: str) -> None:
        """Delete a view.

        Args:
            view_uuid: The view UUID.
        """
        await self._http.delete(f"/views/{view_uuid}")

    async def run(
        self,
        *,
        view_uuids: builtins.list[str] | None = None,
        wait: bool = True,
        timeout: float | None = 1800.0,
        poll_interval: float = 2.0,
        on_progress: Callable[[dict[str, Any]], Any] | None = None,
    ) -> dict[str, Any]:
        """Run view materialization. Polls until completion by default.

        Async mirror of :meth:`Views.run`. ``on_progress`` may be a sync or
        async callable; awaitable returns are awaited.
        """
        payload: dict[str, Any] = {}
        if view_uuids is not None:
            payload["view_uuids"] = view_uuids
        resp = await self._http.post("/views/run", json=payload)
        envelope: dict[str, Any] = resp.json()

        if not wait:
            return envelope

        run_id = envelope.get("run_id")
        if not run_id:
            return envelope

        return await self.wait_for_run(
            run_id,
            timeout=timeout,
            poll_interval=poll_interval,
            on_progress=on_progress,
        )

    async def get_run(self, run_id: str) -> dict[str, Any]:
        """Fetch the current state of a view run."""
        resp = await self._http.get(f"/views/runs/{run_id}")
        return resp.json()  # type: ignore[no-any-return]

    async def wait_for_run(
        self,
        run_id: str,
        *,
        timeout: float | None = 1800.0,
        poll_interval: float = 2.0,
        on_progress: Callable[[dict[str, Any]], Any] | None = None,
    ) -> dict[str, Any]:
        """Block until ``run_id`` reaches a terminal status, then return it.

        See :meth:`Views.wait_for_run` for argument semantics; ``on_progress``
        may be a sync or async callable.
        """
        loop = asyncio.get_event_loop()
        deadline = (
            loop.time() + timeout if timeout is not None else None
        )
        last_seen: str | None = None

        while True:
            record = await self.get_run(run_id)
            status = record.get("status")

            if on_progress is not None and status != last_seen:
                try:
                    cb_result = on_progress(record)
                    if asyncio.iscoroutine(cb_result):
                        await cb_result
                except Exception:
                    pass
                last_seen = status

            if _is_terminal_run_status(status):
                return record

            if deadline is not None and loop.time() >= deadline:
                raise TimeoutError(
                    f"View run {run_id} did not finish within "
                    f"{timeout}s (last status={status!r})."
                )

            await asyncio.sleep(poll_interval)

    async def preview(self, view_uuid: str, *, limit: int = 100) -> dict[str, Any]:
        """Preview view results without materializing.

        Args:
            view_uuid: The view UUID.
            limit: Maximum number of rows to return.

        Returns:
            Dict with preview data rows and column info.
        """
        resp = await self._http.post(
            f"/views/{view_uuid}/preview",
            json={"limit": limit},
        )
        return resp.json()  # type: ignore[no-any-return]

    async def chat(self, view_uuid: str, *, message: str) -> AsyncIterator[str]:
        """Send a message to the view authoring agent and stream the response.

        Args:
            view_uuid: The view UUID.
            message: Natural-language message for the agent.

        Yields:
            Raw SSE data lines from the agent response.
        """
        resp = await self._http.request(
            "POST",
            f"/views/{view_uuid}/chat",
            json={"message": message},
            stream=True,
        )
        try:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]
        finally:
            await resp.aclose()

    async def generate_metadata(self, view_uuid: str) -> dict[str, Any]:
        """Generate name and description from the view's SQL and conversation.

        Args:
            view_uuid: The view UUID.

        Returns:
            Dict with generated name and description.
        """
        resp = await self._http.post(f"/views/{view_uuid}/generate-metadata")
        return resp.json()  # type: ignore[no-any-return]
