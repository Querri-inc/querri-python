"""querri settings / querri flags — read the organization's configuration."""

from __future__ import annotations

import json
from typing import Any

import typer

from querri.cli._context import get_client
from querri.cli._output import handle_api_error, print_error, print_json, print_table

settings_app = typer.Typer(
    name="settings",
    help="Organization settings (read only).",
    no_args_is_help=True,
)

flags_app = typer.Typer(
    name="flags",
    help="Feature flags decided for this organization (read only).",
    no_args_is_help=True,
)


def _render(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, default=str)


@settings_app.command("context")
def context(ctx: typer.Context) -> None:
    """Show the organization's AI context (Settings → Customize).

    Business context, data processing instructions, analysis preferences,
    glossary — what the agents are told about this organization.
    """
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        doc = client.settings.get_context()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    if obj.get("json"):
        print_json(doc)
        return
    shown = {k: v for k, v in doc.items() if v not in (None, "", [], {})}
    if not shown:
        print_error("No AI context is set for this organization.")
        return
    for key, value in shown.items():
        print(f"── {key}")
        print(_render(value))
        print()


@flags_app.command("list")
def list_flags(
    ctx: typer.Context,
    on: bool = typer.Option(False, "--on", help="Only flags that are on."),
) -> None:
    """List every feature flag's value for this organization."""
    obj = ctx.ensure_object(dict)
    client = get_client(ctx)
    try:
        flags = client.flags.list()
    except Exception as exc:
        raise typer.Exit(code=handle_api_error(exc, is_json=obj.get("json"))) from None
    if on:
        flags = {k: v for k, v in flags.items() if v is True}
    if obj.get("json"):
        print_json(flags)
        return
    if not flags:
        print_error("No flags.")
        return
    print_table(
        [{"flag": k, "value": _render(v)} for k, v in sorted(flags.items())],
        [("flag", "Flag"), ("value", "Value")],
        ctx=ctx,
    )
