"""garden validate — validate an agent.yaml without deploying."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from engine.config_parser import validate_config

console = Console()


def validate(
    config_path: Path = typer.Argument(
        ...,
        help="Path to agent.yaml",
        exists=True,
        readable=True,
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """Validate an agent.yaml configuration file."""
    result = validate_config(config_path)

    if json_output:
        import json

        output = {
            "valid": result.valid,
            "errors": [e.model_dump() for e in result.errors],
        }
        console.print(json.dumps(output, indent=2))
        if not result.valid:
            raise typer.Exit(code=1)
        return

    if result.valid:
        console.print()
        console.print(
            Panel(
                f"[bold green]Valid![/bold green] {config_path.name} passed all checks.",
                title="Validation",
                border_style="green",
            )
        )
        console.print()
    else:
        console.print()
        table = Table(title="Validation Errors", border_style="red")
        table.add_column("Field", style="cyan")
        table.add_column("Error", style="red")
        table.add_column("Suggestion", style="yellow")
        table.add_column("Line", style="dim")

        for error in result.errors:
            table.add_row(
                error.path,
                error.message,
                error.suggestion,
                str(error.line) if error.line else "-",
            )

        console.print(table)
        console.print()
        raise typer.Exit(code=1)
