"""Custom role resources (roles as code) — maps to /roles endpoints."""

from __future__ import annotations

import builtins
from collections.abc import Iterable
from typing import Any

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from ..types.role import (
    ROLE_OUTPUT_ONLY_FIELDS,
    PermissionCatalog,
    RoleApplyResult,
    RoleDefinition,
    RoleDeleteResponse,
    RoleImportResult,
)

#: Fields a listed role must carry to be exported without a per-role fetch.
_DEFINITION_FIELDS = frozenset({"grants", "denies", "settings", "config"})


def _to_body(definition: RoleDefinition | dict[str, Any]) -> dict[str, Any]:
    """Serialize a definition for the wire, without output-only fields."""
    if isinstance(definition, RoleDefinition):
        return definition.to_definition()
    if not isinstance(definition, dict):
        raise TypeError(
            "A role definition must be a RoleDefinition or a dict, "
            f"not {type(definition).__name__}."
        )
    return {k: v for k, v in definition.items() if k not in ROLE_OUTPUT_ONLY_FIELDS}


def _key_of(body: dict[str, Any]) -> str:
    key = body.get("key")
    if not isinstance(key, str) or not key:
        raise ValueError("A role definition needs a 'key' to be applied.")
    return key


def _dry_run_params(dry_run: bool) -> dict[str, str]:
    return {"dry_run": "true"} if dry_run else {}


def _needs_fetch(role: RoleDefinition) -> bool:
    """``True`` when a listed role is a summary, not a full definition."""
    return not role.model_fields_set >= _DEFINITION_FIELDS


