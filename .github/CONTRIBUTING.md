# Contributing to querri

Thanks for your interest in contributing! This guide will help you get started.

## Getting started

1. Fork and clone the repository
2. Install dependencies:
   ```sh
   pip install -e ".[dev]"
   ```
3. Run tests:
   ```sh
   pytest tests/ -v
   ```
4. Run linting and type checking:
   ```sh
   ruff check querri/ tests/
   mypy querri/
   ```

## Project structure

```
querri/
  resources/    API resource classes (Users, Projects, Dashboards, Sources, Data, etc.)
  types/        Pydantic v2 models for API request/response types
  _client.py    Querri / AsyncQuerri public entry points
  _base_client.py  SyncHTTPClient / AsyncHTTPClient with auth, retries, error mapping
  _user_client.py  UserQuerri / AsyncUserQuerri for embed session auth
  _config.py    Configuration resolution (constructor args > env vars > defaults)
  _pagination.py   Cursor-based auto-paginating iterators
  _streaming.py    SSE chat streaming (Vercel AI SDK format)
  _convenience.py  High-level helpers (get_session, policy setup)
  _exceptions.py   Exception hierarchy (QuerriError, APIError, etc.)
```

- **Tests**: [pytest](https://docs.pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) with [respx](https://lundberg.github.io/respx/) for HTTP mocking
- **Type checking**: [mypy](https://mypy-lang.org/) in strict mode
- **Linting**: [ruff](https://docs.astral.sh/ruff/)

## Submitting changes

1. Create a branch from `main`
2. Make your changes with clear, descriptive commits
3. Ensure CI passes:
   ```sh
   pytest tests/ -v
   ruff check querri/ tests/
   mypy querri/
   ```
4. Open a pull request against `main`

## Reporting bugs

Please use the [bug report template](https://github.com/querri-ai/querri-python/issues/new?template=bug_report.md) when filing issues.

## Code of conduct

Be respectful and constructive. We're building something together — treat others the way you'd like to be treated.
