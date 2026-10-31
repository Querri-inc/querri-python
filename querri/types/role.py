"""Custom role (roles-as-code) type models for the Querri SDK."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

#: The definition-document schema the API speaks.
ROLE_SCHEMA = "querri.role/v1"

#: Fields the API returns but ignores on input. Stripped by
#: :meth:`RoleDefinition.to_definition` so an exported role re-applies cleanly.
ROLE_OUTPUT_ONLY_FIELDS: frozenset[str] = frozenset(
    {"id", "system", "seat_class", "user_count", "updated_at"}
)


class RoleDefinition(BaseModel):
    """A custom role as a definition document (``querri.role/v1``).

    The same model describes what you send to ``apply`` and what the API
    returns; the output-only fields (``id``, ``system``, ``seat_class``,
    ``user_count``, ``updated_at``) are ignored by the server on input.
    Unknown fields are kept, so a field a newer server adds survives an
    export and re-apply.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    schema_: str = Field(default=ROLE_SCHEMA, alias="schema")
    """Document schema, always ``querri.role/v1`` (serialized as ``schema``)."""
    key: str  #: Stable role key, ``^[a-z0-9][a-z0-9-]{0,47}$``.
    name: str  #: Display name, unique per org ignoring case.
    description: str | None = None  #: Optional description.
    base: str = "creator"  #: Base role: ``guest``, ``creator`` or ``admin``.
    enabled: bool = True  #: Whether the role can be assigned and used.
    grants: list[str] = []  #: Permission keys added on top of the base.
    denies: list[str] = []  #: Permission keys removed from the base.
    settings: dict[str, Any] = {}
    """Setting-kind permissions: ``{key: {"default", "user_can_change"}}``."""
    config: dict[str, Any] = {}
    """Role configuration (``home_chat``, ``landing``, ``credits_monthly``, ...)."""

    # Output-only fields (ignored on input).
    id: str | None = None  #: Server-assigned role ID.
    system: bool | None = None  #: ``True`` for built-in roles (guest/creator/admin).
    seat_class: str | None = None  #: Billing seat class the role counts as.
    user_count: int | None = None  #: Number of people holding the role.
    updated_at: str | None = None  #: ISO-8601 last-update timestamp.

    def to_definition(self) -> dict[str, Any]:
        """Return the document to save to a file and re-apply.

        Output-only fields and top-level ``None`` values are dropped, and the
        schema is serialized under its wire name, ``schema``.

        Returns:
            A JSON-serializable dict.
        """
        data = self.model_dump(mode="json", by_alias=True)
        return {
            k: v
            for k, v in data.items()
            if k not in ROLE_OUTPUT_ONLY_FIELDS and v is not None
        }


class RoleChange(BaseModel):
    """One field an apply changed (or would change, on a dry run)."""

    field: str  #: Definition field, e.g. ``"denies"`` or ``"config"``.
    before: Any = None  #: Value before the apply (``None`` on create).
    after: Any = None  #: Value after the apply.


class RoleApplyError(BaseModel):
    """Why one role in an apply or import failed."""

    code: str = ""  #: Machine-readable error code, e.g. ``"escalation_denied"``.
    message: str = ""  #: Human-readable explanation.


class RoleApplyResult(BaseModel):
    """The outcome of applying one role definition."""

    key: str  #: The role key that was applied.
    action: str
    """``created``, ``updated``, ``unchanged``, ``would_create``,
    ``would_update`` or ``failed``."""
    changes: list[RoleChange] = []  #: Per-field changes (empty when unchanged).
    role: RoleDefinition | None = None  #: The role as stored (``None`` on failure).
    error: RoleApplyError | None = None  #: Set when ``action`` is ``failed``.

    @property
    def failed(self) -> bool:
        """``True`` when this role was not applied."""
        return self.action == "failed"


class RoleImportResult(BaseModel):
    """The outcome of importing several role definitions."""

    results: list[RoleApplyResult] = []  #: One result per definition, in order.
    applied: int = 0  #: Roles that did not fail.
    failed: int = 0  #: Roles that failed.


class RoleDeleteResponse(BaseModel):
    """Response from deleting a role."""

    deleted: str  #: Key of the deleted role.


class CatalogPermission(BaseModel):
    """One permission key a role can grant or deny.

    Extra fields the server sends are kept (``model_extra``).
    """

    model_config = ConfigDict(extra="allow")

    key: str  #: Permission key, e.g. ``"tools.charts.use"``.
    area: str | None = None  #: Product area the permission belongs to.
    kind: str | None = None  #: Permission kind, e.g. ``"action"`` or ``"setting"``.
    defaults: dict[str, Any] = {}  #: Default per base role (guest/creator/admin).
    requires: list[str] = []  #: Permission keys this one depends on.


class PermissionCatalog(BaseModel):
    """Every permission key roles are built from."""

    model_config = ConfigDict(extra="allow")

    catalog_version: int | None = None  #: Catalog revision.
    permissions: list[CatalogPermission] = []  #: The permission keys.
