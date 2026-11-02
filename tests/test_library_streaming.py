"""Library SSE streams — chat_stream / chat / build_view_stream.

Mocked at the transport (respx), not at ``httpx.Client.stream``: the streams go
through ``SyncHTTPClient.request(stream=True)`` so they share token renewal and
typed error parsing with every other call, and a test that patched the httpx
layer directly would skip exactly the code under test.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from querri._base_client import AsyncHTTPClient, SyncHTTPClient
from querri._config import ClientConfig
from querri._exceptions import NotFoundError, ValidationError
from querri.resources.library import AsyncLibrary, Library, choice_label

BASE = "https://test.querri.com/api/v1"
CHAT_URL = f"{BASE}/library/chat"


def _make_config(**overrides: object) -> ClientConfig:
    cfg: dict[str, object] = dict(
        api_key="qk_test", org_id="org_test", base_url=BASE,
        timeout=10.0, max_retries=0,
    )
    cfg.update(overrides)
    return ClientConfig(**cfg)  # type: ignore[arg-type]


def _sse(payload: dict | str) -> str:
    if isinstance(payload, dict):
        return f"data: {json.dumps(payload)}"
    return f"data: {payload}"


def _stream(lines: list[str]) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content="\n".join(lines).encode(),
    )


# ── chat_stream parsing ───────────────────────────────────────────────────


@respx.mock
def test_sync_chat_stream_yields_parsed_events() -> None:
    respx.post(CHAT_URL).mock(return_value=_stream([
        _sse({"type": "tool_use", "name": "search_graph"}),
        _sse({"type": "tool_result", "name": "search_graph", "result": {}}),
        _sse({"type": "done", "chat_id": "libchat_xyz"}),
        "data: [DONE]",
    ]))
    lib = Library(SyncHTTPClient(_make_config()))
    events = list(lib.chat_stream(library_id="lib_x", message="hi"))
    assert [e["type"] for e in events] == ["tool_use", "tool_result", "done"]


@respx.mock
def test_sync_chat_stream_skips_non_data_and_malformed_lines() -> None:
    respx.post(CHAT_URL).mock(return_value=_stream([
        "",
        ": heartbeat",
        "event: foo",
        _sse({"type": "tool_use"}),
        "data: {not valid json",
        _sse({"type": "done"}),
        "data: [DONE]",
        _sse({"type": "should_not_appear"}),
    ]))
    lib = Library(SyncHTTPClient(_make_config()))
    events = list(lib.chat_stream(library_id="lib_x", message="hi"))
    assert [e["type"] for e in events] == ["tool_use", "done"]


@respx.mock
def test_sync_chat_stream_body_carries_chat_id_only_when_given() -> None:
    route = respx.post(CHAT_URL).mock(return_value=_stream(["data: [DONE]"]))
    lib = Library(SyncHTTPClient(_make_config()))
    list(lib.chat_stream(library_id="lib_x", message="hi", chat_id="libchat_1"))
    list(lib.chat_stream(library_id="lib_x", message="hi"))
    first = json.loads(route.calls[0].request.content)
    second = json.loads(route.calls[1].request.content)
    assert first == {
        "library_id": "lib_x", "message": "hi", "mode": "default",
        "chat_id": "libchat_1",
    }
    assert "chat_id" not in second


# ── errors and renewal (the reason streams go through request()) ──────────


@respx.mock
def test_sync_chat_stream_raises_typed_error_with_server_message() -> None:
    respx.post(CHAT_URL).mock(return_value=httpx.Response(
        422, json={"error": {"code": "invalid", "message": "message is empty"}},
    ))
    lib = Library(SyncHTTPClient(_make_config()))
    with pytest.raises(ValidationError) as exc_info:
        list(lib.chat_stream(library_id="lib_x", message=""))
    assert "message is empty" in str(exc_info.value)


@respx.mock
async def test_async_chat_stream_raises_typed_error() -> None:
    respx.post(CHAT_URL).mock(return_value=httpx.Response(
        404, json={"error": {"code": "not_found", "message": "no such library"}},
    ))
    lib = AsyncLibrary(AsyncHTTPClient(_make_config()))
    with pytest.raises(NotFoundError):
        async for _ in lib.chat_stream(library_id="lib_x", message="hi"):
            pass


@respx.mock
def test_sync_chat_stream_renews_an_expired_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stream that 401s with a store-sourced token renews it and retries."""
    import querri._base_client as base

    monkeypatch.setattr(base, "_renew_token", lambda cfg: "fresh_tok")
    route = respx.post(CHAT_URL).mock(side_effect=[
        httpx.Response(401, json={"error": {"message": "expired"}}),
        _stream([_sse({"type": "done"}), "data: [DONE]"]),
    ])
    cfg = _make_config(api_key=None, access_token="old_tok", token_profile="default")
    lib = Library(SyncHTTPClient(cfg))
    events = list(lib.chat_stream(library_id="lib_x", message="hi"))
    assert [e["type"] for e in events] == ["done"]
    assert route.calls[1].request.headers["Authorization"] == "Bearer fresh_tok"


