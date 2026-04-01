"""CLI output formatting — shared helpers for all commands.

Governs all CLI output behavior: Rich tables for TTY, plain text for pipes,
JSON for --json, IDs only for --quiet. Handles exit codes and error formatting.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Sequence

import typer

# ---------------------------------------------------------------------------
# TTY auto-detection — single check, drives all output behavior
# ---------------------------------------------------------------------------

IS_INTERACTIVE = sys.stdout.isatty()


# ---------------------------------------------------------------------------
# Exit code helpers
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_AUTH_ERROR = 2
EXIT_NOT_FOUND = 3
EXIT_RATE_LIMITED = 4


def exit_success() -> None:
    raise typer.Exit(code=EXIT_SUCCESS)


def exit_error() -> None:
    raise typer.Exit(code=EXIT_ERROR)


def exit_auth_error() -> None:
    raise typer.Exit(code=EXIT_AUTH_ERROR)


def exit_not_found() -> None:
    raise typer.Exit(code=EXIT_NOT_FOUND)


def exit_rate_limited() -> None:
    raise typer.Exit(code=EXIT_RATE_LIMITED)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def print_json(data: Any) -> None:
    """Output pretty-printed JSON to stdout."""
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    elif hasattr(data, "__dict__") and not isinstance(data, dict):
        data = {k: v for k, v in data.__dict__.items() if not k.startswith("_")}
    print(json.dumps(data, indent=2, default=str))


def print_id(id_value: str) -> None:
    """Output bare ID string (for --quiet mode)."""
    print(id_value)


def print_table(
    data: Sequence[Any],
    columns: list[tuple[str, str]],
    *,
    ctx: typer.Context | None = None,
) -> None:
    """Render data as a table.

    In TTY mode, uses Rich tables. In non-TTY mode, outputs tab-delimited text.

    Args:
        data: Sequence of objects (dicts or Pydantic models).
        columns: List of (field_name, display_header) tuples.
        ctx: Optional Typer context for checking --json/--quiet flags.
    """
    obj = ctx.ensure_object(dict) if ctx else {}
    is_interactive = obj.get("interactive", IS_INTERACTIVE)

    if is_interactive:
        _print_rich_table(data, columns)
    else:
        _print_plain_table(data, columns)


def _get_field(item: Any, field: str) -> str:
    """Extract a field from a dict or object, return as string."""
    if isinstance(item, dict):
        val = item.get(field, "")
    else:
        val = getattr(item, field, "")
    return str(val) if val is not None else ""


def _print_rich_table(data: Sequence[Any], columns: list[tuple[str, str]]) -> None:
    """Render a Rich table to stdout."""
    from rich.console import Console
    from rich.table import Table

    table = Table(show_header=True, header_style="bold")
    for _, header in columns:
        table.add_column(header)

    for item in data:
        row = [_get_field(item, field) for field, _ in columns]
        table.add_row(*row)

    console = Console()
    console.print(table)


def _print_plain_table(data: Sequence[Any], columns: list[tuple[str, str]]) -> None:
    """Output tab-delimited text (for piping)."""
    # Header
    print("\t".join(header for _, header in columns))
    # Rows
    for item in data:
        row = [_get_field(item, field) for field, _ in columns]
        print("\t".join(row))


def print_detail(data: Any, fields: list[tuple[str, str]]) -> None:
    """Print a single object's details in a key-value format.

    Args:
        data: Dict or Pydantic model.
        fields: List of (field_name, display_label) tuples.
    """
    if IS_INTERACTIVE:
        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="bold")
        table.add_column("Value")

        for field, label in fields:
            table.add_row(label, _get_field(data, field))

        console = Console()
        console.print(table)
    else:
        for field, label in fields:
            print(f"{label}: {_get_field(data, field)}")


def print_success(message: str) -> None:
    """Print a success message."""
    if IS_INTERACTIVE:
        from rich.console import Console
        Console(stderr=True).print(f"[green]✓[/green] {message}")
    else:
        print(message, file=sys.stderr)


def print_error(message: str) -> None:
    """Print an error message to stderr (red in TTY mode)."""
    if IS_INTERACTIVE:
        from rich.console import Console
        Console(stderr=True).print(f"[red]Error:[/red] {message}")
    else:
        print(f"Error: {message}", file=sys.stderr)


def print_json_error(
    error_type: str,
    message: str,
    exit_code: int,
    *,
    hint: str | None = None,
) -> None:
    """Print a JSON-formatted error to stderr."""
    error_obj: dict[str, Any] = {
        "error": error_type,
        "message": message,
        "code": exit_code,
    }
    if hint:
        error_obj["hint"] = hint
    print(json.dumps(error_obj))


# ---------------------------------------------------------------------------
# Error handler — maps SDK exceptions to CLI output + exit codes
# ---------------------------------------------------------------------------


def handle_api_error(exc: Exception, *, is_json: bool = False) -> int:
    """Handle an SDK exception, print appropriate output, return exit code.

    Args:
        exc: The exception from the SDK.
        is_json: Whether --json mode is active.

    Returns:
        Exit code to use.
    """
    from querri._exceptions import (
        AuthenticationError,
        NotFoundError,
        RateLimitError,
    )

    if isinstance(exc, AuthenticationError):
        exit_code = EXIT_AUTH_ERROR
        error_type = "auth_failed"
        message = "Authentication failed. Check your API key or set QUERRI_API_KEY environment variable."
    elif isinstance(exc, NotFoundError):
        exit_code = EXIT_NOT_FOUND
        error_type = "not_found"
        message = str(exc)
    elif isinstance(exc, RateLimitError):
        exit_code = EXIT_RATE_LIMITED
        error_type = "rate_limited"
        retry_after = getattr(exc, "retry_after", None)
        message = f"Rate limited. Retry after {retry_after}s." if retry_after else "Rate limited."
    else:
        exit_code = EXIT_ERROR
        error_type = "api_error"
        message = str(exc)

    if is_json:
        print_json_error(error_type, message, exit_code)
    else:
        print_error(message)

    return exit_code
