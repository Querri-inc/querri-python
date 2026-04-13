"""Project and Chat resources for the Querri API.

Projects are the core entity — they contain steps, data flows, and chats.
Chats are nested under projects and support streaming AI responses.
"""

from __future__ import annotations

import builtins
from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from .._pagination import AsyncCursorPage, SyncCursorPage
from .._streaming import AsyncChatStream, ChatStream
from ..types.chat import Chat, ChatCancelResponse
from ..types.data import DataPage
from ..types.project import (
    AddSourceResponse,
    Project,
    ProjectCancelResponse,
    ProjectRunResponse,
    ProjectRunStatus,
    StepSummary,
)

# ---------------------------------------------------------------------------
# Chats (sync)
# ---------------------------------------------------------------------------


class Chats:
    """Sub-resource for chat operations within a project.

    Accessed via ``client.projects.chats``.
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    # -- CRUD ---------------------------------------------------------------

    def create(
        self,
        project_id: str,
        *,
        name: str | None = None,
    ) -> Chat:
        """Create a new chat on a project.

        Args:
            project_id: The project UUID.
            name: Optional display name for the chat.

        Returns:
            Chat object with id, project_id, name, created_at.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        response = self._http.post(f"/projects/{project_id}/chats", json=body)
        return Chat.model_validate(response.json())

    def get(
        self,
        project_id: str,
        chat_id: str,
    ) -> Chat:
        """Get chat details with full message history.

        Args:
            project_id: The project UUID.
            chat_id: The chat UUID.

        Returns:
            Chat object with id, project_id, name, messages, timestamps.
        """
        response = self._http.get(f"/projects/{project_id}/chats/{chat_id}")
        return Chat.model_validate(response.json())

    def list(
        self,
        project_id: str,
        *,
        limit: int = 25,
    ) -> builtins.list[Chat]:
        """List chats on a project.

        Note: The server returns a flat list (no cursor pagination for chats).

        Args:
            project_id: The project UUID.
            limit: Maximum number of chats to return.

        Returns:
            List of Chat objects.
        """
        response = self._http.get(
            f"/projects/{project_id}/chats",
            params={"limit": limit},
        )
        body = response.json()
        return [Chat.model_validate(c) for c in body.get("data", [])]

    # -- Streaming ----------------------------------------------------------

    def stream(
        self,
        project_id: str,
        chat_id: str,
        *,
        prompt: str,
        user_id: str,
        model: str | None = None,
        experimental_v2: bool = False,
    ) -> ChatStream:
        """Send a message and stream the AI response via SSE.

        Args:
            project_id: The project UUID.
            chat_id: The chat UUID.
            prompt: The user message to send.
            user_id: User ID (or external ID) sending the message.
            model: Optional model selection (default "standard").
            experimental_v2: Use experimental v2 agent (faster, direct SQL execution).

        Returns:
            A ``ChatStream`` that yields text chunks.

        Example::

            stream = client.projects.chats.stream(
                project_id, chat_id,
                prompt="Summarize the data",
                user_id="user_123",
            )
            for chunk in stream:
                print(chunk, end="", flush=True)
        """
        body: dict[str, Any] = {
            "prompt": prompt,
            "user_id": user_id,
        }
        if model is not None:
            body["model"] = model
        if experimental_v2:
            body["experimentalV2"] = True
        response = self._http.post(
            f"/projects/{project_id}/chats/{chat_id}/stream",
            json=body,
            stream=True,
        )
        return ChatStream(response)

    # -- Actions ------------------------------------------------------------

    def cancel(
        self,
        project_id: str,
        chat_id: str,
    ) -> ChatCancelResponse:
        """Cancel an active chat stream.

        Args:
            project_id: The project UUID.
            chat_id: The chat UUID.

        Returns:
            Response with id, message_id, and cancelled status.
        """
        response = self._http.post(f"/projects/{project_id}/chats/{chat_id}/cancel")
        return ChatCancelResponse.model_validate(response.json())

    def delete(
        self,
        project_id: str,
        chat_id: str,
    ) -> None:
        """Delete a chat from a project.

        Args:
            project_id: The project UUID.
            chat_id: The chat UUID.
        """
        self._http.delete(f"/projects/{project_id}/chats/{chat_id}")


# ---------------------------------------------------------------------------
# AsyncChats
# ---------------------------------------------------------------------------


