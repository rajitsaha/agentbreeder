"""garden list — list agents and other registry entities."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

console = Console()

REGISTRY_DIR = Path.home() / ".garden" / "registry"


def list_entities(
    entity_type: str = typer.Argument(
        "agents",
        help="Entity type to list: agents, tools, models, prompts",
    ),
    team: str | None = typer.Option(None, "--team", help="Filter by team"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List agents, tools, models, or prompts from the registry."""
    if entity_type == "agents":
        _list_agents(team=team, json_output=json_output)
    else:
        console.print(f"[yellow]'{entity_type}' listing not yet implemented (v0.2)[/yellow]")


def _list_agents(team: str | None = None, json_output: bool = False) -> None:
    registry_file = REGISTRY_DIR / "agents.json"

    if not registry_file.exists():
        if json_output:
            console.print("[]")
        else:
            console.print("[dim]No agents registered yet. Deploy one with: garden deploy[/dim]")
        return

    registry = json.loads(registry_file.read_text())
    agents = list(registry.values())

    if team:
        agents = [a for a in agents if a.get("team") == team]

    if json_output:
        console.print(json.dumps(agents, indent=2))
        return

    if not agents:
        console.print("[dim]No agents found.[/dim]")
        return

    table = Table(title="Registered Agents")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="dim")
    table.add_column("Team", style="yellow")
    table.add_column("Framework")
    table.add_column("Status", style="green")
    table.add_column("Endpoint", style="dim")

    for agent in agents:
        table.add_row(
            agent.get("name", ""),
            agent.get("version", ""),
            agent.get("team", ""),
            agent.get("framework", ""),
            agent.get("status", ""),
            agent.get("endpoint_url", ""),
        )

    console.print()
    console.print(table)
    console.print()
