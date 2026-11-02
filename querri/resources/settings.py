"""Organization settings — read-only, maps to ``/settings/*``."""

from __future__ import annotations

from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient


class Settings:
    """Synchronous settings resource.

    Usage::

        context = client.settings.get_context()
        print(context.get("analysis_preferences"))
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def get_context(self) -> dict[str, Any]:
        """The organization's AI context — what Settings → Customize holds.

        The same document the app reads: business context, data processing
        instructions, analysis preferences, glossary and the like. Read only.

        Returns:
            The context document, as the server returns it.
        """
        resp = self._http.get("/settings/context")
        return dict(resp.json())


class AsyncSettings:
    """Asynchronous settings resource. Mirrors :class:`Settings`."""

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def get_context(self) -> dict[str, Any]:
        """The organization's AI context — what Settings → Customize holds.

        The same document the app reads: business context, data processing
        instructions, analysis preferences, glossary and the like. Read only.

        Returns:
            The context document, as the server returns it.
        """
        resp = await self._http.get("/settings/context")
        return dict(resp.json())


__all__ = ["Settings", "AsyncSettings"]
