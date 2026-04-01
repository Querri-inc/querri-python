"""Tests for SSE streaming."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from querri._streaming import ChatStream, _parse_sse_line
from querri._exceptions import StreamError, StreamCancelledError


class TestParseSSELine:
    """Test the SSE line parser."""

    def test_empty_line(self):
        assert _parse_sse_line("") is None

    def test_whitespace_only(self):
        assert _parse_sse_line("   ") is None

    def test_comment_line(self):
        assert _parse_sse_line(": comment") is None

    def test_vercel_text_chunk(self):
        result = _parse_sse_line('0:"hello"')
        assert result == ("0", '"hello"')

    def test_vercel_error_event(self):
        result = _parse_sse_line("e:some error")
        assert result == ("e", "some error")

    def test_vercel_done_signal(self):
        result = _parse_sse_line("d:done")
        assert result == ("d", "done")

    def test_standard_sse_data(self):
        result = _parse_sse_line("data: hello world")
        assert result == ("data", "hello world")

    def test_unparseable_line(self):
        assert _parse_sse_line("random garbage without colon at pos 1") is None

    def test_single_char_line(self):
        assert _parse_sse_line("x") is None


class TestChatStream:
    """Test the ChatStream iterator."""

    def _make_response(self, lines: list[str], headers: dict[str, str] | None = None) -> httpx.Response:
        """Create a mock response that yields lines."""
        response = MagicMock(spec=httpx.Response)
        response.headers = headers or {}
        response.iter_lines.return_value = iter(lines)
        response.close = MagicMock()
        return response

    def test_text_chunks(self):
        response = self._make_response([
            '0:"Hello"',
            '0:" world"',
            'd:done',
        ])
        stream = ChatStream(response)
        chunks = list(stream)
        assert chunks == ["Hello", " world"]

    def test_text_method(self):
        response = self._make_response([
            '0:"Hello"',
            '0:" world"',
            'd:done',
        ])
        stream = ChatStream(response)
        assert stream.text() == "Hello world"

    def test_newline_unescaping(self):
        """Verify that escaped \\n sequences in SSE text chunks are unescaped to real newlines."""
        response = self._make_response([
            '0:"line1\\nline2"',
            'd:done',
        ])
        stream = ChatStream(response)
        chunks = list(stream)
        assert chunks == ["line1\nline2"]

    def test_quote_unescaping(self):
        """Verify that escaped quotes inside SSE text chunks are unescaped."""
        response = self._make_response([
            '0:"say \\"hi\\""',
            'd:done',
        ])
        stream = ChatStream(response)
        chunks = list(stream)
        assert chunks == ['say "hi"']

    def test_backslash_unescaping(self):
        """Verify that double-escaped backslashes are reduced to single backslashes."""
        response = self._make_response([
            '0:"path\\\\to\\\\file"',
            'd:done',
        ])
        stream = ChatStream(response)
        chunks = list(stream)
        assert chunks == ["path\\to\\file"]

    def test_error_event_raises(self):
        """Verify that an 'e:' SSE event raises StreamError with the error message."""
        response = self._make_response([
            '0:"partial"',
            'e:something went wrong',
        ])
        stream = ChatStream(response)
        with pytest.raises(StreamError, match="something went wrong"):
            list(stream)

    def test_done_signal_stops_iteration(self):
        """Verify that a 'd:' done signal stops iteration, ignoring subsequent chunks."""
        response = self._make_response([
            '0:"a"',
            'd:done',
            '0:"should not appear"',
        ])
        stream = ChatStream(response)
        chunks = list(stream)
        assert chunks == ["a"]

    def test_empty_lines_and_comments_skipped(self):
        response = self._make_response([
            '',
            ': keep-alive',
            '0:"data"',
            '',
            'd:done',
        ])
        stream = ChatStream(response)
        chunks = list(stream)
        assert chunks == ["data"]

    def test_message_id_from_header(self):
        response = self._make_response(
            ['d:done'],
            headers={"x-message-id": "msg_abc123"},
        )
        stream = ChatStream(response)
        assert stream.message_id == "msg_abc123"

    def test_message_id_none_when_missing(self):
        response = self._make_response(['d:done'])
        stream = ChatStream(response)
        assert stream.message_id is None

    def test_response_closed_after_iteration(self):
        """Verify that the underlying HTTP response is closed when iteration completes."""
        response = self._make_response(['d:done'])
        stream = ChatStream(response)
        list(stream)
        response.close.assert_called_once()

    def test_cancel(self):
        """Verify that cancel() closes the response and raises StreamCancelledError."""
        response = self._make_response([
            '0:"chunk1"',
            '0:"chunk2"',
        ])
        stream = ChatStream(response)
        with pytest.raises(StreamCancelledError):
            stream.cancel()
        response.close.assert_called_once()

    def test_unquoted_text_chunk(self):
        """Verify that text chunks without surrounding quotes are passed through as-is."""
        response = self._make_response([
            '0:raw text without quotes',
            'd:done',
        ])
        stream = ChatStream(response)
        chunks = list(stream)
        assert chunks == ["raw text without quotes"]
