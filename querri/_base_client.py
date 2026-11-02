"""Base HTTP client with auth, retry, and error handling.

Both sync and async clients inherit from this to share configuration
and header injection logic.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any

import httpx

from ._config import ClientConfig
from ._exceptions import (
    APIError,
    raise_for_status,
)

logger = logging.getLogger("querri")

# Methods that are safe to retry on 5xx (idempotent)
_IDEMPOTENT_METHODS = {"GET", "PUT", "DELETE", "HEAD", "OPTIONS"}

# Status codes that trigger automatic retry
_RETRYABLE_STATUSES = {429, 500, 502, 503}


def _default_headers(config: ClientConfig) -> dict[str, str]:
    """Build default HTTP headers including auth, tenant ID, user agent, and Accept.

    Auth priority:
    1. Session token (``X-Embed-Session``) — user-scoped client via ``as_user()``.
    2. JWT access token (``Bearer ey*``) — OAuth login, no X-Tenant-ID needed.
    3. API key (``Bearer qk_*``) — API key auth with X-Tenant-ID for tenant isolation.

    ``X-Querri-Workspace`` is sent whenever the client has an active workspace. It
    is the same header the web app's workspace switcher sends, and it is what makes
    an SDK upload land in a named workspace instead of the caller's personal one.
    Note the server ignores it for API-key auth (there is no user whose membership
    could validate the claim) — workspace scoping needs a signed-in identity, i.e.
    ``querri auth login``.
    """
    headers: dict[str, str] = {
        "User-Agent": config.user_agent,
        "Accept": "application/json",
        "X-Querri-Client": config.client_header,
    }
    if config.workspace_id:
        headers["X-Querri-Workspace"] = config.workspace_id
    if config.session_token:
        headers["X-Embed-Session"] = config.session_token
    elif config.access_token:
        headers["Authorization"] = f"Bearer {config.access_token}"
    elif config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
        if config.org_id:
            headers["X-Tenant-ID"] = config.org_id
    return headers


def _should_retry(status: int, method: str) -> bool:
    """Check if a failed request should be retried.

    429 (rate limit) always retries. 5xx only retries for idempotent methods
    (GET, PUT, DELETE, HEAD, OPTIONS) to avoid duplicate side effects from POST.
    """
    if status == 429:
        return True
    return status in _RETRYABLE_STATUSES and method.upper() in _IDEMPOTENT_METHODS


def _backoff_delay(attempt: int, retry_after: float | None = None) -> float:
    """Exponential backoff with jitter.

    Uses 2^attempt capped at 30s, plus 0-0.5s random jitter to prevent
    thundering herd. If the server sent a Retry-After header, uses that
    value instead.
    """
    if retry_after is not None and retry_after > 0:
        return retry_after
    base: float = min(2**attempt, 30)
    jitter = random.random() * 0.5  # noqa: S311
    return base + jitter


def _parse_error_response(response: httpx.Response) -> Any:
    """Parse the JSON error body (any JSON value), or ``None`` when it is not JSON."""
    try:
        return response.json()
    except Exception:
        return None


def _read_streamed_error(response: httpx.Response) -> None:
    """Load the body of a streamed error response, then close it.

    A response from ``send(stream=True)`` has not read its body, so
    ``response.json()`` raises ``ResponseNotRead`` and the error's code,
    message, permission and reason would be lost. Reading it first lets
    :func:`_parse_error_response` see the body. The response is closed
    either way, since no caller will consume a stream that raised.
    """
    try:
        response.read()
    except httpx.HTTPError:
        pass  # The body is unreadable; the status alone still raises.
    finally:
        response.close()


async def _aread_streamed_error(response: httpx.Response) -> None:
    """Async counterpart of :func:`_read_streamed_error`."""
    try:
        await response.aread()
    except httpx.HTTPError:
        pass  # The body is unreadable; the status alone still raises.
    finally:
        await response.aclose()


def _get_retry_after(response: httpx.Response) -> float | None:
    """Parse Retry-After header as seconds.

    Returns None if absent or unparseable.
    """
    header = response.headers.get("retry-after")
    if header is None:
        return None
    try:
        return float(header)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Token renewal
# ---------------------------------------------------------------------------

def _is_stale_credential(response: httpx.Response) -> bool:
    """Does this failure mean "your token aged out" rather than "you may not"?

    401 from the application always does. The gateway in front of ``/api/v2/*``
    answers a bad JWT with a plain-text **403** ("token validation failed")
    instead, which is indistinguishable from a real authorization refusal by
    status alone — so that one is recognised by its shape: the application's own
    403s carry a JSON ``error`` envelope, the gateway's carries text.

    Deliberately narrow. Renewing on every 403 would retry genuine permission
    failures with a fresh token and report the same refusal a second time.
    """
    if response.status_code == 401:
        return True
    if response.status_code != 403:
        return False
    if "json" in (response.headers.get("content-type") or "").lower():
        return False
    try:
        return "token" in response.text.lower()
    except Exception:  # noqa: BLE001 — a body we cannot read is not evidence
        return False


_REFRESH_LOCK = threading.Lock()


def _renew_token(config: ClientConfig) -> str | None:
    """Refresh a store-sourced JWT and return the new access token, or None.

    **A long-running script outliving its access token is the normal case, not
    an edge case.** WorkOS access tokens are short-lived; the SDK refreshed once
    at construction and then handed the caller a 401 the moment it aged out. A
    batch that ran three requests a minute for six minutes died on the fourth
    minute with `AuthenticationError: The JWT token is invalid or expired`,
    having done all its work and lost the results — with a valid refresh token
    sitting in the same file the access token came from.

    Only store-sourced tokens renew (``config.token_profile``). A token passed
    to the constructor belongs to the caller: the SDK neither renews it nor
    rewrites their token file.

    Serialized on a lock, and it re-reads the store inside it — with several
    threads sharing one client, the first to arrive refreshes and the rest find
    the fresh token already on disk rather than each burning a refresh.
    """
    if not config.token_profile or not config.access_token:
        return None
    with _REFRESH_LOCK:
        try:
            from ._auth import TokenStore, refresh_tokens

            store = TokenStore.load()
            profile = store.profiles.get(config.token_profile)
            if profile is None or not profile.refresh_token:
                return None
            # Someone else may have refreshed while we waited for the lock.
            if profile.access_token and profile.access_token != config.access_token:
                config.access_token = profile.access_token
                return profile.access_token
            profile = refresh_tokens(profile, config.host)
            store.save_profile(config.token_profile, profile)
            config.access_token = profile.access_token
            return profile.access_token
        except Exception as exc:  # noqa: BLE001 — a failed renewal is a 401, not a crash
            logger.debug("Token renewal failed: %s", exc)
            return None


class SyncHTTPClient:
    """Synchronous HTTP client with retry and error handling."""

    def __init__(self, config: ClientConfig) -> None:
        """Initialize with auth headers and connection pool from config."""
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            headers=_default_headers(config),
            timeout=httpx.Timeout(
                connect=config.timeout,
                read=600.0,  # Long read timeout for streaming
                write=config.timeout,
                pool=config.timeout,
            ),
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: Any | None = None,
        headers: dict[str, str] | None = None,
        stream: bool = False,
    ) -> httpx.Response:
        """Make an HTTP request with automatic retry."""
        max_retries = self._config.max_retries
        last_exc: Exception | None = None
        # A 401 does not consume a retry attempt — renewal is a different
        # failure from a flaky server, and burning an attempt on it would make
        # the first real 5xx after a token expiry unretryable.
        renewed = False

        attempt = 0
        while attempt <= max_retries:
            try:
                if stream:
                    # For streaming, caller manages the response lifecycle
                    req = self._client.build_request(
                        method,
                        path,
                        json=json,
                        params=params,
                        data=data,
                        files=files,
                        headers=headers,
                    )
                    response = self._client.send(req, stream=True)
                else:
                    response = self._client.request(
                        method,
                        path,
                        json=json,
                        params=params,
                        data=data,
                        files=files,
                        headers=headers,
                    )

                if response.status_code < 400:
                    return response

                # An expired JWT is renewable, so it is not the caller's
                # problem until renewal fails. Tried once per request: a second
                # rejection of a token minted seconds ago is a real
                # authorization answer, not staleness.
                if not renewed and _is_stale_credential(response):
                    renewed = True
                    fresh = _renew_token(self._config)
                    if fresh:
                        response.close()
                        self._client.headers["Authorization"] = f"Bearer {fresh}"
                        if headers and "Authorization" in headers:
                            headers["Authorization"] = f"Bearer {fresh}"
                        continue

                # Check if we should retry
                if attempt < max_retries and _should_retry(
                    response.status_code, method
                ):
                    retry_after = _get_retry_after(response)
                    delay = _backoff_delay(attempt, retry_after)
                    logger.debug(
                        "Retrying %s %s (attempt %d/%d, status %d, delay %.1fs)",
                        method,
                        path,
                        attempt + 1,
                        max_retries,
                        response.status_code,
                        delay,
                    )
                    if stream:
                        response.close()
                    time.sleep(delay)
                    attempt += 1
                    continue

                # Not retryable — raise
                if stream:
                    _read_streamed_error(response)
                body = _parse_error_response(response)
                request_id = response.headers.get("x-request-id")
                retry_after = _get_retry_after(response)
                raise_for_status(
                    response.status_code,
                    body,
                    request_id=request_id,
                    retry_after=retry_after,
                    permission_denied=response.headers.get("x-permission-denied"),
                )

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < max_retries:
                    delay = _backoff_delay(attempt)
                    logger.debug(
                        "Connection error on %s %s (attempt %d/%d, delay %.1fs): %s",
                        method,
                        path,
                        attempt + 1,
                        max_retries,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                    attempt += 1
                    continue
                raise APIError(
                    f"Connection failed after {max_retries + 1} attempts: {exc}",
                    status=0,
                ) from last_exc

        # Loop exhausted all retries without returning
        # or raising -- re-raise the last error.
        raise APIError(
            f"Request failed after {max_retries + 1} attempts",
            status=0,
        )

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Shorthand for :meth:`request` with method=GET."""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Shorthand for :meth:`request` with method=POST."""
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> httpx.Response:
        """Shorthand for :meth:`request` with method=PUT."""
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        """Shorthand for :meth:`request` with method=PATCH."""
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        """Shorthand for :meth:`request` with method=DELETE."""
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        self._client.close()


class AsyncHTTPClient:
    """Asynchronous HTTP client with retry and error handling."""

    def __init__(self, config: ClientConfig) -> None:
        """Initialize with auth headers and connection pool from config."""
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=_default_headers(config),
            timeout=httpx.Timeout(
                connect=config.timeout,
                read=600.0,
                write=config.timeout,
                pool=config.timeout,
            ),
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: Any | None = None,
        headers: dict[str, str] | None = None,
        stream: bool = False,
    ) -> httpx.Response:
        """Make an async HTTP request with automatic retry."""
        import asyncio

        max_retries = self._config.max_retries
        last_exc: Exception | None = None
        # A 401 does not consume a retry attempt — renewal is a different
        # failure from a flaky server, and burning an attempt on it would make
        # the first real 5xx after a token expiry unretryable.
        renewed = False

        attempt = 0
        while attempt <= max_retries:
            try:
                if stream:
                    req = self._client.build_request(
                        method,
                        path,
                        json=json,
                        params=params,
                        data=data,
                        files=files,
                        headers=headers,
                    )
                    response = await self._client.send(req, stream=True)
                else:
                    response = await self._client.request(
                        method,
                        path,
                        json=json,
                        params=params,
                        data=data,
                        files=files,
                        headers=headers,
                    )

                if response.status_code < 400:
                    return response

                # See the sync client: an expired JWT is renewable, so it is not
                # the caller's problem until renewal fails.
                if not renewed and _is_stale_credential(response):
                    renewed = True
                    fresh = await asyncio.to_thread(_renew_token, self._config)
                    if fresh:
                        await response.aclose()
                        self._client.headers["Authorization"] = f"Bearer {fresh}"
                        if headers and "Authorization" in headers:
                            headers["Authorization"] = f"Bearer {fresh}"
                        continue

                if attempt < max_retries and _should_retry(
                    response.status_code, method
                ):
                    retry_after = _get_retry_after(response)
                    delay = _backoff_delay(attempt, retry_after)
                    logger.debug(
                        "Retrying %s %s (attempt %d/%d, status %d, delay %.1fs)",
                        method,
                        path,
                        attempt + 1,
                        max_retries,
                        response.status_code,
                        delay,
                    )
                    if stream:
                        await response.aclose()
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue

                if stream:
                    await _aread_streamed_error(response)
                body = _parse_error_response(response)
                request_id = response.headers.get("x-request-id")
                retry_after = _get_retry_after(response)
                raise_for_status(
                    response.status_code,
                    body,
                    request_id=request_id,
                    retry_after=retry_after,
                    permission_denied=response.headers.get("x-permission-denied"),
                )

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < max_retries:
                    delay = _backoff_delay(attempt)
                    logger.debug(
                        "Connection error on %s %s (attempt %d/%d, delay %.1fs): %s",
                        method,
                        path,
                        attempt + 1,
                        max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                raise APIError(
                    f"Connection failed after {max_retries + 1} attempts: {exc}",
                    status=0,
                ) from last_exc

        # Loop exhausted all retries without returning
        # or raising -- re-raise the last error.
        raise APIError(
            f"Request failed after {max_retries + 1} attempts",
            status=0,
        )

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Shorthand for :meth:`request` with method=GET."""
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Shorthand for :meth:`request` with method=POST."""
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        """Shorthand for :meth:`request` with method=PUT."""
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        """Shorthand for :meth:`request` with method=PATCH."""
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        """Shorthand for :meth:`request` with method=DELETE."""
        return await self.request("DELETE", path, **kwargs)

    async def close(self) -> None:
        await self._client.aclose()
