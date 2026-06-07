"""File management resource — upload, list, get, delete files."""

from __future__ import annotations

import os
from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._pagination import AsyncCursorPage, SyncCursorPage
from ..types.file import File


class Files:
    """Synchronous file management resource.

    Usage::

        info = client.files.upload("/path/to/data.csv")
        files = client.files.list()
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def upload(
        self,
        file_path: str,
        *,
        name: str | None = None,
    ) -> File:
        """Upload a file.

        Args:
            file_path: Local path to the file to upload.
            name: Optional display name (defaults to filename).

        Returns:
            File object with id, name, size, content_type.
        """
        filename = name or os.path.basename(file_path)
        with open(file_path, "rb") as f:
            files = {"file": (filename, f)}
            resp = self._http.post(
                "/files/upload",
                files=files,
                headers={"filename": filename},
            )
        return File.model_validate(resp.json())

    def get(self, file_id: str) -> File:
        """Get file metadata.

        Args:
            file_id: The file UUID.

        Returns:
            File object with id, name, size, content_type, etc.
        """
        resp = self._http.get(f"/files/{file_id}")
        return File.model_validate(resp.json())

    def list(
        self,
        *,
        limit: int = 25,
        after: str | None = None,
    ) -> SyncCursorPage[File]:
        """List files for the organization with cursor pagination.

        Args:
            limit: Maximum files per page (1-100).
            after: Cursor for the next page.

        Returns:
            Auto-paginating iterator of File objects.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        return SyncCursorPage(self._http, "/files", File, params=params)

    def delete(self, file_id: str) -> None:
        """Delete a file.

        Args:
            file_id: The file UUID.
        """
        self._http.delete(f"/files/{file_id}")


class AsyncFiles:
    """Asynchronous file management resource.

    Usage::

        info = await client.files.upload("/path/to/data.csv")
        files = await client.files.list()
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def upload(
        self,
        file_path: str,
        *,
        name: str | None = None,
    ) -> File:
        """Upload a file.

        Args:
            file_path: Local path to the file to upload.
            name: Optional display name (defaults to filename).

        Returns:
            File object with id, name, size, content_type.
        """
        filename = name or os.path.basename(file_path)
        with open(file_path, "rb") as f:
            files = {"file": (filename, f)}
            resp = await self._http.post(
                "/files/upload",
                files=files,
                headers={"filename": filename},
            )
        return File.model_validate(resp.json())

    async def get(self, file_id: str) -> File:
        """Get file metadata.

        Args:
            file_id: The file UUID.

        Returns:
            File object with id, name, size, content_type, etc.
        """
        resp = await self._http.get(f"/files/{file_id}")
        return File.model_validate(resp.json())

    async def list(
        self,
        *,
        limit: int = 25,
        after: str | None = None,
    ) -> AsyncCursorPage[File]:
        """List files for the organization with cursor pagination.

        Args:
            limit: Maximum files per page (1-100).
            after: Cursor for the next page.

        Returns:
            Auto-paginating iterator of File objects.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        return AsyncCursorPage(self._http, "/files", File, params=params)

    async def delete(self, file_id: str) -> None:
        """Delete a file.

        Args:
            file_id: The file UUID.
        """
        await self._http.delete(f"/files/{file_id}")
