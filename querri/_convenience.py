"""High-level convenience methods that compose multiple API calls.

The flagship method is `get_session()` which handles the complete white-label
embedding workflow: upsert user by external_id, apply access policies, and
create an embed session — all in one call.

These functions are called by resource classes (e.g., Embed.get_session())
and should not be imported directly by end users.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Union

from ._base_client import AsyncHTTPClient, SyncHTTPClient
from ._exceptions import ValidationError
from .types.policy import Policy

logger = logging.getLogger("querri")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _hash_access_spec(access: Dict[str, Any]) -> str:
    """Create a deterministic 8-char hex hash from an access spec.

    Used to generate stable policy names (``sdk_auto_<hash8>``) so that
    repeated calls with the same inline spec reuse the same policy instead
    of creating duplicates.

    The input dict is JSON-serialised with sorted keys and compact separators
    to guarantee determinism regardless of insertion order.
    """
    # Only hash the parts that define the policy content — not meta-keys
    # like ``policy_ids`` which reference existing policies.
    hashable = {
        k: v
        for k, v in access.items()
        if k in ("sources", "filters")
    }
    normalized = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()[:8]


def _build_policy_body(access: Dict[str, Any], policy_name: str) -> Dict[str, Any]:
    """Convert an inline access dict to a policy creation request body.

    Maps the user-friendly SDK format::

        {
            "sources": ["src_abc", "src_def"],
            "filters": {
                "region": ["APAC", "EMEA"],
                "department": "Sales",
            },
        }

    to the server's ``CreatePolicyRequest`` shape::

        {
            "name": "sdk_auto_a1b2c3d4",
            "source_ids": ["src_abc", "src_def"],
            "row_filters": [
                {"column": "region", "values": ["APAC", "EMEA"]},
                {"column": "department", "values": ["Sales"]},
            ],
        }
    """
    body: Dict[str, Any] = {"name": policy_name}

    sources = access.get("sources")
    if sources:
        body["source_ids"] = list(sources)

    filters = access.get("filters")
    if filters and isinstance(filters, dict):
        row_filters: List[Dict[str, Any]] = []
        for column, values in filters.items():
            if isinstance(values, list):
                row_filters.append({"column": column, "values": values})
            else:
                # Single value — wrap in a list for the server
                row_filters.append({"column": column, "values": [values]})
        body["row_filters"] = row_filters

    return body


def _resolve_user_param(user: Union[str, Dict[str, Any]]) -> tuple[str, Optional[Dict[str, Any]]]:
    """Normalise the ``user`` parameter into (external_id, creation_body | None).

    Returns:
        A tuple of ``(external_id, body_for_put_or_none)``.
        When *user* is a plain string the body is ``None`` — the caller must
        look up the user by external_id and raise if not found.
        When *user* is a dict the body contains the fields needed for
        ``PUT /users/external/{external_id}``.
    """
    if isinstance(user, str):
        return user, None

    if not isinstance(user, dict):
        raise TypeError(
            f"'user' must be a string (external_id) or a dict, got {type(user).__name__}"
        )

    external_id = user.get("external_id")
    if not external_id:
        raise ValueError(
            "User dict must contain 'external_id'. "
            "Example: {'external_id': 'cust-42', 'email': 'alice@example.com'}"
        )

    body: Dict[str, Any] = {"role": user.get("role", "member")}
    email = user.get("email")
    if email:
        body["email"] = email
    if user.get("first_name"):
        body["first_name"] = user["first_name"]
    if user.get("last_name"):
        body["last_name"] = user["last_name"]

    return external_id, body


# ---------------------------------------------------------------------------
# Sync convenience methods
# ---------------------------------------------------------------------------


def sync_get_session(
    http: SyncHTTPClient,
    *,
    user: Union[str, Dict[str, Any]],
    access: Optional[Dict[str, Any]] = None,
    origin: Optional[str] = None,
    ttl: int = 3600,
) -> Dict[str, Any]:
    """Flagship convenience method — get-or-create user, apply policy, create session.

    This is the single most important method in the SDK. It encapsulates the
    entire white-label embedding workflow in one call:

    1. **Resolve user** — look up or create a user by ``external_id``.
    2. **Apply access** — assign existing policies or find-or-create an
       inline policy from a spec dict.
    3. **Create session** — mint an embed session token for the resolved user.

    Args:
        http: The synchronous HTTP client (injected by the resource class).
        user: Either a string ``external_id`` (user must already exist) or a
            dict with at least ``external_id`` and ``email`` (get-or-create).
            Optional keys: ``first_name``, ``last_name``, ``role``.
        access: Access policy configuration. Accepts two shapes:

            * ``{"policy_ids": ["pol_abc"]}`` — assign user to existing policies.
            * ``{"sources": [...], "filters": {...}}`` — find-or-create an
              auto-named policy matching this spec, then assign.

            If ``None``, no policy changes are made (user keeps existing access).
        origin: Allowed origin for the embed session (e.g. ``https://app.customer.com``).
        ttl: Session time-to-live in seconds (default 3600, min 900, max 86400).

    Returns:
        Embed session dict with ``session_token``, ``expires_in``, ``user_id``,
        and ``external_id``.

    Raises:
        ValueError: If ``user`` is a string and no user with that external_id exists.
        ValidationError: If request parameters are invalid.
        APIError: On any HTTP error from the Querri API.

    Example — string shorthand (user must exist)::

        session = client.embed.get_session(user="customer-42", ttl=7200)

    Example — full user dict (auto-creates if needed)::

        session = client.embed.get_session(
            user={
                "external_id": "customer-42",
                "email": "alice@customer.com",
                "first_name": "Alice",
            },
            access={
                "sources": ["src_sales"],
                "filters": {"region": ["APAC"]},
            },
            origin="https://app.customer.com",
        )
    """
    external_id, creation_body = _resolve_user_param(user)

    # ------------------------------------------------------------------
    # Step 1: Resolve user
    # ------------------------------------------------------------------
    if creation_body is not None:
        # Dict form — use idempotent PUT (get-or-create)
        resp = http.put(f"/users/external/{external_id}", json=creation_body)
        result = resp.json()
        user_id: str = result["id"]
        logger.debug(
            "Resolved user external_id=%s → id=%s (created=%s)",
            external_id, user_id, result.get("created", "unknown"),
        )
    else:
        # String shorthand — look up existing user by external_id
        resp = http.get("/users", params={"external_id": external_id, "limit": 1})
        data = resp.json().get("data", [])
        if not data:
            raise ValueError(
                f"User with external_id '{external_id}' not found. "
                "Pass a dict with at least 'external_id' and 'email' to "
                "create the user automatically. Example:\n"
                "  client.embed.get_session(\n"
                "      user={'external_id': 'cust-42', 'email': 'alice@example.com'},\n"
                "      ...\n"
                "  )"
            )
        user_id = data[0]["id"]
        logger.debug(
            "Looked up user external_id=%s → id=%s", external_id, user_id,
        )

    # ------------------------------------------------------------------
    # Step 2: Handle access policies
    # ------------------------------------------------------------------
    if access is not None:
        _sync_apply_access(http, user_id=user_id, access=access)

    # ------------------------------------------------------------------
    # Step 3: Create embed session
    # ------------------------------------------------------------------
    session_body: Dict[str, Any] = {"user_id": user_id, "ttl": ttl}
    if origin is not None:
        session_body["origin"] = origin

    resp = http.post("/embed/sessions", json=session_body)
    session = resp.json()

    # Enrich response with the external_id the caller passed in
    session["external_id"] = external_id

    logger.debug(
        "Created embed session for user_id=%s, expires_in=%s",
        user_id, session.get("expires_in"),
    )
    return session


def _sync_apply_access(
    http: SyncHTTPClient,
    *,
    user_id: str,
    access: Dict[str, Any],
) -> None:
    """Apply access policies to a user (sync).

    Handles both ``policy_ids`` references and inline specs.
    Uses atomic replace (PUT) to prevent stale policy accumulation.
    """
    all_policy_ids: List[str] = list(access.get("policy_ids") or [])

    # Inline spec — find-or-create a policy by deterministic content hash
    if access.get("sources") or access.get("filters"):
        spec_hash = _hash_access_spec(access)
        policy_name = f"sdk_auto_{spec_hash}"

        # Try to find an existing policy with this name
        resp = http.get("/access/policies", params={"name": policy_name})
        policies = resp.json().get("data", [])

        if policies:
            policy_id = policies[0]["id"]
            logger.debug("Reusing existing auto-policy %s (name=%s)", policy_id, policy_name)
        else:
            # Create a new policy
            policy_body = _build_policy_body(access, policy_name)
            resp = http.post("/access/policies", json=policy_body)
            policy_id = resp.json()["id"]
            logger.debug("Created auto-policy %s (name=%s)", policy_id, policy_name)

        all_policy_ids.append(policy_id)

    if not all_policy_ids:
        logger.debug("Empty access spec, skipping policy assignment")
        return

    # Atomically replace all policy assignments for the user
    http.put(
        f"/access/users/{user_id}/policies",
        json={"policy_ids": all_policy_ids},
    )
    logger.debug(
        "Replaced policies for user %s with %s", user_id, all_policy_ids,
    )


def sync_setup_policy(
    http: SyncHTTPClient,
    *,
    name: str,
    sources: Optional[List[str]] = None,
    row_filters: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    users: Optional[List[str]] = None,
) -> Policy:
    """Create a policy and optionally assign users in one call.

    Args:
        http: The synchronous HTTP client.
        name: Human-readable policy name.
        sources: List of source IDs to include in the policy scope.
        row_filters: Dict mapping column names to allowed values.
            Values can be a single string or a list of strings.
        description: Optional policy description.
        users: Optional list of user IDs (WorkOS or external) to assign.

    Returns:
        The created policy dict from the API.

    Example::

        policy = client.policies.setup(
            name="APAC Sales Team",
            sources=["src_abc", "src_def"],
            row_filters={"region": ["APAC"], "department": "Sales"},
            users=["user-1", "user-2"],
        )
    """
    body: Dict[str, Any] = {"name": name}
    if description is not None:
        body["description"] = description
    if sources:
        body["source_ids"] = list(sources)
    if row_filters:
        filters: List[Dict[str, Any]] = []
        for col, val in row_filters.items():
            if isinstance(val, list):
                filters.append({"column": col, "values": val})
            else:
                filters.append({"column": col, "values": [val]})
        body["row_filters"] = filters

    resp = http.post("/access/policies", json=body)
    policy = Policy.model_validate(resp.json())

    if users:
        http.post(
            f"/access/policies/{policy.id}/users",
            json={"user_ids": users},
        )
        logger.debug("Assigned %d users to policy %s", len(users), policy.id)

    return policy


# ---------------------------------------------------------------------------
# Async convenience methods
# ---------------------------------------------------------------------------


async def async_get_session(
    http: AsyncHTTPClient,
    *,
    user: Union[str, Dict[str, Any]],
    access: Optional[Dict[str, Any]] = None,
    origin: Optional[str] = None,
    ttl: int = 3600,
) -> Dict[str, Any]:
    """Async version of :func:`sync_get_session`.

    Identical logic and parameters — see :func:`sync_get_session` for full
    documentation.
    """
    external_id, creation_body = _resolve_user_param(user)

    # ------------------------------------------------------------------
    # Step 1: Resolve user
    # ------------------------------------------------------------------
    if creation_body is not None:
        resp = await http.put(f"/users/external/{external_id}", json=creation_body)
        result = resp.json()
        user_id: str = result["id"]
        logger.debug(
            "Resolved user external_id=%s → id=%s (created=%s)",
            external_id, user_id, result.get("created", "unknown"),
        )
    else:
        resp = await http.get("/users", params={"external_id": external_id, "limit": 1})
        data = resp.json().get("data", [])
        if not data:
            raise ValueError(
                f"User with external_id '{external_id}' not found. "
                "Pass a dict with at least 'external_id' and 'email' to "
                "create the user automatically. Example:\n"
                "  await client.embed.get_session(\n"
                "      user={'external_id': 'cust-42', 'email': 'alice@example.com'},\n"
                "      ...\n"
                "  )"
            )
        user_id = data[0]["id"]
        logger.debug(
            "Looked up user external_id=%s → id=%s", external_id, user_id,
        )

    # ------------------------------------------------------------------
    # Step 2: Handle access policies
    # ------------------------------------------------------------------
    if access is not None:
        await _async_apply_access(http, user_id=user_id, access=access)

    # ------------------------------------------------------------------
    # Step 3: Create embed session
    # ------------------------------------------------------------------
    session_body: Dict[str, Any] = {"user_id": user_id, "ttl": ttl}
    if origin is not None:
        session_body["origin"] = origin

    resp = await http.post("/embed/sessions", json=session_body)
    session = resp.json()

    session["external_id"] = external_id

    logger.debug(
        "Created embed session for user_id=%s, expires_in=%s",
        user_id, session.get("expires_in"),
    )
    return session


async def _async_apply_access(
    http: AsyncHTTPClient,
    *,
    user_id: str,
    access: Dict[str, Any],
) -> None:
    """Apply access policies to a user (async).

    Handles both ``policy_ids`` references and inline specs.
    Uses atomic replace (PUT) to prevent stale policy accumulation.
    """
    all_policy_ids: List[str] = list(access.get("policy_ids") or [])

    # Inline spec — find-or-create a policy by deterministic content hash
    if access.get("sources") or access.get("filters"):
        spec_hash = _hash_access_spec(access)
        policy_name = f"sdk_auto_{spec_hash}"

        resp = await http.get("/access/policies", params={"name": policy_name})
        policies = resp.json().get("data", [])

        if policies:
            policy_id = policies[0]["id"]
            logger.debug("Reusing existing auto-policy %s (name=%s)", policy_id, policy_name)
        else:
            policy_body = _build_policy_body(access, policy_name)
            resp = await http.post("/access/policies", json=policy_body)
            policy_id = resp.json()["id"]
            logger.debug("Created auto-policy %s (name=%s)", policy_id, policy_name)

        all_policy_ids.append(policy_id)

    if not all_policy_ids:
        logger.debug("Empty access spec, skipping policy assignment")
        return

    # Atomically replace all policy assignments for the user
    await http.put(
        f"/access/users/{user_id}/policies",
        json={"policy_ids": all_policy_ids},
    )
    logger.debug(
        "Replaced policies for user %s with %s", user_id, all_policy_ids,
    )


async def async_setup_policy(
    http: AsyncHTTPClient,
    *,
    name: str,
    sources: Optional[List[str]] = None,
    row_filters: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    users: Optional[List[str]] = None,
) -> Policy:
    """Async version of :func:`sync_setup_policy`.

    Identical logic and parameters — see :func:`sync_setup_policy` for full
    documentation.
    """
    body: Dict[str, Any] = {"name": name}
    if description is not None:
        body["description"] = description
    if sources:
        body["source_ids"] = list(sources)
    if row_filters:
        filters: List[Dict[str, Any]] = []
        for col, val in row_filters.items():
            if isinstance(val, list):
                filters.append({"column": col, "values": val})
            else:
                filters.append({"column": col, "values": [val]})
        body["row_filters"] = filters

    resp = await http.post("/access/policies", json=body)
    policy = Policy.model_validate(resp.json())

    if users:
        await http.post(
            f"/access/policies/{policy.id}/users",
            json={"user_ids": users},
        )
        logger.debug("Assigned %d users to policy %s", len(users), policy.id)

    return policy
