"""Querri CLI — command-line interface for the Querri data analysis platform.

Entry point guard: if typer is not installed, prints a clean error message
and exits with code 1. No tracebacks, no file paths, no module names.
"""

from __future__ import annotations


def app() -> None:
    """Entry point registered in pyproject.toml as ``querri = "querri.cli:app"``."""
    try:
        from querri.cli._app import main_app
        main_app()
    except ImportError:
        import sys
        print("Querri CLI requires additional dependencies.", file=sys.stderr)
        print("Install with: pip install 'querri[cli]'", file=sys.stderr)
        sys.exit(1)
