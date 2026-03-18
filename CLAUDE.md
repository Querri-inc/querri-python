# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Querri Python SDK — a typed Python client for the Querri API, providing both sync (`Querri`) and async (`AsyncQuerri`) clients. Built on httpx + Pydantic v2. Requires Python >=3.9.

## Commands

```bash
# Install in development mode (includes test + lint + type-check tools)
pip install -e ".[dev]"

# Run all unit tests
pytest tests/ -v

# Run a single test file
pytest tests/test_client.py -v

# Run a single test by name
pytest tests/ -k "test_name" -v

# Run integration tests (requires QUERRI_API_KEY and QUERRI_ORG_ID env vars)
pytest tests/test_integration.py -m integration -v

# Type checking
mypy querri/

# Linting
ruff check querri/ tests/
```

## Architecture

### Client Layer
`Querri` / `AsyncQuerri` (`_client.py`) are the public entry points. They hold lazily-initialized resource namespaces (e.g., `client.users`, `client.projects`) and support context-manager usage. They delegate HTTP to `SyncHTTPClient` / `AsyncHTTPClient` (`_base_client.py`), which handle auth headers (Bearer token + X-Tenant-ID), retries with exponential backoff, and error-to-exception mapping.

### User-Scoped Client
`UserQuerri` / `AsyncUserQuerri` (`_user_client.py`) are created via `client.as_user(session)`. They use `X-Embed-Session` auth against the internal API (`/api` instead of `/api/v1`). Only expose FGA-filtered resources: `projects`, `dashboards`, `sources`, `data`, `chats`.

### Resource Pattern
Each API resource lives in `querri/resources/` with paired sync/async classes (e.g., `Users` / `AsyncUsers`). Resources receive the HTTP client at init and expose CRUD methods that return Pydantic models from `querri/types/`. Projects has a nested `Chats` sub-resource for chat streaming.

### Key Subsystems
- **Pagination** (`_pagination.py`): `SyncCursorPage[T]` / `AsyncCursorPage[T]` — cursor-based with offset fallback, auto-paginating via `__iter__`/`__aiter__`.
- **Streaming** (`_streaming.py`): `ChatStream` / `AsyncChatStream` — SSE parsing (Vercel AI SDK format: `0:` text, `e:` error, `d:` done).
- **Convenience** (`_convenience.py`): `get_session()` is the flagship method — resolves/creates a user, applies access policies, and creates an embed session in one call. `client.policies.setup()` creates a policy and assigns users in one call.
- **Config** (`_config.py`): Constructor args > env vars (`QUERRI_API_KEY`, `QUERRI_ORG_ID`, `QUERRI_HOST`, `QUERRI_TIMEOUT`, `QUERRI_MAX_RETRIES`) > defaults.
- **Exceptions** (`_exceptions.py`): `QuerriError` → `APIError` (with status-specific subclasses like `RateLimitError`), `StreamError`, `ConfigError`.

## Sync/Async Parity

Every resource, pagination class, and stream has mirrored sync/async implementations. When modifying code:
- Always change both sync and async variants simultaneously.
- Async methods use `await` and `async for` but share identical method signatures and return types.
- In resource files: sync class comes first, async class second.
- In `_convenience.py`: shared helpers at top, then sync functions, then async functions.

## Adding a New Resource

1. Create type models in `querri/types/<name>.py` — Pydantic `BaseModel` subclasses with `#:` inline field docs.
2. Create `querri/resources/<name>.py` with paired classes:
   - `class Foo:` taking `SyncHTTPClient` at `__init__`
   - `class AsyncFoo:` taking `AsyncHTTPClient` at `__init__`
   - Both must have full Google-style docstrings (Args/Returns) on every method.
3. Register lazy properties on both `Querri` and `AsyncQuerri` in `_client.py` (follow the existing deferred-import pattern).
4. Export new public types in `querri/__init__.py` if needed.
5. Add tests in `tests/test_<name>.py` using respx mocking.

## Testing Patterns

- Use `@respx.mock` decorator for HTTP mocking.
- Create a `_make_config()` helper returning `ClientConfig` with test values (`api_key="qk_test"`, `org_id="org_test"`, `base_url="https://test.querri.com/api/v1"`).
- Instantiate `SyncHTTPClient(_make_config())` or `AsyncHTTPClient(_make_config())` directly.
- Mock specific URLs: `respx.get("https://test.querri.com/api/v1/endpoint").mock(return_value=httpx.Response(200, json={...}))`.
- Use `side_effect=[Response1, Response2]` for multi-page pagination tests.
- pytest-asyncio runs in `auto` mode — no `@pytest.mark.asyncio` decorator needed on async tests.
- Integration tests are marked `@pytest.mark.integration` and require `QUERRI_API_KEY` + `QUERRI_ORG_ID` env vars.

## Docstring Conventions

- **Style**: Google-style with `Args:`, `Returns:`, `Raises:`, `Example::` sections.
- **Inline code**: Use double backticks — `` ``value`` ``.
- **Sync + async**: Both classes get full docstrings with Args/Returns (don't truncate async).
- **Type model fields**: Use `#:` inline comments on the same line as the field.
- **Module docstrings**: Every module has a 1-line docstring describing its purpose.

## Code Quality

- **mypy**: Strict mode, target Python 3.9
- **ruff**: Rules E, F, I, N, UP, B, SIM (target Python 3.9)
- **Tests**: pytest + pytest-asyncio (mode: auto) + respx for HTTP mocking