class AsyncChats:
    """Async sub-resource for chat operations within a project.

    Accessed via ``client.projects.chats``.
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create(
        self,
        project_id: str,
        *,
        name: str | None = None,
    ) -> Chat:
        """Create a new chat on a project.

        Args:
            project_id: The project UUID.
            name: Optional display name for the chat.

        Returns:
            Chat object with id, project_id, name, created_at.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        response = await self._http.post(f"/projects/{project_id}/chats", json=body)
        return Chat.model_validate(response.json())

    async def get(
        self,
        project_id: str,
        chat_id: str,
    ) -> Chat:
        """Get chat details with full message history.

        Args:
            project_id: The project UUID.
            chat_id: The chat UUID.

        Returns:
            Chat object with id, project_id, name, messages, timestamps.
        """
        response = await self._http.get(f"/projects/{project_id}/chats/{chat_id}")
        return Chat.model_validate(response.json())

    async def list(
        self,
        project_id: str,
        *,
        limit: int = 25,
    ) -> builtins.list[Chat]:
        """List chats on a project.

        Note: The server returns a flat list (no cursor pagination for chats).

        Args:
            project_id: The project UUID.
            limit: Maximum number of chats to return.

        Returns:
            List of Chat objects.
        """
        response = await self._http.get(
            f"/projects/{project_id}/chats",
            params={"limit": limit},
        )
        body = response.json()
        return [Chat.model_validate(c) for c in body.get("data", [])]

    async def stream(
        self,
        project_id: str,
        chat_id: str,
        *,
        prompt: str,
        user_id: str,
        model: str | None = None,
        experimental_v2: bool = False,
    ) -> AsyncChatStream:
        """Send a message and stream the AI response via SSE.

        Args:
            project_id: The project UUID.
            chat_id: The chat UUID.
            prompt: The user message to send.
            user_id: User ID (or external ID) sending the message.
            model: Optional model selection (default "standard").
            experimental_v2: Use experimental v2 agent (faster, direct SQL execution).

        Returns:
            An ``AsyncChatStream`` that yields text chunks.

        Example::

            stream = await client.projects.chats.stream(
                project_id, chat_id,
                prompt="Summarize the data",
                user_id="user_123",
            )
            async for chunk in stream:
                print(chunk, end="", flush=True)
        """
        body: dict[str, Any] = {
            "prompt": prompt,
            "user_id": user_id,
        }
        if model is not None:
            body["model"] = model
        if experimental_v2:
            body["experimentalV2"] = True
        response = await self._http.post(
            f"/projects/{project_id}/chats/{chat_id}/stream",
            json=body,
            stream=True,
        )
        return AsyncChatStream(response)

    async def cancel(
        self,
        project_id: str,
        chat_id: str,
    ) -> ChatCancelResponse:
        """Cancel an active chat stream.

        Args:
            project_id: The project UUID.
            chat_id: The chat UUID.

        Returns:
            Response with id, message_id, and cancelled status.
        """
        response = await self._http.post(
            f"/projects/{project_id}/chats/{chat_id}/cancel",
        )
        return ChatCancelResponse.model_validate(response.json())

    async def delete(
        self,
        project_id: str,
        chat_id: str,
    ) -> None:
        """Delete a chat from a project.

        Args:
            project_id: The project UUID.
            chat_id: The chat UUID.
        """
        await self._http.delete(f"/projects/{project_id}/chats/{chat_id}")


# ---------------------------------------------------------------------------
# Projects (sync)
# ---------------------------------------------------------------------------


