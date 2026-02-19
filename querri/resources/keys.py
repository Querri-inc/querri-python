"""API key management resource."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from ..types.key import ApiKey, ApiKeyCreated


class Keys:
    """Synchronous API key management resource.

    Usage::

        new_key = client.keys.create(name="CI Pipeline", scopes=["data:read"])
        keys = client.keys.list()
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def create(
        self,
        *,
        name: str,
        scopes: List[str],
        expires_in_days: Optional[int] = None,
        source_scope: Optional[Dict[str, Any]] = None,
        access_policy_ids: Optional[List[str]] = None,
        bound_user_id: Optional[str] = None,
        rate_limit_per_minute: Optional[int] = None,
        ip_allowlist: Optional[List[str]] = None,
    ) -> ApiKeyCreated:
        """Create a new API key. Returns the plaintext secret once.

        Args:
            name: Display name for the key.
            scopes: List of permission scopes.
            expires_in_days: Days until expiration.
            source_scope: Source access scope configuration.
            access_policy_ids: Bound access policy UUIDs.
            bound_user_id: User ID to bind RLS to.
            rate_limit_per_minute: Rate limit override.
            ip_allowlist: Allowed IP addresses.

        Returns:
            ApiKeyCreated with id, name, key_prefix, secret, scopes, status, etc.
            The ``secret`` field is only returned on creation.
        """
        payload: Dict[str, Any] = {"name": name, "scopes": scopes}
        if expires_in_days is not None:
            payload["expires_in_days"] = expires_in_days
        if source_scope is not None:
            payload["source_scope"] = source_scope
        if access_policy_ids is not None:
            payload["access_policy_ids"] = access_policy_ids
        if bound_user_id is not None:
            payload["bound_user_id"] = bound_user_id
        if rate_limit_per_minute is not None:
            payload["rate_limit_per_minute"] = rate_limit_per_minute
        if ip_allowlist is not None:
            payload["ip_allowlist"] = ip_allowlist
        resp = self._http.post("/keys", json=payload)
        return ApiKeyCreated.model_validate(resp.json())

    def get(self, key_id: str) -> ApiKey:
        """Get API key details (never returns the secret).

        Args:
            key_id: The key UUID.

        Returns:
            ApiKey object.
        """
        resp = self._http.get(f"/keys/{key_id}")
        return ApiKey.model_validate(resp.json())

    def list(self) -> List[ApiKey]:
        """List API keys for the organization.

        Returns:
            List of ApiKey objects (secrets are never included).
        """
        resp = self._http.get("/keys")
        body = resp.json()
        return [ApiKey.model_validate(k) for k in body.get("data", [])]

    def delete(self, key_id: str) -> Dict[str, Any]:
        """Revoke an API key.

        Args:
            key_id: The key UUID.

        Returns:
            Dict with id and status ("revoked").
        """
        resp = self._http.delete(f"/keys/{key_id}")
        return resp.json()


class AsyncKeys:
    """Asynchronous API key management resource."""

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create(
        self,
        *,
        name: str,
        scopes: List[str],
        expires_in_days: Optional[int] = None,
        source_scope: Optional[Dict[str, Any]] = None,
        access_policy_ids: Optional[List[str]] = None,
        bound_user_id: Optional[str] = None,
        rate_limit_per_minute: Optional[int] = None,
        ip_allowlist: Optional[List[str]] = None,
    ) -> ApiKeyCreated:
        """Create a new API key. Returns the plaintext secret once."""
        payload: Dict[str, Any] = {"name": name, "scopes": scopes}
        if expires_in_days is not None:
            payload["expires_in_days"] = expires_in_days
        if source_scope is not None:
            payload["source_scope"] = source_scope
        if access_policy_ids is not None:
            payload["access_policy_ids"] = access_policy_ids
        if bound_user_id is not None:
            payload["bound_user_id"] = bound_user_id
        if rate_limit_per_minute is not None:
            payload["rate_limit_per_minute"] = rate_limit_per_minute
        if ip_allowlist is not None:
            payload["ip_allowlist"] = ip_allowlist
        resp = await self._http.post("/keys", json=payload)
        return ApiKeyCreated.model_validate(resp.json())

    async def get(self, key_id: str) -> ApiKey:
        """Get API key details (never returns the secret)."""
        resp = await self._http.get(f"/keys/{key_id}")
        return ApiKey.model_validate(resp.json())

    async def list(self) -> List[ApiKey]:
        """List API keys for the organization."""
        resp = await self._http.get("/keys")
        body = resp.json()
        return [ApiKey.model_validate(k) for k in body.get("data", [])]

    async def delete(self, key_id: str) -> Dict[str, Any]:
        """Revoke an API key."""
        resp = await self._http.delete(f"/keys/{key_id}")
        return resp.json()