class Roles:
    """Synchronous custom role management — roles as code.

    A role is a definition document identified by a stable ``key``. Export
    it, edit it, apply it back: apply is an idempotent upsert.

    Usage::

        result = client.roles.apply({
            "key": "ev-datapro",
            "name": "EV DataPro",
            "base": "creator",
            "denies": ["chat.code.view"],
        })
        print(result.action)  # created / updated / unchanged
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def list(self) -> builtins.list[RoleDefinition]:
        """List every role in the organization, system roles included.

        Returns:
            All roles (not paginated). System roles have ``system=True``.
        """
        resp = self._http.get("/roles")
        return [RoleDefinition.model_validate(r) for r in resp.json().get("data", [])]

    def get(self, ref: str) -> RoleDefinition:
        """Get one role.

        Args:
            ref: The role key or ID.

        Returns:
            The role, output-only fields included.
        """
        resp = self._http.get(f"/roles/{ref}")
        return RoleDefinition.model_validate(resp.json())

    def catalog(self) -> PermissionCatalog:
        """Get the permission catalog roles are built from.

        Returns:
            Every permission key with its area, kind, defaults and requirements.
        """
        resp = self._http.get("/roles/catalog")
        return PermissionCatalog.model_validate(resp.json())

    def apply(
        self,
        definition: RoleDefinition | dict[str, Any],
        *,
        dry_run: bool = False,
    ) -> RoleApplyResult:
        """Create or replace a role from its definition (idempotent upsert).

        Args:
            definition: A ``RoleDefinition`` or a definition dict. Its ``key``
                names the role; output-only fields are not sent.
            dry_run: Validate and report the changes without writing anything.

        Returns:
            The result: ``action`` is ``created``, ``updated``, ``unchanged``,
            ``would_create`` or ``would_update``, with per-field ``changes``.

        Raises:
            ValueError: If the definition has no ``key``.
        """
        body = _to_body(definition)
        key = _key_of(body)
        resp = self._http.put(
            f"/roles/{key}", json=body, params=_dry_run_params(dry_run)
        )
        return RoleApplyResult.model_validate(resp.json())

    def import_roles(
        self,
        definitions: Iterable[RoleDefinition | dict[str, Any]],
        *,
        dry_run: bool = False,
    ) -> RoleImportResult:
        """Apply several role definitions in one call.

        Roles are applied in order and independently: one failure does not
        stop the rest. Check ``result.failed`` or each result's ``action``.

        Args:
            definitions: ``RoleDefinition`` objects or definition dicts.
            dry_run: Validate and report the changes without writing anything.

        Returns:
            One result per definition, plus ``applied`` / ``failed`` counts.
        """
        roles = [_to_body(d) for d in definitions]
        resp = self._http.post(
            "/roles/import", json={"roles": roles, "dry_run": dry_run}
        )
        return RoleImportResult.model_validate(resp.json())

    def delete(self, ref: str, *, reassign_to: str | None = None) -> RoleDeleteResponse:
        """Delete a custom role.

        Args:
            ref: The role key or ID.
            reassign_to: Key of the role to give people who hold this role as
                their only role. Required when there are any (409
                ``role_in_use`` otherwise).

        Returns:
            The key of the deleted role.
        """
        params = {"reassign_to": reassign_to} if reassign_to else {}
        resp = self._http.delete(f"/roles/{ref}", params=params)
        return RoleDeleteResponse.model_validate(resp.json())

    def export(self, *, include_system: bool = False) -> builtins.list[dict[str, Any]]:
        """Export roles as definition documents ready to save and re-apply.

        Args:
            include_system: Also export the built-in roles. They cannot be
                applied, so they are left out by default.

        Returns:
            One definition dict per role, output-only fields stripped.
        """
        out: builtins.list[dict[str, Any]] = []
        for role in self.list():
            if role.system and not include_system:
                continue
            full = self.get(role.key) if _needs_fetch(role) else role
            out.append(full.to_definition())
        return out


class AsyncRoles:
    """Asynchronous custom role management — roles as code.

    A role is a definition document identified by a stable ``key``. Export
    it, edit it, apply it back: apply is an idempotent upsert.

    Usage::

        result = await client.roles.apply({
            "key": "ev-datapro",
            "name": "EV DataPro",
            "base": "creator",
            "denies": ["chat.code.view"],
        })
        print(result.action)  # created / updated / unchanged
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def list(self) -> builtins.list[RoleDefinition]:
        """List every role in the organization, system roles included.

        Returns:
            All roles (not paginated). System roles have ``system=True``.
        """
        resp = await self._http.get("/roles")
        return [RoleDefinition.model_validate(r) for r in resp.json().get("data", [])]

    async def get(self, ref: str) -> RoleDefinition:
        """Get one role.

        Args:
            ref: The role key or ID.

        Returns:
            The role, output-only fields included.
        """
        resp = await self._http.get(f"/roles/{ref}")
        return RoleDefinition.model_validate(resp.json())

    async def catalog(self) -> PermissionCatalog:
        """Get the permission catalog roles are built from.

        Returns:
            Every permission key with its area, kind, defaults and requirements.
        """
        resp = await self._http.get("/roles/catalog")
        return PermissionCatalog.model_validate(resp.json())

    async def apply(
        self,
        definition: RoleDefinition | dict[str, Any],
        *,
        dry_run: bool = False,
    ) -> RoleApplyResult:
        """Create or replace a role from its definition (idempotent upsert).

        Args:
            definition: A ``RoleDefinition`` or a definition dict. Its ``key``
                names the role; output-only fields are not sent.
            dry_run: Validate and report the changes without writing anything.

        Returns:
            The result: ``action`` is ``created``, ``updated``, ``unchanged``,
            ``would_create`` or ``would_update``, with per-field ``changes``.

        Raises:
            ValueError: If the definition has no ``key``.
        """
        body = _to_body(definition)
        key = _key_of(body)
        resp = await self._http.put(
            f"/roles/{key}", json=body, params=_dry_run_params(dry_run)
        )
        return RoleApplyResult.model_validate(resp.json())

    async def import_roles(
        self,
        definitions: Iterable[RoleDefinition | dict[str, Any]],
        *,
        dry_run: bool = False,
    ) -> RoleImportResult:
        """Apply several role definitions in one call.

        Roles are applied in order and independently: one failure does not
        stop the rest. Check ``result.failed`` or each result's ``action``.

        Args:
            definitions: ``RoleDefinition`` objects or definition dicts.
            dry_run: Validate and report the changes without writing anything.

        Returns:
            One result per definition, plus ``applied`` / ``failed`` counts.
        """
        roles = [_to_body(d) for d in definitions]
        resp = await self._http.post(
            "/roles/import", json={"roles": roles, "dry_run": dry_run}
        )
        return RoleImportResult.model_validate(resp.json())

    async def delete(
        self, ref: str, *, reassign_to: str | None = None
    ) -> RoleDeleteResponse:
        """Delete a custom role.

        Args:
            ref: The role key or ID.
            reassign_to: Key of the role to give people who hold this role as
                their only role. Required when there are any (409
                ``role_in_use`` otherwise).

        Returns:
            The key of the deleted role.
        """
        params = {"reassign_to": reassign_to} if reassign_to else {}
        resp = await self._http.delete(f"/roles/{ref}", params=params)
        return RoleDeleteResponse.model_validate(resp.json())

    async def export(
        self, *, include_system: bool = False
    ) -> builtins.list[dict[str, Any]]:
        """Export roles as definition documents ready to save and re-apply.

        Args:
            include_system: Also export the built-in roles. They cannot be
                applied, so they are left out by default.

        Returns:
            One definition dict per role, output-only fields stripped.
        """
        out: builtins.list[dict[str, Any]] = []
        for role in await self.list():
            if role.system and not include_system:
                continue
            full = await self.get(role.key) if _needs_fetch(role) else role
            out.append(full.to_definition())
        return out
