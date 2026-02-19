"""SSE stream handling for chat responses.

Parses the Vercel AI SDK SSE chunk format:
- 0: text content chunks
- e: completion/error events
- d: done signal
"""

from __future__ import annotations

from typing import Iterator, Optional

import httpx

from ._exceptions import StreamCancelledError, StreamError, StreamTimeoutError


def _parse_sse_line(line: str) -> Optional[tuple[str, str]]:
    """Parse a single SSE line into (type_prefix, data).

    Returns None for empty lines, comments, or unparseable lines.
    """
    line = line.strip()
    if not line or line.startswith(":"):
        return None

    # Vercel AI SDK format: "0:text chunk" or "e:event" or "d:done"
    if len(line) >= 2 and line[1] == ":":
        return (line[0], line[2:])

    # Standard SSE format: "data: ..."
    if line.startswith("data: "):
        return ("data", line[6:])

    return None


class ChatStream:
    """Synchronous iterator over SSE chat response chunks.

    Usage::

        stream = client.projects.chats.stream(project_id, chat_id, ...)

        # Iterate chunks
        for chunk in stream:
            print(chunk, end="", flush=True)

        # Or get full text
        text = stream.text()
    """

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self._text_chunks: list[str] = []
        self._done = False
        self._cancelled = False
        self._message_id = response.headers.get("x-message-id")

    @property
    def message_id(self) -> Optional[str]:
        return self._message_id

    def __iter__(self) -> Iterator[str]:
        try:
            for line in self._response.iter_lines():
                if self._cancelled:
                    break

                parsed = _parse_sse_line(line)
                if parsed is None:
                    continue

                prefix, data = parsed

                if prefix == "0":
                    # Text content chunk — strip surrounding quotes if present
                    text = data
                    if text.startswith('"') and text.endswith('"'):
                        text = text[1:-1]
                        # Unescape common sequences
                        text = text.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
                    self._text_chunks.append(text)
                    yield text

                elif prefix == "e":
                    # Error event
                    raise StreamError(f"Stream error: {data}")

                elif prefix == "d":
                    # Done signal
                    self._done = True
                    break

        except httpx.ReadTimeout as exc:
            raise StreamTimeoutError(
                "Stream timed out waiting for data"
            ) from exc
        finally:
            self._response.close()

    def text(self) -> str:
        """Consume the entire stream and return the full text."""
        if not self._text_chunks:
            # Haven't iterated yet — consume now
            for _ in self:
                pass
        return "".join(self._text_chunks)

    def cancel(self) -> None:
        """Cancel the stream."""
        self._cancelled = True
        self._response.close()
        raise StreamCancelledError("Stream cancelled by client")


class AsyncChatStream:
    """Asynchronous iterator over SSE chat response chunks.

    Usage::

        stream = await client.projects.chats.stream(project_id, chat_id, ...)

        async for chunk in stream:
            print(chunk, end="", flush=True)

        text = await stream.text()
    """

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self._text_chunks: list[str] = []
        self._done = False
        self._cancelled = False
        self._message_id = response.headers.get("x-message-id")

    @property
    def message_id(self) -> Optional[str]:
        return self._message_id

    async def __aiter__(self):  # type: ignore[override]
        try:
            async for line in self._response.aiter_lines():
                if self._cancelled:
                    break

                parsed = _parse_sse_line(line)
                if parsed is None:
                    continue

                prefix, data = parsed

                if prefix == "0":
                    text = data
                    if text.startswith('"') and text.endswith('"'):
                        text = text[1:-1]
                        text = text.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
                    self._text_chunks.append(text)
                    yield text

                elif prefix == "e":
                    raise StreamError(f"Stream error: {data}")

                elif prefix == "d":
                    self._done = True
                    break

        except httpx.ReadTimeout as exc:
            raise StreamTimeoutError(
                "Stream timed out waiting for data"
            ) from exc
        finally:
            await self._response.aclose()

    async def text(self) -> str:
        """Consume the entire stream and return the full text."""
        if not self._text_chunks:
            async for _ in self:
                pass
        return "".join(self._text_chunks)

    async def cancel(self) -> None:
        """Cancel the stream."""
        self._cancelled = True
        await self._response.aclose()
        raise StreamCancelledError("Stream cancelled by client")
