"""``X-Querri-Client`` separates the CLI from library use of the SDK.

Both send the same ``querri-python/<ver>`` User-Agent, so before this header
the server could not tell a CLI user from someone scripting the SDK. The
server (Querri server-api `server_analytics.resolve_surface`) reads the
``cli`` / ``sdk`` prefix.
"""

from __future__ import annotations

import httpx
import typer

from querri import Querri
from querri._auth import _cli_headers
from querri._base_client import _default_headers
from querri._config import ClientConfig
from querri._version import __version__
from querri.cli._context import get_client


def test_library_use_is_sdk():
    cfg = ClientConfig(api_key="qk_abc", org_id="org_123")
    assert cfg.client_header == f"sdk/{__version__}"
    assert _default_headers(cfg)["X-Querri-Client"] == f"sdk/{__version__}"


def test_querri_client_sends_sdk_header():
    client = Querri(api_key="qk_abc", org_id="org_123")
    assert client._http._client.headers["X-Querri-Client"] == f"sdk/{__version__}"


def test_cli_built_client_sends_cli_header(monkeypatch):
    monkeypatch.delenv("QUERRI_API_KEY", raising=False)
    monkeypatch.delenv("QUERRI_ACCESS_TOKEN", raising=False)
    ctx = typer.Context(typer.core.TyperCommand(name="t"))
    ctx.obj = {"api_key": "qk_abc", "org_id": "org_123"}
    client = get_client(ctx)
    assert client._http._client.headers["X-Querri-Client"] == f"cli/{__version__}"
    assert client._config.client_kind == "cli"


def test_cli_header_actually_goes_on_the_wire(monkeypatch):
    """Not just set on an object — present on a real outgoing request."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": [], "has_more": False})

    ctx = typer.Context(typer.core.TyperCommand(name="t"))
    ctx.obj = {"api_key": "qk_abc", "org_id": "org_123"}
    client = get_client(ctx)
    client._http._client._transport = httpx.MockTransport(handler)
    client._http._client.get("/projects")
    assert seen and seen[0].headers["X-Querri-Client"] == f"cli/{__version__}"


def test_cli_token_requests_identify_as_cli():
    headers = _cli_headers()
    assert headers["X-Querri-Client"] == f"cli/{__version__}"
    assert headers["User-Agent"] == f"querri-python/{__version__}"
