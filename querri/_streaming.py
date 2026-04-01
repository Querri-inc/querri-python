"""SSE stream handling for chat responses.

Parses both Vercel AI SDK v1 format (``0:text``, ``e:error``, ``d:done``)
and v2 SSE format (``event: text-delta``, ``data: {...}``).

v2 event types handled in v0.2.0 (must-parse):
  text-delta, tool-output-available, file, error, finish, terminate, [DONE]

Unknown event types are silently ignored for forward compatibility.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

import httpx

from ._exceptions import StreamCancelledError, StreamError, StreamTimeoutError

logger = logging.getLogger("querri")


# ---------------------------------------------------------------------------
# Typed event model
# ---------------------------------------------------------------------------


@dataclass
class ChatStreamEvent:
    """Typed event from a Vercel AI SDK v2 SSE stream.

    The ``event_type`` field indicates which fields are populated:

    - ``text-delta``: ``text`` contains the chunk.
    - ``tool-output-available``: ``tool_name`` and ``tool_data``.
    - ``file``: ``file_url`` and ``media_type``.
    - ``error``: ``error`` message.
    - ``finish``: ``usage`` dict with credits/tokens.
    - ``terminate``: ``terminate_reason`` and ``terminate_message``.
    - Unknown types: ``raw_data`` contains the unparsed data string.
    """

    event_type: str
    text: str | None = None
    tool_name: str | None = None
    tool_data: Any | None = None
    file_url: str | None = None
    media_type: str | None = None
    step_result: dict[str, Any] | None = None
    error: str | None = None
    usage: dict[str, Any] | None = None
    terminate_reason: str | None = None
    terminate_message: str | None = None
    raw_data: str | None = None


# ---------------------------------------------------------------------------
# SSE line parsing
# ---------------------------------------------------------------------------


def _parse_sse_line(line: str) -> Optional[tuple[str, str]]:
    """Parse a single SSE line into (type_prefix, data).

    Returns None for empty lines, comments, or unparseable lines.
    """
    line = line.strip()
    if not line or line.startswith(":"):
        return None

    # Vercel AI SDK v1 format: "0:text chunk" or "e:event" or "d:done"
    if len(line) >= 2 and line[1] == ":":
        return (line[0], line[2:])

    # Standard SSE format: "data: ..."
    if line.startswith("data: "):
        return ("data", line[6:])

    # SSE event type line: "event: text-delta"
    if line.startswith("event: "):
        return ("event", line[7:])

    return None


def _unquote_text(data: str) -> str:
    """Strip surrounding quotes and unescape a text chunk."""
    if data.startswith('"') and data.endswith('"'):
        data = data[1:-1]
        data = data.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
    return data


def _parse_json_safe(data: str) -> dict[str, Any] | None:
    """Parse JSON data, return None on failure."""
    try:
        result = json.loads(data)
        return result if isinstance(result, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _build_event(event_type: str, data: str) -> ChatStreamEvent:
    """Build a ChatStreamEvent from an event type and data payload."""
    parsed = _parse_json_safe(data)

    match event_type:
        case "text-delta":
            text = parsed.get("textDelta", data) if parsed else _unquote_text(data)
            return ChatStreamEvent(event_type=event_type, text=text)

        case "tool-output-available":
            return ChatStreamEvent(
                event_type=event_type,
                tool_name=parsed.get("toolName") if parsed else None,
                tool_data=parsed.get("output") if parsed else None,
                raw_data=data,
            )

        case "file":
            return ChatStreamEvent(
                event_type=event_type,
                file_url=parsed.get("url") if parsed else None,
                media_type=parsed.get("mediaType") if parsed else None,
                raw_data=data,
            )

        case "error":
            err_msg = parsed.get("message", data) if parsed else data
            return ChatStreamEvent(event_type=event_type, error=err_msg, raw_data=data)

        case "finish":
            return ChatStreamEvent(
                event_type=event_type,
                usage=parsed.get("usage") if parsed else None,
                raw_data=data,
            )

        case "terminate":
            return ChatStreamEvent(
                event_type=event_type,
                terminate_reason=parsed.get("reason") if parsed else None,
                terminate_message=parsed.get("message") if parsed else None,
                raw_data=data,
            )

        case "[DONE]":
            return ChatStreamEvent(event_type=event_type)

        case _:
            # Unknown event type — pass through for forward compatibility
            return ChatStreamEvent(event_type=event_type, raw_data=data)


# ---------------------------------------------------------------------------
# Synchronous stream
# ---------------------------------------------------------------------------


class ChatStream:
    """Synchronous iterator over SSE chat response chunks.

    Supports both v1 (text-only) and v2 (typed events) iteration:

    v1 (backward-compatible)::

        for chunk in stream:
            print(chunk, end="", flush=True)

    v2 (typed events)::

        for event in stream.events():
            if event.event_type == "text-delta":
                print(event.text, end="")
            elif event.event_type == "terminate":
                print(f"Stream closed: {event.terminate_reason}")
    """

    def __init__(self, response: httpx.Response) -> None:
        """Wrap an httpx streaming response for SSE chunk parsing.

        Extracts ``x-message-id`` from response headers for message correlation.
        """
        self._response = response
        self._text_chunks: list[str] = []
        self._events: list[ChatStreamEvent] = []
        self._done = False
        self._cancelled = False
        self._consumed = False
        self._message_id = response.headers.get("x-message-id")

    @property
    def message_id(self) -> Optional[str]:
        """Server-assigned message ID from the ``x-message-id`` response header."""
        return self._message_id

    def __iter__(self) -> Iterator[str]:
        """Iterate text chunks (backward-compatible v1 API)."""
        try:
            for line in self._response.iter_lines():
                if self._cancelled:
                    break

                parsed = _parse_sse_line(line)
                if parsed is None:
                    continue

                prefix, data = parsed

                if prefix == "0":
                    text = _unquote_text(data)
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
            self._consumed = True
            self._response.close()

    def events(self) -> Iterator[ChatStreamEvent]:
        """Iterate typed events (v2 API).

        Yields ``ChatStreamEvent`` objects for each SSE event. Handles both
        v1 prefix format (``0:``, ``e:``, ``d:``) and v2 SSE format
        (``event: text-delta`` / ``data: {...}``).
        """
        current_event_type: str | None = None

        try:
            for line in self._response.iter_lines():
                if self._cancelled:
                    break

                parsed = _parse_sse_line(line)
                if parsed is None:
                    continue

                prefix, data = parsed

                # v2 SSE: "event: <type>" followed by "data: <payload>"
                if prefix == "event":
                    current_event_type = data.strip()
                    continue

                if prefix == "data" and current_event_type:
                    event = _build_event(current_event_type, data)
                    self._events.append(event)
                    if event.event_type == "text-delta" and event.text:
                        self._text_chunks.append(event.text)
                    current_event_type = None
                    yield event
                    continue

                # v1 prefix format fallback
                if prefix == "0":
                    text = _unquote_text(data)
                    event = ChatStreamEvent(event_type="text-delta", text=text)
                    self._text_chunks.append(text)
                    self._events.append(event)
                    yield event

                elif prefix == "e":
                    event = ChatStreamEvent(event_type="error", error=data, raw_data=data)
                    self._events.append(event)
                    yield event
                    raise StreamError(f"Stream error: {data}")

                elif prefix == "d":
                    event = ChatStreamEvent(event_type="[DONE]")
                    self._events.append(event)
                    self._done = True
                    yield event
                    break

        except httpx.ReadTimeout as exc:
            raise StreamTimeoutError(
                "Stream timed out waiting for data"
            ) from exc
        finally:
            self._consumed = True
            self._response.close()

    def text(self) -> str:
        """Consume the entire stream and return the full text."""
        if not self._text_chunks and not self._consumed:
            for _ in self:
                pass
        return "".join(self._text_chunks)

    def _signal_cancel(self) -> None:
        """Signal-safe cancel — set flag and close, but do NOT raise.

        Safe to call from signal handlers (e.g. SIGINT). The iteration loop
        checks ``self._cancelled`` and exits cleanly.
        """
        self._cancelled = True
        self._response.close()

    def cancel(self) -> None:
        """Cancel the stream (user-callable path).

        Raises ``StreamCancelledError`` so callers outside signal handlers
        get an explicit exception.
        """
        self._signal_cancel()
        raise StreamCancelledError("Stream cancelled by client")


# ---------------------------------------------------------------------------
# Asynchronous stream
# ---------------------------------------------------------------------------


class AsyncChatStream:
    """Asynchronous iterator over SSE chat response chunks.

    Supports both v1 (text-only) and v2 (typed events) iteration:

    v1::

        async for chunk in stream:
            print(chunk, end="", flush=True)

    v2::

        async for event in stream.events():
            if event.event_type == "text-delta":
                print(event.text, end="")
    """

    def __init__(self, response: httpx.Response) -> None:
        """Wrap an httpx streaming response for SSE chunk parsing.

        Extracts ``x-message-id`` from response headers for message correlation.
        """
        self._response = response
        self._text_chunks: list[str] = []
        self._events: list[ChatStreamEvent] = []
        self._done = False
        self._cancelled = False
        self._consumed = False
        self._message_id = response.headers.get("x-message-id")

    @property
    def message_id(self) -> Optional[str]:
        """Server-assigned message ID from the ``x-message-id`` response header."""
        return self._message_id

    async def __aiter__(self):  # type: ignore[override]
        """Iterate text chunks (backward-compatible v1 API)."""
        try:
            async for line in self._response.aiter_lines():
                if self._cancelled:
                    break

                parsed = _parse_sse_line(line)
                if parsed is None:
                    continue

                prefix, data = parsed

                if prefix == "0":
                    text = _unquote_text(data)
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
            self._consumed = True
            await self._response.aclose()

    async def events(self):  # type: ignore[override]
        """Iterate typed events (v2 API).

        Yields ``ChatStreamEvent`` objects for each SSE event.
        """
        current_event_type: str | None = None

        try:
            async for line in self._response.aiter_lines():
                if self._cancelled:
                    break

                parsed = _parse_sse_line(line)
                if parsed is None:
                    continue

                prefix, data = parsed

                if prefix == "event":
                    current_event_type = data.strip()
                    continue

                if prefix == "data" and current_event_type:
                    event = _build_event(current_event_type, data)
                    self._events.append(event)
                    if event.event_type == "text-delta" and event.text:
                        self._text_chunks.append(event.text)
                    current_event_type = None
                    yield event
                    continue

                # v1 prefix format fallback
                if prefix == "0":
                    text = _unquote_text(data)
                    event = ChatStreamEvent(event_type="text-delta", text=text)
                    self._text_chunks.append(text)
                    self._events.append(event)
                    yield event

                elif prefix == "e":
                    event = ChatStreamEvent(event_type="error", error=data, raw_data=data)
                    self._events.append(event)
                    yield event
                    raise StreamError(f"Stream error: {data}")

                elif prefix == "d":
                    event = ChatStreamEvent(event_type="[DONE]")
                    self._events.append(event)
                    self._done = True
                    yield event
                    break

        except httpx.ReadTimeout as exc:
            raise StreamTimeoutError(
                "Stream timed out waiting for data"
            ) from exc
        finally:
            self._consumed = True
            await self._response.aclose()

    async def text(self) -> str:
        """Consume the entire stream and return the full text."""
        if not self._text_chunks and not self._consumed:
            async for _ in self:
                pass
        return "".join(self._text_chunks)

    def _signal_cancel(self) -> None:
        """Signal-safe cancel — set flag and close, but do NOT raise.

        Note: uses synchronous close even on the async stream because signal
        handlers cannot be async. The httpx response handles this gracefully.
        """
        self._cancelled = True
        self._response.close()

    async def cancel(self) -> None:
        """Cancel the stream and close the response. Always raises ``StreamCancelledError``."""
        self._cancelled = True
        await self._response.aclose()
        raise StreamCancelledError("Stream cancelled by client")
