"""Main Typer application with global options and sub-app registration."""

from __future__ import annotations

import sys
from typing import Optional

import typer

from querri._version import __version__

# ---------------------------------------------------------------------------
# TTY detection — drives output behavior across the CLI
# ---------------------------------------------------------------------------

IS_INTERACTIVE = sys.stdout.isatty()


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

main_app = typer.Typer(
    name="querri",
    help=(
        "[bold #f15a24]Querri CLI[/bold #f15a24] — command-line interface for the "
        "[#f15a24]Querri[/#f15a24] data analysis platform.\n\n"
        "Get started:\n"
        "  [#f15a24]querri auth login[/#f15a24]              Authenticate via browser\n"
        "  [#f15a24]querri project new[/#f15a24]             Create a new project\n"
        "  [#f15a24]querri file upload data.csv[/#f15a24]    Upload a data file\n"
        "  [#f15a24]querri chat \"analyze this\"[/#f15a24]     Chat with your data"
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


# ---------------------------------------------------------------------------
# Version callback
# ---------------------------------------------------------------------------

def _version_callback(value: bool) -> None:
    if value:
        if IS_INTERACTIVE:
            from rich.console import Console
            Console(stderr=True).print(
                f"[bold #f15a24]querri[/bold #f15a24] {__version__}"
            )
        else:
            print(f"querri {__version__}")
        raise typer.Exit()


# ---------------------------------------------------------------------------
# Global options callback
# ---------------------------------------------------------------------------

@main_app.callback()
def _global_options(
    ctx: typer.Context,
    host: Optional[str] = typer.Option(
        None,
        "--host",
        envvar="QUERRI_HOST",
        help="Querri server host (default: https://app.querri.com).",
        show_default=False,
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="QUERRI_API_KEY",
        help="API key (prefer QUERRI_API_KEY env var).",
        show_default=False,
    ),
    org_id: Optional[str] = typer.Option(
        None,
        "--org-id",
        envvar="QUERRI_ORG_ID",
        help="Organization ID.",
        show_default=False,
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="Named auth profile (v0.2.1+).",
        hidden=True,
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet", "-q",
        help="Minimal output (IDs only).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Verbose output.",
    ),
    interactive: Optional[bool] = typer.Option(
        None,
        "--interactive/--no-interactive",
        help="Force interactive/non-interactive mode.",
        show_default=False,
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project", "-p",
        envvar="QUERRI_PROJECT_ID",
        help="Project ID (overrides active project).",
        show_default=False,
    ),
    chat: Optional[str] = typer.Option(
        None,
        "--chat",
        envvar="QUERRI_CHAT_ID",
        help="Chat ID (overrides active chat).",
        show_default=False,
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """[#f15a24]Querri CLI[/#f15a24] — manage projects, data, and AI chats from the terminal."""
    # Determine interactive mode
    is_interactive = interactive if interactive is not None else IS_INTERACTIVE

    # Warn about --api-key in shell history (only in interactive TTY mode)
    if api_key and is_interactive:
        import sys as _sys
        print(
            "Warning: API key passed as command argument may appear in shell history. "
            "Consider using QUERRI_API_KEY env var instead.",
            file=_sys.stderr,
        )

    # Store options in context for downstream commands
    ctx.ensure_object(dict)
    ctx.obj["host"] = host
    ctx.obj["api_key"] = api_key
    ctx.obj["org_id"] = org_id
    ctx.obj["profile"] = profile
    ctx.obj["project"] = project
    ctx.obj["chat"] = chat
    ctx.obj["json"] = json_output
    ctx.obj["quiet"] = quiet
    ctx.obj["verbose"] = verbose
    ctx.obj["interactive"] = is_interactive


# ---------------------------------------------------------------------------
# Sub-app registration with rich_help_panel groupings
# ---------------------------------------------------------------------------

# ── Getting Started ──────────────────────────────────────────────────────
from querri.cli.auth import auth_app
from querri.cli.whoami import whoami_app

main_app.add_typer(auth_app, name="auth", rich_help_panel="[#f15a24]Getting Started[/#f15a24]")
main_app.add_typer(whoami_app, name="whoami", rich_help_panel="[#f15a24]Getting Started[/#f15a24]")

# ── Projects & Data ─────────────────────────────────────────────────────
from querri.cli.projects import projects_app
from querri.cli.chat import chat_app
from querri.cli.steps import steps_app
from querri.cli.chats import chats_app
from querri.cli.files import files_app
from querri.cli.sources import sources_app
from querri.cli.views import view_app

main_app.add_typer(projects_app, name="project", rich_help_panel="[#f15a24]Projects & Data[/#f15a24]")
main_app.add_typer(chat_app, name="chat", rich_help_panel="[#f15a24]Projects & Data[/#f15a24]")
main_app.add_typer(steps_app, name="step", rich_help_panel="[#f15a24]Projects & Data[/#f15a24]")
main_app.add_typer(chats_app, name="chats", rich_help_panel="[#f15a24]Projects & Data[/#f15a24]", hidden=True)
main_app.add_typer(files_app, name="file", rich_help_panel="[#f15a24]Projects & Data[/#f15a24]")
main_app.add_typer(sources_app, name="source", rich_help_panel="[#f15a24]Projects & Data[/#f15a24]")
main_app.add_typer(view_app, name="view", rich_help_panel="[#f15a24]Projects & Data[/#f15a24]")

from querri.cli.dashboards import dashboards_app
main_app.add_typer(dashboards_app, name="dashboard", rich_help_panel="[#f15a24]Projects & Data[/#f15a24]")

# ── Administration ──────────────────────────────────────────────────────
from querri.cli.users import users_app
from querri.cli.keys import keys_app
from querri.cli.policies import policies_app
from querri.cli.sharing import sharing_app

main_app.add_typer(users_app, name="user", rich_help_panel="[#f15a24]Administration[/#f15a24]")
main_app.add_typer(keys_app, name="key", rich_help_panel="[#f15a24]Administration[/#f15a24]")
main_app.add_typer(policies_app, name="policy", rich_help_panel="[#f15a24]Administration[/#f15a24]")
main_app.add_typer(sharing_app, name="share", rich_help_panel="[#f15a24]Administration[/#f15a24]")

# ── Advanced ────────────────────────────────────────────────────────────
from querri.cli.embed import embed_app
from querri.cli.usage import usage_app
from querri.cli.audit import audit_app

main_app.add_typer(embed_app, name="embed", rich_help_panel="[#f15a24]Advanced[/#f15a24]")
main_app.add_typer(usage_app, name="usage", rich_help_panel="[#f15a24]Advanced[/#f15a24]")
main_app.add_typer(audit_app, name="audit", rich_help_panel="[#f15a24]Advanced[/#f15a24]")
