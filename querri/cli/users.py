"""querri users — manage organization users."""

from __future__ import annotations

from typing import Optional

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    handle_api_error,
    print_detail,
    print_id,
    print_json,
    print_success,
    print_table,
)

users_app = typer.Typer(
    name="users",
    help="Manage users in the organization.",
    no_args_is_help=True,
)


@users_app.command("list")
def list_users(
    ctx: typer.Context,
    limit: int = typer.Option(50, "--limit", "-n", help="Max results."),
    after: Optional[str] = typer.Option(None, "--after", help="Cursor for pagination."),
    external_id: Optional[str] = typer.Option(None, "--external-id", help="Filter by external ID."),
) -> None:
    """List users in the organization."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        page = client.users.list(limit=limit, after=after, external_id=external_id)
        items = list(page)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json([u.model_dump(mode="json") for u in items])
    elif obj.get("quiet"):
        for u in items:
            print_id(u.id)
    else:
        print_table(
            items,
            [("id", "ID"), ("email", "Email"), ("role", "Role"), ("external_id", "External ID")],
            ctx=ctx,
        )


@users_app.command("get")
def get_user(
    ctx: typer.Context,
    user_id: str = typer.Argument(help="User ID."),
) -> None:
    """Get user details."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        user = client.users.get(user_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(user)
    elif obj.get("quiet"):
        print_id(user.id)
    else:
        print_detail(
            user,
            [
                ("id", "ID"),
                ("email", "Email"),
                ("first_name", "First Name"),
                ("last_name", "Last Name"),
                ("role", "Role"),
                ("external_id", "External ID"),
                ("created_at", "Created"),
            ],
        )


@users_app.command("create")
def create_user(
    ctx: typer.Context,
    email: str = typer.Option(..., "--email", "-e", help="User email."),
    role: str = typer.Option("member", "--role", "-r", help="Role (member, admin)."),
    external_id: Optional[str] = typer.Option(None, "--external-id", help="External ID."),
    first_name: Optional[str] = typer.Option(None, "--first-name", help="First name."),
    last_name: Optional[str] = typer.Option(None, "--last-name", help="Last name."),
) -> None:
    """Create a new user."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        user = client.users.create(
            email=email,
            role=role,
            external_id=external_id,
            first_name=first_name,
            last_name=last_name,
        )
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(user)
    elif obj.get("quiet"):
        print_id(user.id)
    else:
        print_success(f"Created user {user.id} ({user.email})")


@users_app.command("delete")
def delete_user(
    ctx: typer.Context,
    user_id: str = typer.Argument(help="User ID."),
) -> None:
    """Delete a user."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.users.delete(user_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"id": user_id, "deleted": True})
    else:
        print_success(f"Deleted user {user_id}")