@respx.mock
async def test_async_chat_stream_renews_an_expired_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import querri._base_client as base

    monkeypatch.setattr(base, "_renew_token", lambda cfg: "fresh_tok")
    route = respx.post(CHAT_URL).mock(side_effect=[
        httpx.Response(401, json={"error": {"message": "expired"}}),
        _stream([_sse({"type": "done"}), "data: [DONE]"]),
    ])
    cfg = _make_config(api_key=None, access_token="old_tok", token_profile="default")
    lib = AsyncLibrary(AsyncHTTPClient(cfg))
    events = [e async for e in lib.chat_stream(library_id="lib_x", message="hi")]
    assert [e["type"] for e in events] == ["done"]
    assert route.calls[1].request.headers["Authorization"] == "Bearer fresh_tok"


@respx.mock
def test_sync_build_view_stream_goes_through_request() -> None:
    url = f"{BASE}/library/collections/coll_1/views"
    route = respx.post(url).mock(return_value=_stream([
        _sse({"type": "data-view-built", "data": {"view_uuid": "v1", "status": "ok"}}),
        "data: [DONE]",
    ]))
    lib = Library(SyncHTTPClient(_make_config()))
    result = lib.build_view(collection_id="coll_1", source_node_ids=["src_1"])
    assert result == {"view_uuid": "v1", "status": "ok"}
    assert json.loads(route.calls[0].request.content) == {"source_node_ids": ["src_1"]}


@respx.mock
async def test_async_build_view_stream_raises_typed_error() -> None:
    url = f"{BASE}/library/collections/coll_1/views"
    respx.post(url).mock(return_value=httpx.Response(
        404, json={"error": {"message": "collection not found"}},
    ))
    lib = AsyncLibrary(AsyncHTTPClient(_make_config()))
    with pytest.raises(NotFoundError):
        await lib.build_view(collection_id="coll_1", source_node_ids=["src_1"])


# ── chat() drain ──────────────────────────────────────────────────────────

_CARD = {
    "presented": True,
    "question": "Build this view?",
    "options": [
        {"label": "Build the view"}, {"label": "Change the plan"},
        {"label": "Not now"},
    ],
    "multi_select": False,
    "allow_other": True,
    "review": [{"label": "View", "value": "one row per order"}],
    "confirm_label": "Build the view",
}


def _card_turn() -> list[str]:
    return [
        _sse({"type": "text-start", "id": "t1"}),
        _sse({"type": "text-delta", "id": "t1", "delta": "Orders has 4,210 rows "}),
        _sse({"type": "text-delta", "id": "t1", "delta": "and two date columns."}),
        _sse({"type": "tool-input-available", "toolCallId": "tu_1",
              "toolName": "ask_choices", "input": {"question": "Build this view?"}}),
        _sse({"type": "tool-output-available", "toolCallId": "tu_1", "output": _CARD}),
        _sse({"type": "text-delta", "id": "t2", "delta": "Shall I go ahead?"}),
        _sse({"type": "data-librarian", "data": {
            "chat_id": "libchat_xyz", "library_id": "lib_x",
            # The server's assistant_message is the LAST turn's text only.
            "assistant_message": "Shall I go ahead?",
            "turns_used": 2, "stop_reason": "end_turn",
        }}),
        _sse({"type": "finish"}),
        "data: [DONE]",
    ]


@respx.mock
def test_sync_chat_keeps_every_text_segment_and_the_card() -> None:
    respx.post(CHAT_URL).mock(return_value=_stream(_card_turn()))
    lib = Library(SyncHTTPClient(_make_config()))
    result = lib.chat(library_id="lib_x", message="hi")
    assert result.chat_id == "libchat_xyz"
    assert result.assistant_message == "Shall I go ahead?"
    assert result.narrative == (
        "Orders has 4,210 rows and two date columns.\n\nShall I go ahead?"
    )
    assert result.choices == _CARD
    assert result.tool_calls[0].name == "ask_choices"
    assert result.turns_used == 2


@respx.mock
async def test_async_chat_keeps_every_text_segment_and_the_card() -> None:
    respx.post(CHAT_URL).mock(return_value=_stream(_card_turn()))
    lib = AsyncLibrary(AsyncHTTPClient(_make_config()))
    result = await lib.chat(library_id="lib_x", message="hi")
    assert result.narrative.startswith("Orders has 4,210 rows")
    assert result.choices is not None
    assert result.choices["confirm_label"] == "Build the view"


@respx.mock
def test_sync_chat_without_deltas_falls_back_to_assistant_message() -> None:
    respx.post(CHAT_URL).mock(return_value=_stream([
        _sse({"type": "data-librarian", "data": {
            "chat_id": "c", "library_id": "lib_x", "assistant_message": "Done.",
        }}),
        "data: [DONE]",
    ]))
    lib = Library(SyncHTTPClient(_make_config()))
    result = lib.chat(library_id="lib_x", message="hi")
    assert result.narrative == "Done."
    assert result.choices is None


def test_error_output_is_not_a_card() -> None:
    from querri.resources.library import is_choice_card

    assert not is_choice_card({"error": "ask_choices needs a `question`"})
    assert not is_choice_card({"presented": True, "options": []})
    assert is_choice_card(_CARD)


# ── choice_label ──────────────────────────────────────────────────────────


def test_choice_label_by_number_and_label() -> None:
    assert choice_label(_CARD, "1") == "Build the view"
    assert choice_label(_CARD, "not NOW") == "Not now"
    assert choice_label(_CARD, "4") is None
    assert choice_label(_CARD, "Sí") is None


def test_choice_label_multi_select() -> None:
    card = {"options": [{"label": "A"}, {"label": "B"}, {"label": "C"}],
            "multi_select": True}
    assert choice_label(card, "1, c") == "A, C"
    assert choice_label(card, "1, nope") is None
