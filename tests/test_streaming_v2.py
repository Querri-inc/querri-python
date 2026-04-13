"""Tests for v2 SSE streaming with typed ChatStreamEvent.

Tests the events() method, all v0.2.0 event types, backward compatibility,
error cases, and forward compatibility with unknown event types.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from querri._exceptions import StreamError
from querri._streaming import (
    ChatStream,
    ChatStreamEvent,
    _build_event,
    _parse_sse_line,
    _unquote_text,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(lines: list[str], headers: dict[str, str] | None = None) -> httpx.Response:
    """Create a mock response that yields lines."""
    response = MagicMock(spec=httpx.Response)
    response.headers = headers or {}
    response.iter_lines.return_value = iter(lines)
    response.close = MagicMock()
    return response


# ---------------------------------------------------------------------------
# SSE line parser — v2 extensions
# ---------------------------------------------------------------------------


class TestParseSSELineV2:
    """Test v2 SSE line parsing additions."""

    def test_event_type_line(self):
        result = _parse_sse_line("event: text-delta")
        assert result == ("event", "text-delta")

    def test_event_type_with_extra_spaces(self):
        result = _parse_sse_line("event:  finish ")
        assert result == ("event", " finish")

    def test_data_line(self):
        result = _parse_sse_line('data: {"textDelta": "hello"}')
        assert result == ("data", '{"textDelta": "hello"}')


# ---------------------------------------------------------------------------
# _unquote_text
# ---------------------------------------------------------------------------


class TestUnquoteText:
    def test_quoted_string(self):
        assert _unquote_text('"hello"') == "hello"

    def test_unquoted_string(self):
        assert _unquote_text("hello") == "hello"

    def test_newline_escape(self):
        assert _unquote_text('"line1\\nline2"') == "line1\nline2"

    def test_quote_escape(self):
        assert _unquote_text('"say \\"hi\\""') == 'say "hi"'

    def test_backslash_escape(self):
        assert _unquote_text('"a\\\\b"') == "a\\b"


# ---------------------------------------------------------------------------
# _build_event
# ---------------------------------------------------------------------------


class TestBuildEvent:
    def test_text_delta_json(self):
        event = _build_event("text-delta", '{"textDelta": "hello"}')
        assert event.event_type == "text-delta"
        assert event.text == "hello"

    def test_text_delta_raw(self):
        event = _build_event("text-delta", '"hello world"')
        assert event.event_type == "text-delta"
        assert event.text == "hello world"

    def test_tool_output_available(self):
        event = _build_event(
            "tool-output-available",
            '{"toolName": "query_data", "output": {"rows": 42}}'
        )
        assert event.event_type == "tool-output-available"
        assert event.tool_name == "query_data"
        assert event.tool_data == {"rows": 42}

    def test_file_event(self):
        event = _build_event(
            "file",
            '{"url": "https://example.com/chart.png", "mediaType": "image/png"}'
        )
        assert event.event_type == "file"
        assert event.file_url == "https://example.com/chart.png"
        assert event.media_type == "image/png"

    def test_error_event(self):
        event = _build_event("error", '{"message": "Rate limited"}')
        assert event.event_type == "error"
        assert event.error == "Rate limited"

    def test_error_event_raw_string(self):
        event = _build_event("error", "something broke")
        assert event.error == "something broke"

    def test_finish_event(self):
        event = _build_event(
            "finish",
            '{"usage": {"credits_used": 5, "tokens_used": 1200}}'
        )
        assert event.event_type == "finish"
        assert event.usage == {"credits_used": 5, "tokens_used": 1200}

    def test_terminate_event(self):
        event = _build_event(
            "terminate",
            '{"reason": "session_timeout", "message": "Session expired"}'
        )
        assert event.event_type == "terminate"
        assert event.terminate_reason == "session_timeout"
        assert event.terminate_message == "Session expired"

    def test_done_event(self):
        event = _build_event("[DONE]", "")
        assert event.event_type == "[DONE]"

    def test_unknown_event_passes_through(self):
        event = _build_event("some-future-event", '{"data": "stuff"}')
        assert event.event_type == "some-future-event"
        assert event.raw_data == '{"data": "stuff"}'
        assert event.text is None
        assert event.error is None

    def test_reasoning_delta_event(self):
        event = _build_event("reasoning-delta", '{"delta": "thinking..."}')
        assert event.event_type == "reasoning-delta"
        assert event.reasoning_text == "thinking..."
        assert event.text is None

    def test_reasoning_start_end(self):
        start = _build_event("reasoning-start", "")
        assert start.event_type == "reasoning-start"
        end = _build_event("reasoning-end", "")
        assert end.event_type == "reasoning-end"


# ---------------------------------------------------------------------------
# ChatStream.events() — v2 SSE format
# ---------------------------------------------------------------------------


class TestChatStreamEvents:
    """Test the events() iterator with v2 SSE format."""

    def test_v2_text_delta_events(self):
        response = _make_response([
            "event: text-delta",
            'data: {"textDelta": "Hello"}',
            "",
            "event: text-delta",
            'data: {"textDelta": " world"}',
            "",
            "event: finish",
            'data: {"usage": {"credits_used": 1}}',
        ])
        stream = ChatStream(response)
        events = list(stream.events())

        assert len(events) == 3
        assert events[0].event_type == "text-delta"
        assert events[0].text == "Hello"
        assert events[1].event_type == "text-delta"
        assert events[1].text == " world"
        assert events[2].event_type == "finish"
        assert events[2].usage == {"credits_used": 1}

    def test_v2_text_accumulates(self):
        response = _make_response([
            "event: text-delta",
            'data: {"textDelta": "Hello"}',
            "",
            "event: text-delta",
            'data: {"textDelta": " world"}',
        ])
        stream = ChatStream(response)
        list(stream.events())  # consume
        assert stream.text() == "Hello world"

    def test_v2_tool_output(self):
        response = _make_response([
            "event: text-delta",
            'data: {"textDelta": "Analyzing..."}',
            "",
            "event: tool-output-available",
            'data: {"toolName": "query", "output": {"rows": 10}}',
        ])
        stream = ChatStream(response)
        events = list(stream.events())

        assert events[1].event_type == "tool-output-available"
        assert events[1].tool_name == "query"

    def test_v2_file_event(self):
        response = _make_response([
            "event: file",
            'data: {"url": "https://x.com/chart.png", "mediaType": "image/png"}',
        ])
        stream = ChatStream(response)
        events = list(stream.events())

        assert events[0].event_type == "file"
        assert events[0].file_url == "https://x.com/chart.png"

    def test_v2_error_event_yielded(self):
        """v2 error events are yielded (not raised); callers decide how to handle."""
        response = _make_response([
            "event: text-delta",
            'data: {"textDelta": "partial"}',
            "",
            "event: error",
            'data: {"message": "Internal error"}',
        ])
        stream = ChatStream(response)
        events = list(stream.events())

        assert len(events) == 2
        assert events[1].event_type == "error"
        assert events[1].error == "Internal error"

    def test_v2_terminate_event(self):
        response = _make_response([
            "event: text-delta",
            'data: {"textDelta": "Hello"}',
            "",
            "event: terminate",
            'data: {"reason": "session_timeout", "message": "Session expired"}',
        ])
        stream = ChatStream(response)
        events = list(stream.events())

        assert events[1].event_type == "terminate"
        assert events[1].terminate_reason == "session_timeout"
        assert events[1].terminate_message == "Session expired"

    def test_v2_reasoning_events(self):
        """Reasoning events are parsed with reasoning_text field."""
        response = _make_response([
            "event: text-delta",
            'data: {"textDelta": "Hi"}',
            "",
            "event: reasoning-delta",
            'data: {"delta": "thinking..."}',
            "",
            "event: text-delta",
            'data: {"textDelta": "!"}',
        ])
        stream = ChatStream(response)
        events = list(stream.events())

        assert len(events) == 3
        assert events[0].event_type == "text-delta"
        assert events[1].event_type == "reasoning-delta"
        assert events[1].reasoning_text == "thinking..."
        assert events[2].event_type == "text-delta"

    def test_v2_unknown_event_ignored(self):
        """Unknown event types pass through without error (forward compat)."""
        response = _make_response([
            "event: text-delta",
            'data: {"textDelta": "Hi"}',
            "",
            "event: some-future-event",
            'data: {"foo": "bar"}',
            "",
            "event: text-delta",
            'data: {"textDelta": "!"}',
        ])
        stream = ChatStream(response)
        events = list(stream.events())

        assert len(events) == 3
        assert events[0].event_type == "text-delta"
        assert events[1].event_type == "some-future-event"
        assert events[1].raw_data == '{"foo": "bar"}'
        assert events[2].event_type == "text-delta"


# ---------------------------------------------------------------------------
# ChatStream.events() — v1 format fallback
# ---------------------------------------------------------------------------


class TestChatStreamEventsV1Fallback:
    """Test that events() also handles v1 prefix format."""

    def test_v1_text_as_events(self):
        response = _make_response([
            '0:"Hello"',
            '0:" world"',
            'd:done',
        ])
        stream = ChatStream(response)
        events = list(stream.events())

        assert len(events) == 3
        assert events[0].event_type == "text-delta"
        assert events[0].text == "Hello"
        assert events[1].event_type == "text-delta"
        assert events[1].text == " world"
        assert events[2].event_type == "[DONE]"

    def test_v1_error_as_event(self):
        response = _make_response([
            'e:something broke',
        ])
        stream = ChatStream(response)
        with pytest.raises(StreamError, match="something broke"):
            list(stream.events())

    def test_v1_text_accumulates_via_events(self):
        response = _make_response([
            '0:"Hello"',
            '0:" world"',
            'd:done',
        ])
        stream = ChatStream(response)
        list(stream.events())
        assert stream.text() == "Hello world"


# ---------------------------------------------------------------------------
# Backward compatibility: __iter__ still works
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    """Verify that the old __iter__ API still works after v2 changes."""

    def test_iter_yields_text(self):
        response = _make_response([
            '0:"Hello"',
            '0:" world"',
            'd:done',
        ])
        stream = ChatStream(response)
        chunks = list(stream)
        assert chunks == ["Hello", " world"]

    def test_text_method(self):
        response = _make_response([
            '0:"Hello"',
            '0:" world"',
            'd:done',
        ])
        stream = ChatStream(response)
        assert stream.text() == "Hello world"

    def test_message_id(self):
        response = _make_response(
            ['d:done'],
            headers={"x-message-id": "msg_123"},
        )
        stream = ChatStream(response)
        assert stream.message_id == "msg_123"

    def test_response_closed(self):
        response = _make_response(['d:done'])
        stream = ChatStream(response)
        list(stream)
        response.close.assert_called_once()


# ---------------------------------------------------------------------------
# ChatStreamEvent dataclass
# ---------------------------------------------------------------------------


class TestChatStreamEvent:
    def test_default_fields(self):
        event = ChatStreamEvent(event_type="text-delta", text="hi")
        assert event.event_type == "text-delta"
        assert event.text == "hi"
        assert event.tool_name is None
        assert event.error is None
        assert event.usage is None

    def test_all_fields(self):
        event = ChatStreamEvent(
            event_type="terminate",
            terminate_reason="session_timeout",
            terminate_message="Session expired",
            raw_data='{"reason": "session_timeout"}',
        )
        assert event.terminate_reason == "session_timeout"
        assert event.terminate_message == "Session expired"


# ---------------------------------------------------------------------------
# Mixed v1/v2 format (edge case)
# ---------------------------------------------------------------------------


class TestMixedFormat:
    """Test streams that mix v1 and v2 format."""

    def test_v1_then_v2(self):
        """A stream that starts with v1 format then switches to v2."""
        response = _make_response([
            '0:"Hello"',
            "",
            "event: text-delta",
            'data: {"textDelta": " world"}',
            "",
            'd:done',
        ])
        stream = ChatStream(response)
        events = list(stream.events())

        # v1 text, v2 text, v1 done
        assert events[0].event_type == "text-delta"
        assert events[0].text == "Hello"
        assert events[1].event_type == "text-delta"
        assert events[1].text == " world"
        assert events[2].event_type == "[DONE]"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_stream(self):
        response = _make_response([])
        stream = ChatStream(response)
        events = list(stream.events())
        assert events == []

    def test_only_comments_and_blanks(self):
        response = _make_response([
            "",
            ": keepalive",
            "",
            ": another comment",
        ])
        stream = ChatStream(response)
        events = list(stream.events())
        assert events == []

    def test_malformed_json_in_data(self):
        """Malformed JSON should not crash — event passes through with raw_data."""
        response = _make_response([
            "event: text-delta",
            "data: {this is not json}",
        ])
        stream = ChatStream(response)
        events = list(stream.events())

        assert len(events) == 1
        assert events[0].event_type == "text-delta"
        # Falls back to raw unquoting since JSON parse fails
        assert events[0].text == "{this is not json}"

    def test_event_without_data_is_ignored(self):
        """An event: line not followed by data: line gets discarded."""
        response = _make_response([
            "event: text-delta",
            "",  # blank line, no data follows
            "event: finish",
            'data: {"usage": {}}',
        ])
        stream = ChatStream(response)
        events = list(stream.events())

        # The first text-delta had no data, so current_event_type was reset
        # when the second event: line was parsed. Only finish yields.
        assert len(events) == 1
        assert events[0].event_type == "finish"
