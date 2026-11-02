"""querri file — manage file uploads."""

from __future__ import annotations

import glob as globmod
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from querri.cli._context import get_client

if TYPE_CHECKING:
    from querri._client import Querri
    from querri.types.file import File
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
    limit: int = typer.Option(25, "--limit", "-l", help="Results fetched per page."),
    after: str | None = typer.Option(None, "--after", help="Cursor to start from."),
) -> None:
    """List uploaded files (fetches all pages)."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        items = list(client.files.list(limit=limit, after=after))
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json([f.model_dump(mode="json") for f in items])
    elif obj.get("quiet"):
        for f in items:
            print_id(f.id)
    else:
        print_table(
            items,
            [
                ("id", "ID"),
                ("name", "Name"),
                ("size", "Size"),
                ("content_type", "Type"),
                ("created_at", "Created"),
            ],
            ctx=ctx,
        )


@files_app.command("get")
def get_file(
    ctx: typer.Context,
    file_id: str | None = typer.Argument(default=None, help="File ID."),
) -> None:
    """Get file details."""
    if file_id is None:
        if sys.stdin.isatty():
            file_id = input("File ID: ").strip()
            if not file_id:
                print_error("File ID cannot be empty.")
                raise typer.Exit(code=1)
        else:
            print_error(
                "Missing required argument <FILE_ID>. Usage: querri file get <FILE_ID>"
            )
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        file = client.files.get(file_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

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
    path: str | None = typer.Argument(
        default=None, help="File path or glob pattern (e.g. '*.csv')."
    ),
    name: str | None = typer.Option(None, "--name", "-n", help="Override file name."),
    wait: bool = typer.Option(
        False,
        "--wait",
        help="Block until every upload finishes processing and is queryable.",
    ),
    timeout: float = typer.Option(
        900.0, "--timeout", help="Seconds to wait per batch with --wait."
    ),
    concurrency: int = typer.Option(
        1,
        "--concurrency",
        "-c",
        min=1,
        max=16,
        help="Parallel uploads. The server parses off a queue, so this bounds "
        "how many files are in flight, not how hard it is hit.",
    ),
) -> None:
    """Upload a file (supports glob patterns for batch upload).

    Uploads land in the active workspace (``querri workspace use``, or
    ``--workspace``); with none set they land in your personal workspace.

    An upload returns as soon as the bytes arrive — parsing happens afterwards
    on a queue, and the file is not queryable until it finishes. ``--wait``
    blocks until it is, and reports anything that failed rather than leaving you
    to discover it later.
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
            print_error(
                "Missing required argument <PATH>. Usage: querri file upload <PATH>"
            )
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

    paths = []
    for match in matches:
        file_path = Path(match).resolve()
        if not file_path.is_file():
            print_error(f"Skipping non-regular file: {match}")
            continue
        paths.append(file_path)

    def _upload(file_path: Path) -> File:
        return client.files.upload(
            str(file_path), name=name if len(matches) == 1 else None
        )

    results: list[File] = []
    if concurrency > 1 and len(paths) > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [(fp, pool.submit(_upload, fp)) for fp in paths]
            for fp, fut in futures:
                try:
                    results.append(fut.result())
                except Exception as exc:
                    # One bad file must not discard the ones that worked — the
                    # server has already accepted them.
                    print_error(f"{fp.name}: {exc}")
    else:
        for file_path in paths:
            try:
                results.append(_upload(file_path))
            except Exception as exc:
                raise typer.Exit(
                    code=handle_api_error(exc, is_json=obj.get("json"))
                ) from None

    wait_report: dict[str, dict[str, Any]] = {}
    if wait and results:
        wait_report = _wait_for_uploads(
            client,
            [f.id for f in results],
            timeout=timeout,
            quiet=bool(obj.get("json")),
        )

    if obj.get("json"):
        payload = [f.model_dump(mode="json") for f in results]
        for row in payload:
            rec = wait_report.get(str(row.get("id")))
            if rec:
                row["state"] = rec["state"]
                row["row_count"] = rec["source"].get("row_count")
                if rec["state"] == "error":
                    row["error_message"] = rec["source"].get("error_message")
        print_json(payload[0] if len(payload) == 1 else payload)
    elif obj.get("quiet"):
        for f in results:
            print_id(f.id)
    else:
        for f in results:
            state = (wait_report.get(f.id) or {}).get("state")
            suffix = f"  [{state}]" if state and state != "ready" else ""
            print_success(f"Uploaded {f.name} → {f.id}{suffix}")
        if results:
            where = results[0].workspace_id
            if where:
                print(f"\nWorkspace: {where}", file=sys.stderr)
            print(
                f"To add to your project: querri project add-source {results[0].id}",
                file=sys.stderr,
            )

    if wait_report and any(
        r["state"] != "ready" for r in wait_report.values()
    ):
        raise typer.Exit(code=1)


def _wait_for_uploads(
    client: Querri, source_ids: list[str], *, timeout: float, quiet: bool
) -> dict[str, dict[str, Any]]:
    """Block on processing, printing a live count to stderr.

    Progress goes to stderr so ``--json`` output on stdout stays machine-clean.
    """

    def _tick(done: int, total: int, counts: dict[str, int]) -> None:
        if quiet:
            return
        detail = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        print(f"\r  processing… {done}/{total} settled  {detail}   ",
              end="", file=sys.stderr, flush=True)

    report = client.sources.wait_until_ready(
        source_ids, timeout=timeout, on_progress=_tick
    )
    if not quiet:
        print(file=sys.stderr)
    for sid, rec in report.items():
        if rec["state"] == "error":
            print_error(
                f"{sid}: processing failed — "
                f"{rec['source'].get('error_message') or 'no reason given'}"
            )
        elif rec["state"] == "timeout":
            print_error(f"{sid}: still processing after the timeout")
        elif rec["state"] == "missing":
            print_error(f"{sid}: vanished before it finished processing")
    return report


@files_app.command("delete")
def delete_file(
    ctx: typer.Context,
    file_id: str | None = typer.Argument(default=None, help="File ID."),
) -> None:
    """Delete a file."""
    if file_id is None:
        if sys.stdin.isatty():
            file_id = input("File ID: ").strip()
            if not file_id:
                print_error("File ID cannot be empty.")
                raise typer.Exit(code=1)
        else:
            print_error(
                "Missing required argument <FILE_ID>."
                " Usage: querri file delete <FILE_ID>"
            )
            raise typer.Exit(code=1)
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        client.files.delete(file_id)
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None

    if obj.get("json"):
        print_json({"id": file_id, "deleted": True})
    else:
        print_success(f"Deleted file {file_id}")
