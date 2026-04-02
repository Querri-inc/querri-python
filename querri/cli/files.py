"""querri file — manage file uploads."""

from __future__ import annotations

import glob as globmod
import sys
from pathlib import Path
from typing import Optional

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
    file_id: Optional[str] = typer.Argument(default=None, help="File ID."),
) -> None:
    """Get file details."""
    if file_id is None:
        if sys.stdin.isatty():
            file_id = input("File ID: ").strip()
            if not file_id:
                print_error("File ID cannot be empty.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument <FILE_ID>. Usage: querri file get <FILE_ID>")
            raise typer.Exit(code=1)
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
                ("row_count", "Rows"),
                ("columns", "Columns"),
                ("created_by", "Created By"),
                ("created_at", "Created"),
            ],
        )


@files_app.command("upload")
def upload_file(
    ctx: typer.Context,
    path: Optional[str] = typer.Argument(default=None, help="File path or glob pattern (e.g. '*.csv')."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Override file name."),
) -> None:
    """Upload a file (supports glob patterns for batch upload).

    After uploading, use ``querri data add-source <id>`` to add the
    file as a data source to your active project.
    """
    if path is None:
        if sys.stdin.isatty():
            path = input("File path: ").strip()
            if not path:
                print_error("File path cannot be empty.")
                raise typer.Exit(code=1)
            resolved = Path(path).resolve()
            if not resolved.exists():
                print_error(f"File not found: {path}")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument <PATH>. Usage: querri file upload <PATH>")
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)

    # Expand glob patterns
    matches = sorted(globmod.glob(path))
    if not matches:
        resolved = Path(path).resolve()
        if not resolved.exists():
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

        if not file_path.is_file():
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

    if obj.get("json"):
        if len(results) == 1:
            print_json(results[0])
        else:
            print_json([f.model_dump(mode="json") for f in results])
    elif obj.get("quiet"):
        for f in results:
            print_id(f.id)
    else:
        for f in results:
            print_success(f"Uploaded {f.name} → {f.id}")
        if results:
            print(
                f"\nTo add to your project: querri project add-source {results[0].id}",
                file=sys.stderr,
            )


@files_app.command("delete")
def delete_file(
    ctx: typer.Context,
    file_id: Optional[str] = typer.Argument(default=None, help="File ID."),
) -> None:
    """Delete a file."""
    if file_id is None:
        if sys.stdin.isatty():
            file_id = input("File ID: ").strip()
            if not file_id:
                print_error("File ID cannot be empty.")
                raise typer.Exit(code=1)
        else:
            print_error("Missing required argument <FILE_ID>. Usage: querri file delete <FILE_ID>")
            raise typer.Exit(code=1)
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
