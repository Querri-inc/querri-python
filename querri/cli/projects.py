"""querri projects — manage projects and runs."""

from __future__ import annotations

import time
from typing import Optional

import typer

from querri.cli._context import get_client
from querri.cli._output import (
    EXIT_SUCCESS,
    IS_INTERACTIVE,
    handle_api_error,
    print_detail,
    print_id,
    print_json,
    print_success,
    print_table,
)

projects_app = typer.Typer(
    name="projects",
    help="Manage projects — create, run, and track analysis pipelines.",
    no_args_is_help=True,
)


@projects_app.command("list")
def list_projects(
    ctx: typer.Context,
    limit: int = typer.Option(25, "--limit", "-n", help="Max results to return."),
    after: Optional[str] = typer.Option(None, "--after", help="Cursor for pagination."),
) -> None:
    """List projects in the organization."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        page = client.projects.list(limit=limit, after=after)
        items = list(page)
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
            [("id", "ID"), ("name", "Name"), ("status", "Status"), ("updated_at", "Updated")],
            ctx=ctx,
        )


@projects_app.command("get")
def get_project(
    ctx: typer.Context,
    project_id: str = typer.Argument(help="Project ID."),
) -> None:
    """Get project details."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        project = client.projects.get(project_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(project)
    elif obj.get("quiet"):
        print_id(project.id)
    else:
        print_detail(
            project,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("description", "Description"),
                ("status", "Status"),
                ("step_count", "Steps"),
                ("chat_count", "Chats"),
                ("created_by", "Created By"),
                ("created_at", "Created"),
                ("updated_at", "Updated"),
            ],
        )


@projects_app.command("create")
def create_project(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", "-n", help="Project name."),
    user_id: str = typer.Option(..., "--user-id", help="Owner user ID."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Description."),
) -> None:
    """Create a new project."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        project = client.projects.create(name=name, user_id=user_id, description=description)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(project)
    elif obj.get("quiet"):
        print_id(project.id)
    else:
        print_success(f"Created project {project.id}")
        print_detail(project, [("id", "ID"), ("name", "Name"), ("status", "Status")])


@projects_app.command("update")
def update_project(
    ctx: typer.Context,
    project_id: str = typer.Argument(help="Project ID."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description."),
) -> None:
    """Update a project."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        project = client.projects.update(project_id, name=name, description=description)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(project)
    elif obj.get("quiet"):
        print_id(project.id)
    else:
        print_success(f"Updated project {project_id}")


@projects_app.command("delete")
def delete_project(
    ctx: typer.Context,
    project_id: str = typer.Argument(help="Project ID."),
) -> None:
    """Delete a project."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.projects.delete(project_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"id": project_id, "deleted": True})
    else:
        print_success(f"Deleted project {project_id}")


@projects_app.command("run")
def run_project(
    ctx: typer.Context,
    project_id: str = typer.Argument(help="Project ID."),
    user_id: str = typer.Option(..., "--user-id", help="User ID to run as."),
    wait: bool = typer.Option(False, "--wait", "-w", help="Block until run completes."),
    timeout: int = typer.Option(600, "--timeout", help="Max seconds to wait (with --wait)."),
) -> None:
    """Run a project pipeline."""
    obj = ctx.ensure_object(dict)
    is_interactive = obj.get("interactive", IS_INTERACTIVE)
    client = get_client(ctx)
    try:
        result = client.projects.run(project_id, user_id=user_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if wait:
        import sys as _sys

        elapsed = 0
        try:
            while True:
                status = client.projects.run_status(project_id)
                if not status.is_running:
                    break
                if elapsed >= timeout:
                    if obj.get("json"):
                        from querri.cli._output import print_json_error
                        print_json_error("timeout", f"Run did not complete within {timeout}s", 1)
                    else:
                        from querri.cli._output import print_error
                        print_error(f"Run did not complete within {timeout}s")
                    raise typer.Exit(code=1)
                if is_interactive:
                    _sys.stderr.write(f"\r⏳ Waiting... {elapsed}s elapsed (status: {status.status})")
                    _sys.stderr.flush()
                time.sleep(2)
                elapsed += 2
        except Exception as exc:
            if isinstance(exc, (typer.Exit, SystemExit)):
                raise
            raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

        if is_interactive:
            _sys.stderr.write("\r" + " " * 60 + "\r")  # clear spinner line

        if obj.get("json"):
            print_json(status)
        elif obj.get("quiet"):
            print_id(project_id)
        else:
            print_success(f"Run completed: {status.status}")
    else:
        if obj.get("json"):
            print_json(result)
        elif obj.get("quiet"):
            print_id(result.run_id)
        else:
            print_success(f"Run started: {result.run_id} (status: {result.status})")


@projects_app.command("run-status")
def run_status(
    ctx: typer.Context,
    project_id: str = typer.Argument(help="Project ID."),
) -> None:
    """Check the run status of a project."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        status = client.projects.run_status(project_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(status)
    else:
        print_detail(
            status,
            [("id", "ID"), ("status", "Status"), ("is_running", "Running")],
        )


@projects_app.command("run-cancel")
def run_cancel(
    ctx: typer.Context,
    project_id: str = typer.Argument(help="Project ID."),
) -> None:
    """Cancel a running project."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        result = client.projects.run_cancel(project_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Cancelled run for project {project_id}")
