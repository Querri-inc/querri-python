"""Feature flags — the decided values for the caller's organization (read-only)."""

from __future__ import annotations

from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient


class Flags:
    """Synchronous flags resource.

    Usage::

        flags = client.flags.list()
        if flags.get("mcp_connectors"):
            ...
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def list(self) -> dict[str, Any]:
        """Every flag's decided value for this organization.

        Decided the way the app decides them: a per-org override, else the
        catalog default. Read only; flags are changed by Querri staff.

        Returns:
            ``{flag_key: value}``.
        """
        resp = self._http.get("/flags")
        data = resp.json().get("data", {})
        return dict(data) if isinstance(data, dict) else {}


class AsyncFlags:
    """Asynchronous flags resource. Mirrors :class:`Flags`."""

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def list(self) -> dict[str, Any]:
        """Every flag's decided value for this organization.

        Decided the way the app decides them: a per-org override, else the
        catalog default. Read only; flags are changed by Querri staff.

        Returns:
            ``{flag_key: value}``.
        """
        resp = await self._http.get("/flags")
        data = resp.json().get("data", {})
        return dict(data) if isinstance(data, dict) else {}


__all__ = ["Flags", "AsyncFlags"]
