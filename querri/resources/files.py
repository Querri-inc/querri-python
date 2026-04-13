"""File management resource — upload, list, get, delete files."""

from __future__ import annotations

import builtins
import os

from .._base_client import AsyncHTTPClient, SyncHTTPClient
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

    def list(self) -> builtins.list[File]:
        """List files for the organization.

        Returns:
            List of File objects.
        """
        resp = self._http.get("/files")
        body = resp.json()
        return [File.model_validate(f) for f in body.get("data", [])]

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

    async def list(self) -> builtins.list[File]:
        """List files for the organization.

        Returns:
            List of File objects.
        """
        resp = await self._http.get("/files")
        body = resp.json()
        return [File.model_validate(f) for f in body.get("data", [])]

    async def delete(self, file_id: str) -> None:
        """Delete a file.

        Args:
            file_id: The file UUID.
        """
        await self._http.delete(f"/files/{file_id}")
