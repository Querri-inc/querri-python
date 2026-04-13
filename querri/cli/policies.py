"""querri policy — manage access control policies."""

from __future__ import annotations

import json
import sys

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    handle_api_error,
    print_detail,
    print_error,
    print_id,
    print_json,
    print_success,
    print_table,
)

policies_app = typer.Typer(
    name="policies",
    help="Manage fine-grained access control policies.",
    no_args_is_help=True,
)


@policies_app.command("list")
def list_policies(
    ctx: typer.Context,
    name: str | None = typer.Option(None, "--name", help="Filter by name."),
) -> None:
    """List access policies."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.policies.list(name=name)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json([p.model_dump(mode="json") for p in items])
    elif obj.get("quiet"):
        for p in items:
            print_id(p.id)
    else:
        print_table(
            items,
            [("id", "ID"), ("name", "Name"), ("user_count", "Users"), ("updated_at", "Updated")],
            ctx=ctx,
        )


@policies_app.command("get")
def get_policy(
    ctx: typer.Context,
    policy_id: str | None = typer.Argument(default=None, help="Policy ID."),
) -> None:
    """Get policy details."""
    if not policy_id:
        if sys.stdin.isatty():
            policy_id = input("Policy ID: ").strip()
            if not policy_id:
                print_error("Policy ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument POLICY_ID. Usage: querri policy get POLICY_ID")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        policy = client.policies.get(policy_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(policy)
    elif obj.get("quiet"):
        print_id(policy.id)
    else:
        print_detail(
            policy,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("description", "Description"),
                ("source_ids", "Sources"),
                ("row_filters", "Row Filters"),
                ("user_count", "Users"),
                ("assigned_user_ids", "Assigned Users"),
                ("created_at", "Created"),
                ("updated_at", "Updated"),
            ],
        )


@policies_app.command("new")
def new_policy(
    ctx: typer.Context,
    name: str | None = typer.Option(None, "--name", "-n", help="Policy name."),
    description: str | None = typer.Option(None, "--description", "-d", help="Description."),
    source_ids: str | None = typer.Option(None, "--source-ids", help="Comma-separated source IDs."),
    row_filters: str | None = typer.Option(None, "--row-filters", help="JSON array of row filter objects."),
) -> None:
    """Create a new access policy."""
    if not name:
        if sys.stdin.isatty():
            name = input("Policy name: ").strip()
            if not name:
                print_error("Policy name is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required option --name. Usage: querri policy new --name NAME")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    source_list = [s.strip() for s in source_ids.split(",")] if source_ids else None
    filters = None
    if row_filters:
        try:
            filters = json.loads(row_filters)
        except json.JSONDecodeError as exc:
            print_error(f"Invalid JSON for --row-filters: {exc}")
            raise typer.Exit(code=1)

    try:
        policy = client.policies.create(
            name=name,
            description=description,
            source_ids=source_list,
            row_filters=filters,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(policy)
    elif obj.get("quiet"):
        print_id(policy.id)
    else:
        print_success(f"Created policy {policy.id} ({policy.name})")


@policies_app.command("update")
def update_policy(
    ctx: typer.Context,
    policy_id: str | None = typer.Argument(default=None, help="Policy ID."),
    name: str | None = typer.Option(None, "--name", "-n", help="New name."),
    description: str | None = typer.Option(None, "--description", "-d", help="New description."),
    source_ids: str | None = typer.Option(None, "--source-ids", help="Comma-separated source IDs."),
    row_filters: str | None = typer.Option(None, "--row-filters", help="JSON array of row filter objects."),
) -> None:
    """Update an access policy."""
    if not policy_id:
        if sys.stdin.isatty():
            policy_id = input("Policy ID: ").strip()
            if not policy_id:
                print_error("Policy ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument POLICY_ID. Usage: querri policy update POLICY_ID")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    source_list = [s.strip() for s in source_ids.split(",")] if source_ids else None
    filters = None
    if row_filters:
        try:
            filters = json.loads(row_filters)
        except json.JSONDecodeError as exc:
            print_error(f"Invalid JSON for --row-filters: {exc}")
            raise typer.Exit(code=1)

    try:
        client.policies.update(
            policy_id,
            name=name,
            description=description,
            source_ids=source_list,
            row_filters=filters,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"id": policy_id, "updated": True})
    else:
        print_success(f"Updated policy {policy_id}")


@policies_app.command("delete")
def delete_policy(
    ctx: typer.Context,
    policy_id: str | None = typer.Argument(default=None, help="Policy ID."),
) -> None:
    """Delete an access policy."""
    if not policy_id:
        if sys.stdin.isatty():
            policy_id = input("Policy ID: ").strip()
            if not policy_id:
                print_error("Policy ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument POLICY_ID. Usage: querri policy delete POLICY_ID")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.policies.delete(policy_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"id": policy_id, "deleted": True})
    else:
        print_success(f"Deleted policy {policy_id}")


@policies_app.command("assign")
def assign_users(
    ctx: typer.Context,
    policy_id: str | None = typer.Argument(default=None, help="Policy ID."),
    user_ids: str | None = typer.Option(None, "--user-ids", help="Comma-separated user IDs."),
) -> None:
    """Assign users to an access policy."""
    if not policy_id:
        if sys.stdin.isatty():
            policy_id = input("Policy ID: ").strip()
            if not policy_id:
                print_error("Policy ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument POLICY_ID. Usage: querri policy assign POLICY_ID --user-ids USER_IDS")
            raise typer.Exit(code=1)
    if not user_ids:
        if sys.stdin.isatty():
            user_ids = input("User IDs (comma-separated): ").strip()
            if not user_ids:
                print_error("User IDs are required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required option --user-ids. Usage: querri policy assign POLICY_ID --user-ids USER_IDS")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    user_list = [u.strip() for u in user_ids.split(",")]

    try:
        result = client.policies.assign_users(policy_id, user_ids=user_list)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Assigned {len(user_list)} user(s) to policy {policy_id}")


@policies_app.command("remove")
def remove_user(
    ctx: typer.Context,
    policy_id: str | None = typer.Argument(default=None, help="Policy ID."),
    user_id: str | None = typer.Argument(default=None, help="User ID to remove."),
) -> None:
    """Remove a user from an access policy."""
    if not policy_id:
        if sys.stdin.isatty():
            policy_id = input("Policy ID: ").strip()
            if not policy_id:
                print_error("Policy ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument POLICY_ID. Usage: querri policy remove POLICY_ID USER_ID")
            raise typer.Exit(code=1)
    if not user_id:
        if sys.stdin.isatty():
            user_id = input("User ID: ").strip()
            if not user_id:
                print_error("User ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument USER_ID. Usage: querri policy remove POLICY_ID USER_ID")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.policies.remove_user(policy_id, user_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"policy_id": policy_id, "user_id": user_id, "removed": True})
    else:
        print_success(f"Removed user {user_id} from policy {policy_id}")


@policies_app.command("resolve")
def resolve_access(
    ctx: typer.Context,
    user_id: str | None = typer.Option(None, "--user-id", help="User ID."),
    source_id: str | None = typer.Option(None, "--source-id", help="Source ID."),
) -> None:
    """Resolve effective access for a user on a source."""
    if not user_id:
        if sys.stdin.isatty():
            user_id = input("User ID: ").strip()
            if not user_id:
                print_error("User ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required option --user-id. Usage: querri policy resolve --user-id USER_ID --source-id SOURCE_ID")
            raise typer.Exit(code=1)
    if not source_id:
        if sys.stdin.isatty():
            source_id = input("Source ID: ").strip()
            if not source_id:
                print_error("Source ID is required.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required option --source-id. Usage: querri policy resolve --user-id USER_ID --source-id SOURCE_ID")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.policies.resolve(user_id=user_id, source_id=source_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_detail(
            result,
            [
                ("user_id", "User ID"),
                ("source_id", "Source ID"),
                ("source_is_access_controlled", "Access Controlled"),
                ("effective_access", "Effective Access"),
                ("where_clause", "Where Clause"),
            ],
        )


@policies_app.command("columns")
def list_columns(
    ctx: typer.Context,
    source_id: str | None = typer.Option(None, "--source-id", help="Filter by source ID."),
) -> None:
    """List columns available for access policies."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.policies.columns(source_id=source_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json([sc.model_dump(mode="json") for sc in items])
    else:
        for sc in items:
            print(f"\n{sc.source_name} ({sc.source_id}):")
            print_table(
                [{"name": c.name, "type": c.type} for c in sc.columns],
                [("name", "Column"), ("type", "Type")],
                ctx=ctx,
            )
