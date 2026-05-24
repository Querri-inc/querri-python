"""WS-D6.1 — Streaming-method coverage for Library.chat_stream / .chat.

Closes the deferred half of WS-D6. The chat_stream method at
`querri/resources/library.py:261-289` (sync) + `:549-572` (async) wasn't
covered in D6 because respx doesn't have a clean streaming-fixture
pattern in the existing SDK test suite. This file builds the pattern.

## What chat_stream actually does (4 testable paths)

```python
with self._http._client.stream("POST", "/library/chat", json=body) as response:
    response.raise_for_status()
    for line in response.iter_lines():
        if not line or not line.startswith("data: "):
            continue
        payload = line[len("data: "):]
        if payload == "[DONE]":
            break
        try:
            yield json.loads(payload)
        except json.JSONDecodeError:
            continue
```

Four behaviors to pin:
1. POST body construction (chat_id optional).
2. Lines without `data: ` prefix are filtered out (heartbeats, comments).
3. `[DONE]` sentinel breaks iteration.
4. Malformed JSON lines are swallowed silently (don't crash the stream).

Plus the `.chat()` drain → ChatResponse construction.

## Why not respx-streaming

`respx` mocks HTTP at the transport layer, but `httpx.Client.stream` uses
a different code path than `Client.get/post` that respx's streaming
support has incomplete coverage for at the version pinned in this repo.
Cleaner path for SDK testing is to patch `_http._client.stream` directly
with a mock context manager — same level as the existing `test_streaming.py`
pattern (MagicMock(spec=httpx.Response) + iter_lines.return_value).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from querri._base_client import AsyncHTTPClient, SyncHTTPClient
from querri._config import ClientConfig
from querri.resources.library import AsyncLibrary, Library

BASE = "https://test.querri.com/api/v1"


def _make_config() -> ClientConfig:
    return ClientConfig(
        api_key="qk_test", org_id="org_test", base_url=BASE,
        timeout=10.0, max_retries=0,
    )


# ── Mock helpers ──────────────────────────────────────────────────────────


def _sse(payload: dict | str) -> str:
    """Build one SSE-shaped data line (no trailing newline — iter_lines splits)."""
    if isinstance(payload, dict):
        import json
        return f"data: {json.dumps(payload)}"
    return f"data: {payload}"


def _mock_sync_stream_response(lines: list[str]):
    """Mock the sync `client.stream(...)` context manager returning a
    response whose `.iter_lines()` yields the canned lines."""
    response = MagicMock(spec=httpx.Response)
    response.headers = {"content-type": "text/event-stream"}
    response.iter_lines.return_value = iter(lines)
    response.raise_for_status = MagicMock()
    # The `with client.stream(...) as response:` shape: stream() returns
    # a context manager whose __enter__ yields response.
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=response)
    cm.__exit__ = MagicMock(return_value=None)
    return cm, response


def _mock_async_stream_response(lines: list[str]):
    """Async equivalent: aiter_lines() yields canned lines."""
    response = MagicMock(spec=httpx.Response)
    response.headers = {"content-type": "text/event-stream"}

    async def _aiter():
        for line in lines:
            yield line

    response.aiter_lines = MagicMock(return_value=_aiter())
    response.raise_for_status = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm, response


# ── Sync: chat_stream behavior ────────────────────────────────────────────


def test_sync_chat_stream_yields_parsed_events():
    """Happy path: 3 SSE events + [DONE]. Yields 3 parsed dicts."""
    lines = [
        _sse({"type": "tool_use", "name": "search_graph"}),
        _sse({"type": "tool_result", "name": "search_graph", "result": {}}),
        _sse({"type": "done", "chat_id": "libchat_xyz", "assistant_message": "ok"}),
        "data: [DONE]",
    ]
    cm, _resp = _mock_sync_stream_response(lines)

    lib = Library(SyncHTTPClient(_make_config()))
    lib._http._client.stream = MagicMock(return_value=cm)

    events = list(lib.chat_stream(library_id="lib_x", message="hi"))
    assert len(events) == 3
    assert events[0]["type"] == "tool_use"
    assert events[1]["type"] == "tool_result"
    assert events[2]["type"] == "done"
    assert events[2]["chat_id"] == "libchat_xyz"


def test_sync_chat_stream_skips_non_data_lines():
    """Heartbeats / comments / empty lines that don't start with `data: ` are
    silently filtered. Pins the prefix-check at resources/library.py:281."""
    lines = [
        "",
        ": heartbeat",
        "event: foo",
        _sse({"type": "tool_use", "name": "search_graph"}),
        "data: [DONE]",
    ]
    cm, _resp = _mock_sync_stream_response(lines)

    lib = Library(SyncHTTPClient(_make_config()))
    lib._http._client.stream = MagicMock(return_value=cm)

    events = list(lib.chat_stream(library_id="lib_x", message="hi"))
    assert len(events) == 1
    assert events[0]["type"] == "tool_use"


def test_sync_chat_stream_done_sentinel_breaks_iteration():
    """`data: [DONE]` ends the stream even if more lines follow. Pins the
    break at resources/library.py:285."""
    lines = [
        _sse({"type": "tool_use", "name": "search_graph"}),
        "data: [DONE]",
        _sse({"type": "tool_use", "name": "should_not_appear"}),
    ]
    cm, _resp = _mock_sync_stream_response(lines)

    lib = Library(SyncHTTPClient(_make_config()))
    lib._http._client.stream = MagicMock(return_value=cm)

    events = list(lib.chat_stream(library_id="lib_x", message="hi"))
    assert len(events) == 1
    assert events[0]["name"] == "search_graph"


def test_sync_chat_stream_swallows_malformed_json_lines():
    """A malformed JSON payload is logged-or-silently-skipped, not raised.
    Pins the try/except at resources/library.py:286-289 — protects the
    stream consumer from a single bad event killing the iteration."""
    lines = [
        _sse({"type": "tool_use", "name": "search_graph"}),
        "data: {not valid json",  # malformed
        _sse({"type": "done", "chat_id": "libchat_xyz", "assistant_message": "ok"}),
        "data: [DONE]",
    ]
    cm, _resp = _mock_sync_stream_response(lines)

    lib = Library(SyncHTTPClient(_make_config()))
    lib._http._client.stream = MagicMock(return_value=cm)

    events = list(lib.chat_stream(library_id="lib_x", message="hi"))
    # 2 events (malformed swallowed), not 3.
    assert len(events) == 2
    assert events[1]["type"] == "done"


def test_sync_chat_stream_includes_chat_id_in_body_when_provided():
    """When `chat_id` is supplied, body carries it; otherwise omitted.
    Pins the body construction at resources/library.py:272-274."""
    cm, _ = _mock_sync_stream_response(["data: [DONE]"])
    lib = Library(SyncHTTPClient(_make_config()))
    spy = MagicMock(return_value=cm)
    lib._http._client.stream = spy

    list(lib.chat_stream(
        library_id="lib_x", message="hi", chat_id="libchat_existing",
    ))
    sent_json = spy.call_args.kwargs["json"]
    assert sent_json["chat_id"] == "libchat_existing"
    assert sent_json["library_id"] == "lib_x"
    assert sent_json["message"] == "hi"


def test_sync_chat_stream_omits_chat_id_when_not_provided():
    cm, _ = _mock_sync_stream_response(["data: [DONE]"])
    lib = Library(SyncHTTPClient(_make_config()))
    spy = MagicMock(return_value=cm)
    lib._http._client.stream = spy

    list(lib.chat_stream(library_id="lib_x", message="hi"))
    sent_json = spy.call_args.kwargs["json"]
    assert "chat_id" not in sent_json


# ── Sync: chat() drain → ChatResponse construction ────────────────────────


def test_sync_chat_drains_stream_into_chat_response():
    """`chat()` consumes the stream + builds a ChatResponse from the done
    event. Pins the drain at resources/library.py:300-329."""
    lines = [
        _sse({
            "type": "tool_result",
            "name": "search_graph",
            "input": {"query": "x"},
            "result": {"focal_nodes": []},
            "duration_ms": 123,
        }),
        _sse({
            "type": "done",
            "chat_id": "libchat_xyz",
            "library_id": "lib_x",
            "assistant_message": "Final answer",
            "turns_used": 2,
            "stop_reason": "end_turn",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_ms": 1234,
        }),
        "data: [DONE]",
    ]
    cm, _ = _mock_sync_stream_response(lines)
    lib = Library(SyncHTTPClient(_make_config()))
    lib._http._client.stream = MagicMock(return_value=cm)

    result = lib.chat(library_id="lib_x", message="hi")
    assert result.chat_id == "libchat_xyz"
    assert result.assistant_message == "Final answer"
    assert result.turns_used == 2
    assert result.stop_reason == "end_turn"
    assert len(result.tool_calls) == 1
    # tool_calls items are ChatToolCall objects (attr access), not dicts.
    assert result.tool_calls[0].name == "search_graph"
    assert result.tool_calls[0].duration_ms == 123


# ── Async parity (3 mirror tests) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_chat_stream_yields_parsed_events():
    lines = [
        _sse({"type": "tool_use", "name": "search_graph"}),
        _sse({"type": "done", "chat_id": "libchat_xyz", "assistant_message": "ok"}),
        "data: [DONE]",
    ]
    cm, _resp = _mock_async_stream_response(lines)

    lib = AsyncLibrary(AsyncHTTPClient(_make_config()))
    lib._http._client.stream = MagicMock(return_value=cm)

    events = [ev async for ev in lib.chat_stream(library_id="lib_x", message="hi")]
    assert len(events) == 2
    assert events[0]["type"] == "tool_use"
    assert events[1]["type"] == "done"


@pytest.mark.asyncio
async def test_async_chat_stream_done_sentinel_breaks():
    lines = [
        _sse({"type": "tool_use", "name": "search_graph"}),
        "data: [DONE]",
        _sse({"type": "should_not_appear"}),
    ]
    cm, _ = _mock_async_stream_response(lines)
    lib = AsyncLibrary(AsyncHTTPClient(_make_config()))
    lib._http._client.stream = MagicMock(return_value=cm)

    events = [ev async for ev in lib.chat_stream(library_id="lib_x", message="hi")]
    assert len(events) == 1


@pytest.mark.asyncio
async def test_async_chat_drains_into_chat_response():
    lines = [
        _sse({
            "type": "done",
            "chat_id": "libchat_xyz",
            "library_id": "lib_x",
            "assistant_message": "async answer",
            "turns_used": 1,
            "stop_reason": "end_turn",
        }),
        "data: [DONE]",
    ]
    cm, _ = _mock_async_stream_response(lines)
    lib = AsyncLibrary(AsyncHTTPClient(_make_config()))
    lib._http._client.stream = MagicMock(return_value=cm)

    result = await lib.chat(library_id="lib_x", message="hi")
    assert result.chat_id == "libchat_xyz"
    assert result.assistant_message == "async answer"
    assert result.stop_reason == "end_turn"
