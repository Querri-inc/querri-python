"""Base HTTP client with auth, retry, and error handling.

Both sync and async clients inherit from this to share configuration
and header injection logic.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Optional, Union

import httpx

from ._config import ClientConfig
from ._exceptions import (
    APIError,
    RateLimitError,
    raise_for_status,
)

logger = logging.getLogger("querri")

# Methods that are safe to retry on 5xx (idempotent)
_IDEMPOTENT_METHODS = {"GET", "PUT", "DELETE", "HEAD", "OPTIONS"}

# Status codes that trigger automatic retry
_RETRYABLE_STATUSES = {429, 500, 502, 503}


def _default_headers(config: ClientConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.api_key}",
        "X-Tenant-ID": config.org_id,
        "User-Agent": config.user_agent,
        "Accept": "application/json",
    }


def _should_retry(status: int, method: str) -> bool:
    if status == 429:
        return True
    if status in _RETRYABLE_STATUSES and method.upper() in _IDEMPOTENT_METHODS:
        return True
    return False


def _backoff_delay(attempt: int, retry_after: Optional[float] = None) -> float:
    """Exponential backoff with jitter."""
    if retry_after is not None and retry_after > 0:
        return retry_after
    base = min(2**attempt, 30)
    jitter = random.random() * 0.5  # noqa: S311
    return base + jitter


def _parse_error_response(response: httpx.Response) -> dict[str, Any]:
    """Try to parse JSON error body, fall back to empty dict."""
    try:
        return response.json()  # type: ignore[no-any-return]
    except Exception:
        return {}


def _get_retry_after(response: httpx.Response) -> Optional[float]:
    header = response.headers.get("retry-after")
    if header is None:
        return None
    try:
        return float(header)
    except ValueError:
        return None


class SyncHTTPClient:
    """Synchronous HTTP client with retry and error handling."""

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            headers=_default_headers(config),
            timeout=httpx.Timeout(config.timeout),
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        files: Optional[Any] = None,
        headers: Optional[dict[str, str]] = None,
        stream: bool = False,
    ) -> httpx.Response:
        """Make an HTTP request with automatic retry."""
        max_retries = self._config.max_retries
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                if stream:
                    # For streaming, caller manages the response lifecycle
                    req = self._client.build_request(
                        method, path, json=json, params=params,
                        data=data, files=files, headers=headers,
                    )
                    response = self._client.send(req, stream=True)
                else:
                    response = self._client.request(
                        method, path, json=json, params=params,
                        data=data, files=files, headers=headers,
                    )

                if response.status_code < 400:
                    return response

                # Check if we should retry
                if (
                    attempt < max_retries
                    and _should_retry(response.status_code, method)
                ):
                    retry_after = _get_retry_after(response)
                    delay = _backoff_delay(attempt, retry_after)
                    logger.debug(
                        "Retrying %s %s (attempt %d/%d, status %d, delay %.1fs)",
                        method, path, attempt + 1, max_retries,
                        response.status_code, delay,
                    )
                    time.sleep(delay)
                    continue

                # Not retryable — raise
                body = _parse_error_response(response)
                request_id = response.headers.get("x-request-id")
                retry_after = _get_retry_after(response)
                raise_for_status(
                    response.status_code, body,
                    request_id=request_id, retry_after=retry_after,
                )

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < max_retries:
                    delay = _backoff_delay(attempt)
                    logger.debug(
                        "Connection error on %s %s (attempt %d/%d, delay %.1fs): %s",
                        method, path, attempt + 1, max_retries, delay, exc,
                    )
                    time.sleep(delay)
                    continue
                raise APIError(
                    f"Connection failed after {max_retries + 1} attempts: {exc}",
                    status=0,
                ) from last_exc

        # Should not reach here, but just in case
        raise APIError(
            f"Request failed after {max_retries + 1} attempts",
            status=0,
        )

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        self._client.close()


class AsyncHTTPClient:
    """Asynchronous HTTP client with retry and error handling."""

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=_default_headers(config),
            timeout=httpx.Timeout(config.timeout),
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        files: Optional[Any] = None,
        headers: Optional[dict[str, str]] = None,
        stream: bool = False,
    ) -> httpx.Response:
        """Make an async HTTP request with automatic retry."""
        import asyncio

        max_retries = self._config.max_retries
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                if stream:
                    req = self._client.build_request(
                        method, path, json=json, params=params,
                        data=data, files=files, headers=headers,
                    )
                    response = await self._client.send(req, stream=True)
                else:
                    response = await self._client.request(
                        method, path, json=json, params=params,
                        data=data, files=files, headers=headers,
                    )

                if response.status_code < 400:
                    return response

                if (
                    attempt < max_retries
                    and _should_retry(response.status_code, method)
                ):
                    retry_after = _get_retry_after(response)
                    delay = _backoff_delay(attempt, retry_after)
                    logger.debug(
                        "Retrying %s %s (attempt %d/%d, status %d, delay %.1fs)",
                        method, path, attempt + 1, max_retries,
                        response.status_code, delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                body = _parse_error_response(response)
                request_id = response.headers.get("x-request-id")
                retry_after = _get_retry_after(response)
                raise_for_status(
                    response.status_code, body,
                    request_id=request_id, retry_after=retry_after,
                )

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < max_retries:
                    delay = _backoff_delay(attempt)
                    logger.debug(
                        "Connection error on %s %s (attempt %d/%d, delay %.1fs): %s",
                        method, path, attempt + 1, max_retries, delay, exc,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise APIError(
                    f"Connection failed after {max_retries + 1} attempts: {exc}",
                    status=0,
                ) from last_exc

        raise APIError(
            f"Request failed after {max_retries + 1} attempts",
            status=0,
        )

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)

    async def close(self) -> None:
        await self._client.aclose()
