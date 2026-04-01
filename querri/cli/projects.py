"""querri project — manage projects with workspace state."""

from __future__ import annotations

import sys
import time
from typing import Optional

import typer

from querri.cli._context import (
    get_client,
    resolve_project_id,
    resolve_user_id,
    _get_profile,
    _save_profile,
)
from querri.cli._output import (
    EXIT_SUCCESS,
    IS_INTERACTIVE,
    handle_api_error,
    print_detail,
    print_error,
    print_id,
    print_json,
    print_success,
    print_table,
)

projects_app = typer.Typer(
    name="project",
    help="Manage projects — create, select, and run analysis pipelines.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ---------------------------------------------------------------------------
# querri project new
# ---------------------------------------------------------------------------


@projects_app.command("new")
def new_project(
    ctx: typer.Context,
    name: Optional[str] = typer.Argument(None, help="Project name."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Description."),
) -> None:
    """Create a new project and set it as active.

    Example: querri project new "Sales Analysis"
    """
    obj = ctx.ensure_object(dict)

    # Interactive prompt if name not provided
    if not name:
        if sys.stdin.isatty():
            name = input("Project name: ").strip()
            if not name:
                print_error("Project name is required.")
                raise typer.Exit(code=1)
            if description is None:
                desc = input("Description (optional): ").strip()
                if desc:
                    description = desc
        else:
            print_error("Project name is required.")
            raise typer.Exit(code=1)

    client = get_client(ctx)
    user_id = resolve_user_id(ctx)

    try:
        project = client.projects.create(name=name, user_id=user_id, description=description)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    # Auto-select the new project
    profile = _get_profile(ctx)
    if profile:
        profile.active_project_id = project.id
        profile.active_project_name = name
        profile.active_chat_id = ""  # reset chat for new project
        _save_profile(ctx, profile)

    if obj.get("json"):
        print_json(project)
    elif obj.get("quiet"):
        print_id(project.id)
    else:
        print_success(f"Created and selected project: {name} ({project.id})")


# ---------------------------------------------------------------------------
# querri project select
# ---------------------------------------------------------------------------


@projects_app.command("select")
def select_project(
    ctx: typer.Context,
    name_or_id: Optional[str] = typer.Argument(None, help="Project name (fuzzy) or UUID."),
) -> None:
    """Set the active project for subsequent commands.

    Accepts a project UUID or a name search string. If the name matches
    multiple projects, shows a picker. Run with no arguments to pick
    from all projects interactively.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    # If no argument, show interactive picker with all projects
    if not name_or_id:
        if not sys.stdin.isatty():
            print_error("Project name or ID is required in non-interactive mode.")
            raise typer.Exit(code=1)

        try:
            page = client.projects.list(limit=50)
            all_projects = list(page)
        except Exception as exc:
            raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

        if not all_projects:
            print_error("No projects found. Create one with 'querri project new'.")
            raise typer.Exit(code=1)

        profile = _get_profile(ctx)
        active_id = profile.active_project_id if profile else ""

        print("\nProjects:\n", file=sys.stderr)
        for i, p in enumerate(all_projects, 1):
            marker = " (active)" if p.id == active_id else ""
            print(f"  [{i}] {p.name}{marker}", file=sys.stderr)
        print(file=sys.stderr)

        while True:
            try:
                raw = input("Select project: ").strip()
            except (EOFError, KeyboardInterrupt):
                print(file=sys.stderr)
                raise typer.Exit(code=0)
            if not raw:
                continue
            try:
                idx = int(raw)
                if 1 <= idx <= len(all_projects):
                    project = all_projects[idx - 1]
                    break
            except ValueError:
                pass
            print(f"  Enter 1-{len(all_projects)}.", file=sys.stderr)

        # Save and report
        if profile:
            profile.active_project_id = project.id
            profile.active_project_name = project.name
            profile.active_chat_id = ""
            _save_profile(ctx, profile)

        if obj.get("json"):
            print_json({"active_project": {"id": project.id, "name": project.name}})
        elif not obj.get("quiet"):
            print_success(f"Selected project: {project.name} ({project.id})")
        return

    # Try as UUID first (UUIDs are 32+ hex chars or have dashes)
    project = None
    if len(name_or_id) >= 20 or "-" in name_or_id:
        try:
            project = client.projects.get(name_or_id)
        except Exception:
            pass  # Not a valid UUID, fall through to name search

    # Name search
    if project is None:
        try:
            page = client.projects.list(limit=100)
            all_projects = list(page)
        except Exception as exc:
            raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

        query = name_or_id.lower()
        matches = [p for p in all_projects if query in p.name.lower()]

        if not matches:
            print_error(f"No project matching '{name_or_id}'.")
            raise typer.Exit(code=1)
        elif len(matches) == 1:
            project = matches[0]
        else:
            # Multiple matches — show picker
            if obj.get("json"):
                print_json([{"id": p.id, "name": p.name} for p in matches])
                return
            print(f"\nMultiple projects match '{name_or_id}':\n", file=__import__("sys").stderr)
            for i, p in enumerate(matches, 1):
                print(f"  [{i}] {p.name} ({p.id})", file=__import__("sys").stderr)
            print(file=__import__("sys").stderr)
            while True:
                try:
                    raw = input("Select [1]: ").strip() or "1"
                except (EOFError, KeyboardInterrupt):
                    raw = "1"
                try:
                    idx = int(raw)
                    if 1 <= idx <= len(matches):
                        project = matches[idx - 1]
                        break
                except ValueError:
                    pass
                print(f"  Enter 1-{len(matches)}.", file=__import__("sys").stderr)

    # Save selection
    profile = _get_profile(ctx)
    if profile:
        profile.active_project_id = project.id
        profile.active_project_name = project.name
        profile.active_chat_id = ""  # reset chat when switching projects
        _save_profile(ctx, profile)

    if obj.get("json"):
        print_json({"active_project": {"id": project.id, "name": project.name}})
    elif not obj.get("quiet"):
        print_success(f"Selected project: {project.name} ({project.id})")


# ---------------------------------------------------------------------------
# querri project list
# ---------------------------------------------------------------------------


@projects_app.command("list")
def list_projects(
    ctx: typer.Context,
    limit: int = typer.Option(25, "--limit", "-n", help="Max results to return."),
    after: Optional[str] = typer.Option(None, "--after", help="Cursor for pagination."),
) -> None:
    """List projects in the organization."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    # Get active project for marking
    profile = _get_profile(ctx)
    active_id = profile.active_project_id if profile else ""

    try:
        page = client.projects.list(limit=limit, after=after)
        items = list(page)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        data = []
        for p in items:
            d = p.model_dump(mode="json")
            d["active"] = p.id == active_id
            data.append(d)
        print_json(data)
    elif obj.get("quiet"):
        for p in items:
            print_id(p.id)
    else:
        # Add active marker to display
        rows = []
        for p in items:
            marker = " *" if p.id == active_id else ""
            rows.append({
                "id": p.id,
                "name": f"{p.name}{marker}",
                "status": getattr(p, "status", ""),
                "updated_at": getattr(p, "updated_at", ""),
            })
        print_table(
            rows,
            [("id", "ID"), ("name", "Name"), ("status", "Status"), ("updated_at", "Updated")],
            ctx=ctx,
        )
        if active_id:
            import sys
            print(f"\n  * = active project", file=sys.stderr)


# ---------------------------------------------------------------------------
# querri project get
# ---------------------------------------------------------------------------


@projects_app.command("get")
def get_project(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project ID (default: active project)."),
) -> None:
    """Get project details."""
    obj = ctx.ensure_object(dict)
    pid = project_id or resolve_project_id(ctx)
    client = get_client(ctx)
    try:
        project = client.projects.get(pid)
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


# ---------------------------------------------------------------------------
# querri project create (alias for new, keeps --name style for scripts)
# ---------------------------------------------------------------------------


@projects_app.command("create", hidden=True)
def create_project(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", "-n", help="Project name."),
    user_id: Optional[str] = typer.Option(None, "--user-id", help="Owner user ID."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Description."),
) -> None:
    """Create a new project (scripting interface)."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    uid = user_id or resolve_user_id(ctx)

    try:
        project = client.projects.create(name=name, user_id=uid, description=description)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    # Auto-select
    profile = _get_profile(ctx)
    if profile:
        profile.active_project_id = project.id
        profile.active_project_name = name
        profile.active_chat_id = ""
        _save_profile(ctx, profile)

    if obj.get("json"):
        print_json(project)
    elif obj.get("quiet"):
        print_id(project.id)
    else:
        print_success(f"Created and selected project: {name} ({project.id})")


# ---------------------------------------------------------------------------
# querri project update
# ---------------------------------------------------------------------------


@projects_app.command("update")
def update_project(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project ID (default: active project)."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description."),
) -> None:
    """Update a project."""
    obj = ctx.ensure_object(dict)
    pid = project_id or resolve_project_id(ctx)
    client = get_client(ctx)
    try:
        project = client.projects.update(pid, name=name, description=description)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    # Update stored name if this is the active project
    if name:
        profile = _get_profile(ctx)
        if profile and profile.active_project_id == pid:
            profile.active_project_name = name
            _save_profile(ctx, profile)

    if obj.get("json"):
        print_json(project)
    elif obj.get("quiet"):
        print_id(project.id)
    else:
        print_success(f"Updated project {pid}")


# ---------------------------------------------------------------------------
# querri project delete
# ---------------------------------------------------------------------------


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

    # Clear state if deleting active project
    profile = _get_profile(ctx)
    if profile and profile.active_project_id == project_id:
        profile.active_project_id = ""
        profile.active_project_name = ""
        profile.active_chat_id = ""
        _save_profile(ctx, profile)

    if obj.get("json"):
        print_json({"id": project_id, "deleted": True})
    else:
        print_success(f"Deleted project {project_id}")


# ---------------------------------------------------------------------------
# querri project run
# ---------------------------------------------------------------------------


@projects_app.command("run")
def run_project(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project ID (default: active project)."),
    user_id: Optional[str] = typer.Option(None, "--user-id", help="User ID to run as."),
    wait: bool = typer.Option(False, "--wait", "-w", help="Block until run completes."),
    timeout: int = typer.Option(600, "--timeout", help="Max seconds to wait (with --wait)."),
) -> None:
    """Run a project pipeline."""
    obj = ctx.ensure_object(dict)
    is_interactive = obj.get("interactive", IS_INTERACTIVE)
    pid = project_id or resolve_project_id(ctx)
    uid = user_id or resolve_user_id(ctx)
    client = get_client(ctx)

    try:
        result = client.projects.run(pid, user_id=uid)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if wait:
        import sys as _sys

        elapsed = 0
        try:
            while True:
                status = client.projects.run_status(pid)
                if not status.is_running:
                    break
                if elapsed >= timeout:
                    if obj.get("json"):
                        from querri.cli._output import print_json_error
                        print_json_error("timeout", f"Run did not complete within {timeout}s", 1)
                    else:
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
            _sys.stderr.write("\r" + " " * 60 + "\r")

        if obj.get("json"):
            print_json(status)
        elif obj.get("quiet"):
            print_id(pid)
        else:
            print_success(f"Run completed: {status.status}")
    else:
        if obj.get("json"):
            print_json(result)
        elif obj.get("quiet"):
            print_id(result.run_id)
        else:
            print_success(f"Run started: {result.run_id} (status: {result.status})")


# ---------------------------------------------------------------------------
# querri project run-status / run-cancel
# ---------------------------------------------------------------------------


@projects_app.command("run-status")
def run_status(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(None, help="Project ID (default: active project)."),
) -> None:
    """Check the run status of a project."""
    obj = ctx.ensure_object(dict)
    pid = project_id or resolve_project_id(ctx)
    client = get_client(ctx)
    try:
        status = client.projects.run_status(pid)
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
    project_id: Optional[str] = typer.Argument(None, help="Project ID (default: active project)."),
) -> None:
    """Cancel a running project."""
    obj = ctx.ensure_object(dict)
    pid = project_id or resolve_project_id(ctx)
    client = get_client(ctx)
    try:
        result = client.projects.run_cancel(pid)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(result)
    else:
        print_success(f"Cancelled run for project {pid}")


# ---------------------------------------------------------------------------
# querri project add-source
# ---------------------------------------------------------------------------


@projects_app.command("add-source")
def add_source(
    ctx: typer.Context,
    source_id: str = typer.Argument(help="Source UUID to add to the project."),
    project_id: Optional[str] = typer.Argument(None, help="Project ID (default: active project)."),
) -> None:
    """Add a data source to the active project.

    Sends a <load> command that triggers the project's source loading
    pipeline, which adds the source as a step and runs processing.

    Example: querri project add-source 18806a44-1d6f-4bbf-94b4-628b112890d6
    """
    obj = ctx.ensure_object(dict)
    is_json = obj.get("json", False)
    is_interactive = obj.get("interactive", IS_INTERACTIVE)
    pid = project_id or resolve_project_id(ctx)
    uid = resolve_user_id(ctx)
    client = get_client(ctx)

    # Create a chat for the source load operation and save as active
    try:
        chat = client.projects.chats.create(pid)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json))

    profile = _get_profile(ctx)
    if profile:
        profile.active_chat_id = chat.id
        _save_profile(ctx, profile)

    # Use the <load> format that the agent loop recognizes
    prompt = f"<load>{source_id}</load>"

    if is_interactive and not is_json:
        print(f"  Adding source {source_id} to project...", file=sys.stderr)

    try:
        stream = client.projects.chats.stream(
            pid, chat.id, prompt=prompt, user_id=uid,
        )
        # Consume the stream to completion
        text_parts: list[str] = []
        for event in stream.events():
            if event.event_type == "text-delta" and event.text:
                text_parts.append(event.text)
            elif event.event_type == "error":
                print_error(f"Error: {event.error}")
                raise typer.Exit(code=1)
    except Exception as exc:
        if isinstance(exc, (typer.Exit, SystemExit)):
            raise
        raise typer.Exit(code=handle_api_error(exc, is_json=is_json))

    response_text = "".join(text_parts)

    if is_json:
        print_json({
            "source_id": source_id,
            "project_id": pid,
            "status": "added",
            "response": response_text,
        })
    else:
        print_success(f"Added source {source_id} to project")
        if response_text.strip():
            print(response_text)
