"""querri files — manage file uploads."""

from __future__ import annotations

import glob as globmod
from pathlib import Path
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

files_app = typer.Typer(
    name="files",
    help="Upload, list, and manage files.",
    no_args_is_help=True,
)


@files_app.command("list")
def list_files(
    ctx: typer.Context,
) -> None:
    """List uploaded files."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = client.files.list()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json([f.model_dump(mode="json") for f in items])
    elif obj.get("quiet"):
        for f in items:
            print_id(f.id)
    else:
        print_table(
            items,
            [("id", "ID"), ("name", "Name"), ("size", "Size"), ("content_type", "Type"), ("created_at", "Created")],
            ctx=ctx,
        )


@files_app.command("get")
def get_file(
    ctx: typer.Context,
    file_id: str = typer.Argument(help="File ID."),
) -> None:
    """Get file details."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        file = client.files.get(file_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json(file)
    elif obj.get("quiet"):
        print_id(file.id)
    else:
        print_detail(
            file,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("size", "Size"),
                ("content_type", "Content Type"),
                ("created_by", "Created By"),
                ("created_at", "Created"),
            ],
        )


@files_app.command("upload")
def upload_file(
    ctx: typer.Context,
    path: str = typer.Argument(help="File path or glob pattern (e.g. '*.csv')."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Override file name."),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Add uploaded file(s) as source(s) to this project."),
) -> None:
    """Upload a file (supports glob patterns for batch upload).

    When --project is provided, each uploaded file is also added as a data
    source to the specified project, triggering execution automatically.

    Path validation: resolves to absolute path, checks file exists and is a
    regular file (no symlinks to sensitive paths).
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    # Expand glob patterns
    matches = sorted(globmod.glob(path))
    if not matches:
        # Try as literal path
        resolved = Path(path).resolve()
        if not resolved.exists():
            from querri.cli._output import print_error
            if obj.get("json"):
                from querri.cli._output import print_json_error
                print_json_error("validation_error", f"File not found: {path}", 1)
            else:
                print_error(f"File not found: {path}")
            raise typer.Exit(code=1)
        matches = [str(resolved)]

    results = []
    for match in matches:
        file_path = Path(match).resolve()

        # Security: reject non-regular files (R18)
        if not file_path.is_file():
            from querri.cli._output import print_error
            print_error(f"Skipping non-regular file: {match}")
            continue

        try:
            uploaded = client.files.upload(
                str(file_path),
                name=name if len(matches) == 1 else None,
            )
            results.append(uploaded)
        except Exception as exc:
            raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    # Optionally add each uploaded file to a project
    source_results = []
    if project:
        for f in results:
            try:
                source_resp = client.projects.add_source(project, f.id)
                source_results.append(source_resp)
            except Exception as exc:
                raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        if project and source_results:
            output = []
            for f, sr in zip(results, source_results):
                entry = f.model_dump(mode="json") if hasattr(f, "model_dump") else {"id": f.id, "name": f.name}
                entry["source"] = sr.model_dump(mode="json") if hasattr(sr, "model_dump") else {"step_id": sr.step_id, "project_id": sr.project_id, "status": sr.status}
                output.append(entry)
            print_json(output[0] if len(output) == 1 else output)
        elif len(results) == 1:
            print_json(results[0])
        else:
            print_json([f.model_dump(mode="json") for f in results])
    elif obj.get("quiet"):
        for f in results:
            print_id(f.id)
    else:
        for f in results:
            print_success(f"Uploaded {f.name} → {f.id}")
        if project and source_results:
            for sr in source_results:
                print_success(f"Added to project {sr.project_id} → step {sr.step_id} ({sr.status})")


@files_app.command("delete")
def delete_file(
    ctx: typer.Context,
    file_id: str = typer.Argument(help="File ID."),
) -> None:
    """Delete a file."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.files.delete(file_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json")))

    if obj.get("json"):
        print_json({"id": file_id, "deleted": True})
    else:
        print_success(f"Deleted file {file_id}")
