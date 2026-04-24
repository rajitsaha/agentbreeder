"""agentbreeder down — stop the AgentBreeder platform."""

from __future__ import annotations

import json
import subprocess
import sys

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()

_QS_PROJECT = "agentbreeder-qs"


def _qs_is_running() -> bool:
    """Return True if any containers from the quickstart stack are up."""
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={_QS_PROJECT}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _stop_qs(volumes: bool) -> int:
    """Stop the quickstart stack by project name. Returns returncode."""
    cmd = ["docker", "compose", "--project-name", _QS_PROJECT, "down"]
    if volumes:
        cmd.append("--volumes")
    return subprocess.run(cmd).returncode


def down(
    clean: bool = typer.Option(
        False,
        "--clean",
        help="Also remove volumes (deletes database data)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """Stop AgentBreeder and all its services.

    Works from any directory — stops the quickstart stack if running,
    or the dev stack if found. Use --clean to also remove volumes.
    """
    stopped_qs = False
    stopped_dev = False

    # ── 1. Stop quickstart stack (project-name-based, no file needed) ──────
    if _qs_is_running():
        if not json_output:
            label = "quickstart stack" + (" + volumes" if clean else "")
            console.print(f"  Stopping {label} ({_QS_PROJECT})...")
        rc = _stop_qs(clean)
        if rc == 0:
            stopped_qs = True
        elif not json_output:
            console.print("  [red]✗[/red] Failed to stop quickstart stack")

    # ── 2. Stop dev stack (compose file required) ───────────────────────────
    from cli.commands.up import _find_compose_dir  # noqa: PLC0415

    compose_dir = _find_compose_dir()
    if compose_dir is not None:
        compose_file = compose_dir / "docker-compose.yml"
        project_root = compose_dir.parent
        cmd = [
            "docker", "compose",
            "-f", str(compose_file),
            "--project-directory", str(project_root),
            "down",
        ]
        if clean:
            cmd.append("--volumes")
        if not json_output:
            console.print("  Stopping dev stack...")
        rc = subprocess.run(cmd, cwd=str(project_root)).returncode
        if rc == 0:
            stopped_dev = True
        elif not json_output:
            console.print("  [red]✗[/red] Failed to stop dev stack")

    # ── 3. Nothing found ────────────────────────────────────────────────────
    if not stopped_qs and not stopped_dev:
        if json_output:
            sys.stdout.write(json.dumps({"status": "not_running"}) + "\n")
        else:
            console.print(
                Panel(
                    "[bold]No AgentBreeder services are running.[/bold]\n\n"
                    "  [dim]Start them with: [cyan]agentbreeder quickstart[/cyan][/dim]",
                    border_style="dim",
                    padding=(1, 2),
                )
            )
        return

    if json_output:
        sys.stdout.write(
            json.dumps({"status": "stopped", "quickstart": stopped_qs, "dev": stopped_dev, "clean": clean})
            + "\n"
        )
        return

    console.print()
    parts = []
    if stopped_qs:
        parts.append("[green]✓[/green] Quickstart stack stopped")
    if stopped_dev:
        parts.append("[green]✓[/green] Dev stack stopped")
    if clean:
        parts.append("[dim]Volumes removed — database data deleted[/dim]")
    else:
        parts.append("[dim]Data preserved. Run [bold]agentbreeder quickstart[/bold] to start again.[/dim]")
    console.print(Panel("\n".join(parts), title="[bold]AgentBreeder stopped[/bold]", border_style="blue", padding=(1, 2)))