class Projects:
    """Resource for project operations.

    Example::

        # List projects
        for project in client.projects.list():
            print(project.name)

        # Create a project
        project = client.projects.create(name="My Project", user_id="usr_123")

        # Stream a chat
        stream = client.projects.chats.stream(
            project.id, chat_id,
            prompt="Analyze this data",
            user_id="usr_123",
        )
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http
        self._chats = Chats(http)

    @property
    def chats(self) -> Chats:
        """Access the nested Chats sub-resource."""
        return self._chats

    # -- CRUD ---------------------------------------------------------------

    def create(
        self,
        *,
        name: str,
        user_id: str,
        description: str | None = None,
    ) -> Project:
        """Create a new project.

        Args:
            name: Project name (1-255 chars).
            user_id: Owner user ID or external ID.
            description: Optional description (max 2000 chars).

        Returns:
            Created Project object.
        """
        body: dict[str, Any] = {"name": name, "user_id": user_id}
        if description is not None:
            body["description"] = description
        response = self._http.post("/projects", json=body)
        return Project.model_validate(response.json())

    def get(self, project_id: str) -> Project:
        """Get project detail with step summaries.

        Args:
            project_id: The project UUID.

        Returns:
            Project object including steps list.
        """
        response = self._http.get(f"/projects/{project_id}")
        return Project.model_validate(response.json())

    def list(
        self,
        *,
        limit: int = 25,
        after: str | None = None,
        user_id: str | None = None,
    ) -> SyncCursorPage[Project]:
        """List projects with cursor pagination.

        Args:
            limit: Maximum number of projects per page (1-200).
            after: Cursor for the next page.
            user_id: Filter projects by owner user ID.

        Returns:
            Auto-paginating iterator of Project objects.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        if user_id is not None:
            params["user_id"] = user_id
        return SyncCursorPage(self._http, "/projects", Project, params=params)

    def update(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Project:
        """Update project name and/or description.

        Args:
            project_id: The project UUID.
            name: New project name.
            description: New description.

        Returns:
            Updated Project object.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        response = self._http.put(f"/projects/{project_id}", json=body)
        return Project.model_validate(response.json())

    def delete(self, project_id: str) -> None:
        """Delete a project and clean up associated resources.

        Args:
            project_id: The project UUID.
        """
        self._http.delete(f"/projects/{project_id}")

    # -- Sources ------------------------------------------------------------

    def add_source(
        self,
        project_id: str,
        file_id: str,
        *,
        run: bool = True,
    ) -> AddSourceResponse:
        """Add a file as a data source to a project.

        Args:
            project_id: The project UUID.
            file_id: The file UUID to add as a source.
            run: Whether to trigger project execution after adding (default True).

        Returns:
            Response with step_id, project_id, and status.
        """
        body: dict[str, Any] = {"file_id": file_id, "run": run}
        response = self._http.post(f"/projects/{project_id}/sources", json=body)
        return AddSourceResponse.model_validate(response.json())

    # -- Execution ----------------------------------------------------------

    def run(
        self,
        project_id: str,
        *,
        user_id: str,
    ) -> ProjectRunResponse:
        """Submit a project for execution.

        Args:
            project_id: The project UUID.
            user_id: User ID (or external ID) for execution context.

        Returns:
            Response with id, run_id, and status ("submitted").
        """
        body: dict[str, Any] = {"user_id": user_id}
        response = self._http.post(f"/projects/{project_id}/run", json=body)
        return ProjectRunResponse.model_validate(response.json())

    def run_status(self, project_id: str) -> ProjectRunStatus:
        """Check execution status for a project.

        Args:
            project_id: The project UUID.

        Returns:
            Status with id, status, and is_running flag.
        """
        response = self._http.get(f"/projects/{project_id}/run/status")
        return ProjectRunStatus.model_validate(response.json())

    def run_cancel(self, project_id: str) -> ProjectCancelResponse:
        """Cancel a running project execution.

        Args:
            project_id: The project UUID.

        Returns:
            Response with id and cancelled flag.
        """
        response = self._http.post(f"/projects/{project_id}/run/cancel")
        return ProjectCancelResponse.model_validate(response.json())

    # -- Steps --------------------------------------------------------------

    def list_steps(self, project_id: str) -> builtins.list[StepSummary]:
        """List steps in a project with summary metadata.

        Args:
            project_id: The project UUID.

        Returns:
            List of StepSummary objects.
        """
        response = self._http.get(f"/projects/{project_id}/steps")
        body = response.json()
        return [StepSummary.model_validate(s) for s in body.get("data", [])]

    def get_step_data(
        self,
        project_id: str,
        step_id: str,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> DataPage:
        """Get paginated step result data (with RLS enforcement).

        Args:
            project_id: The project UUID.
            step_id: The step UUID.
            page: Page number (1-indexed).
            page_size: Rows per page (1-10000).

        Returns:
            Paginated DataPage object.
        """
        response = self._http.get(
            f"/projects/{project_id}/steps/{step_id}/data",
            params={"page": page, "page_size": page_size},
        )
        return DataPage.model_validate(response.json())


# ---------------------------------------------------------------------------
# AsyncProjects
# ---------------------------------------------------------------------------


class AsyncProjects:
    """Async resource for project operations.

    Example::

        # List projects
        async for project in client.projects.list():
            print(project.name)

        # Create a project
        project = await client.projects.create(name="My Project", user_id="usr_123")

        # Stream a chat
        stream = await client.projects.chats.stream(
            project.id, chat_id,
            prompt="Analyze this data",
            user_id="usr_123",
        )
        async for chunk in stream:
            print(chunk, end="", flush=True)
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http
        self._chats = AsyncChats(http)

    @property
    def chats(self) -> AsyncChats:
        """Access the nested async Chats sub-resource."""
        return self._chats

    # -- CRUD ---------------------------------------------------------------

    async def create(
        self,
        *,
        name: str,
        user_id: str,
        description: str | None = None,
    ) -> Project:
        """Create a new project.

        Args:
            name: Project name (1-255 chars).
            user_id: Owner user ID or external ID.
            description: Optional description (max 2000 chars).

        Returns:
            Created Project object.
        """
        body: dict[str, Any] = {"name": name, "user_id": user_id}
        if description is not None:
            body["description"] = description
        response = await self._http.post("/projects", json=body)
        return Project.model_validate(response.json())

    async def get(self, project_id: str) -> Project:
        """Get project detail with step summaries.

        Args:
            project_id: The project UUID.

        Returns:
            Project object including steps list.
        """
        response = await self._http.get(f"/projects/{project_id}")
        return Project.model_validate(response.json())

    def list(
        self,
        *,
        limit: int = 25,
        after: str | None = None,
        user_id: str | None = None,
    ) -> AsyncCursorPage[Project]:
        """List projects with cursor pagination.

        Args:
            limit: Maximum number of projects per page (1-200).
            after: Cursor for the next page.
            user_id: Filter projects by owner user ID.

        Returns:
            Auto-paginating iterator of Project objects.
        """
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        if user_id is not None:
            params["user_id"] = user_id
        return AsyncCursorPage(self._http, "/projects", Project, params=params)

    async def update(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Project:
        """Update project name and/or description.

        Args:
            project_id: The project UUID.
            name: New project name.
            description: New description.

        Returns:
            Updated Project object.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        response = await self._http.put(f"/projects/{project_id}", json=body)
        return Project.model_validate(response.json())

    async def delete(self, project_id: str) -> None:
        """Delete a project and clean up associated resources.

        Args:
            project_id: The project UUID.
        """
        await self._http.delete(f"/projects/{project_id}")

    # -- Sources ------------------------------------------------------------

    async def add_source(
        self,
        project_id: str,
        file_id: str,
        *,
        run: bool = True,
    ) -> AddSourceResponse:
        """Add a file as a data source to a project."""
        body: dict[str, Any] = {"file_id": file_id, "run": run}
        response = await self._http.post(f"/projects/{project_id}/sources", json=body)
        return AddSourceResponse.model_validate(response.json())

    # -- Execution ----------------------------------------------------------

    async def run(
        self,
        project_id: str,
        *,
        user_id: str,
    ) -> ProjectRunResponse:
        """Submit a project for execution.

        Args:
            project_id: The project UUID.
            user_id: User ID (or external ID) for execution context.

        Returns:
            Response with id, run_id, and status ("submitted").
        """
        body: dict[str, Any] = {"user_id": user_id}
        response = await self._http.post(f"/projects/{project_id}/run", json=body)
        return ProjectRunResponse.model_validate(response.json())

    async def run_status(self, project_id: str) -> ProjectRunStatus:
        """Check execution status for a project.

        Args:
            project_id: The project UUID.

        Returns:
            Status with id, status, and is_running flag.
        """
        response = await self._http.get(f"/projects/{project_id}/run/status")
        return ProjectRunStatus.model_validate(response.json())

    async def run_cancel(self, project_id: str) -> ProjectCancelResponse:
        """Cancel a running project execution.

        Args:
            project_id: The project UUID.

        Returns:
            Response with id and cancelled flag.
        """
        response = await self._http.post(f"/projects/{project_id}/run/cancel")
        return ProjectCancelResponse.model_validate(response.json())

    # -- Steps --------------------------------------------------------------

    async def list_steps(self, project_id: str) -> builtins.list[StepSummary]:
        """List steps in a project with summary metadata.

        Args:
            project_id: The project UUID.

        Returns:
            List of StepSummary objects.
        """
        response = await self._http.get(f"/projects/{project_id}/steps")
        body = response.json()
        return [StepSummary.model_validate(s) for s in body.get("data", [])]

    async def get_step_data(
        self,
        project_id: str,
        step_id: str,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> DataPage:
        """Get paginated step result data (with RLS enforcement).

        Args:
            project_id: The project UUID.
            step_id: The step UUID.
            page: Page number (1-indexed).
            page_size: Rows per page (1-10000).

        Returns:
            Paginated DataPage object.
        """
        response = await self._http.get(
            f"/projects/{project_id}/steps/{step_id}/data",
            params={"page": page, "page_size": page_size},
        )
        return DataPage.model_validate(response.json())
