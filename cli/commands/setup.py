"""agentbreeder setup — interactive first-run wizard.

Guides the user through:
  1. Installing and starting Ollama (local, free, no API key)
  2. Configuring cloud LLM provider API keys
  3. Verifying everything works with a live test

Run at any time to add providers or re-verify your setup.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import time
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

console = Console()

PROVIDERS_FILE = Path.home() / ".agentbreeder" / "providers.json"
ENV_FILE = Path.cwd() / ".env"

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# ── Ollama starter models (name, size, best for) ──────────────────────────
STARTER_MODELS = [
    ("llama3.2", "~2 GB", "General purpose — fast responses"),
    ("gemma3", "~2 GB", "Google's efficient small model"),
    ("phi4-mini", "~2 GB", "Microsoft — great at reasoning"),
    ("mistral", "~4 GB", "Strong at coding and instruction"),
    ("qwen2.5", "~4 GB", "Alibaba — multilingual + tools"),
]

# ── Cloud providers ────────────────────────────────────────────────────────
CLOUD_PROVIDERS = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "env_key": "ANTHROPIC_API_KEY",
        "key_url": "https://console.anthropic.com/settings/keys",
        "prefix": "sk-ant-",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-20250414"],
        "why": "Best reasoning, safety, and long-context tasks",
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "env_key": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys",
        "prefix": "sk-",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "why": "Widest ecosystem, function calling pioneer",
    },
    "google": {
        "name": "Google AI (Gemini)",
        "env_key": "GOOGLE_API_KEY",
        "key_url": "https://aistudio.google.com/app/apikey",
        "prefix": "AIza",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro"],
        "why": "Huge context window, multimodal, free tier",
    },
    "openrouter": {
        "name": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "key_url": "https://openrouter.ai/keys",
        "prefix": "sk-or-",
        "models": ["openai/gpt-4o", "anthropic/claude-sonnet-4-20250514"],
        "why": "Access 200+ models through one key",
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────


def _load_providers() -> dict:
    if not PROVIDERS_FILE.exists():
        return {}
    return json.loads(PROVIDERS_FILE.read_text())


def _save_providers(providers: dict) -> None:
    PROVIDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROVIDERS_FILE.write_text(json.dumps(providers, indent=2) + "\n")


def _write_env_key(key: str, value: str) -> None:
    env_path = ENV_FILE
    if env_path.exists():
        lines = env_path.read_text().splitlines()
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                updated = True
                break
        if not updated:
            lines.append(f"{key}={value}")
        env_path.write_text("\n".join(lines) + "\n")
    else:
        env_path.write_text(f"{key}={value}\n")


def _read_env_key(key: str) -> str | None:
    env_path = ENV_FILE
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key)


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "••••"
    return f"••••{value[-4:]}"


def _ollama_install_instructions() -> list[str]:
    """Return OS-specific install instructions as a list of display lines."""
    system = platform.system()
    if system == "Darwin":
        return [
            "[bold]Option A — Homebrew (recommended):[/bold]",
            "  [cyan]brew install ollama[/cyan]",
            "",
            "[bold]Option B — One-liner:[/bold]",
            "  [cyan]curl -fsSL https://ollama.com/install.sh | sh[/cyan]",
            "",
            "[bold]Option C — Desktop app:[/bold]",
            "  Download from [link=https://ollama.com/download]https://ollama.com/download[/link]",
        ]
    elif system == "Linux":
        return [
            "[bold]Install with one command:[/bold]",
            "  [cyan]curl -fsSL https://ollama.com/install.sh | sh[/cyan]",
            "",
            "[bold]Or via Docker:[/bold]",
            "  [cyan]docker run -d -v ollama:/root/.ollama -p 11434:11434 ollama/ollama[/cyan]",
        ]
    elif system == "Windows":
        return [
            "[bold]Download the installer:[/bold]",
            "  [link=https://ollama.com/download/windows]https://ollama.com/download/windows[/link]",
            "",
            "[bold]Or via winget:[/bold]",
            "  [cyan]winget install Ollama.Ollama[/cyan]",
        ]
    else:
        return [
            "[bold]Download from:[/bold]",
            "  [link=https://ollama.com/download]https://ollama.com/download[/link]",
        ]


async def _ollama_is_running(base_url: str = OLLAMA_BASE_URL) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/")
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


async def _ollama_list_models(base_url: str = OLLAMA_BASE_URL) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def _validate_api_key_format(key: str, prefix: str) -> bool:
    return key.startswith(prefix) and len(key) > len(prefix) + 8


async def _test_anthropic_key(api_key: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-20250414",
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            return resp.status_code == 200
    except Exception:
        return False


async def _test_openai_key(api_key: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            return resp.status_code == 200
    except Exception:
        return False


async def _test_google_key(api_key: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            )
            return resp.status_code == 200
    except Exception:
        return False


async def _test_openrouter_key(api_key: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            return resp.status_code == 200
    except Exception:
        return False


_KEY_TESTERS = {
    "anthropic": _test_anthropic_key,
    "openai": _test_openai_key,
    "google": _test_google_key,
    "openrouter": _test_openrouter_key,
}


# ── Section renderers ──────────────────────────────────────────────────────


def _print_header() -> None:
    console.print()
    console.print(
        Panel(
            "[bold cyan]AgentBreeder Setup[/bold cyan]\n\n"
            "[dim]This wizard will help you connect LLM providers so your agents\n"
            "have a model to run on. Takes about 2 minutes.\n\n"
            "Skip any step by pressing [bold]Enter[/bold]. "
            "Re-run any time with [bold cyan]agentbreeder setup[/bold cyan].[/dim]",
            border_style="cyan",
            padding=(1, 3),
        )
    )
    console.print()


def _print_status_overview(providers: dict) -> None:
    """Print a quick at-a-glance of what's already configured."""
    ollama_ok = asyncio.run(_ollama_is_running())
    rows: list[tuple[str, str, str]] = []

    # Ollama
    if ollama_ok:
        models = asyncio.run(_ollama_list_models())
        rows.append(("Ollama (local)", "[green]running[/green]", ", ".join(models[:3]) or "—"))
    else:
        rows.append(("Ollama (local)", "[dim]not running[/dim]", "—"))

    # Cloud providers
    for key, meta in CLOUD_PROVIDERS.items():
        env_val = _read_env_key(meta["env_key"])
        stored = providers.get(key, {})
        if env_val or stored.get("status") == "active":
            display_key = _mask(env_val or "configured")
            rows.append((meta["name"], "[green]configured[/green]", display_key))
        else:
            rows.append((meta["name"], "[dim]not configured[/dim]", "—"))

    table = Table(title="Current Status", show_header=True, header_style="bold")
    table.add_column("Provider")
    table.add_column("Status")
    table.add_column("Key / Models")
    for name, status, detail in rows:
        table.add_row(name, status, detail)

    console.print(table)
    console.print()


def _section(title: str, step: int, total: int = 3) -> None:
    console.print(Rule(f"[bold]Step {step}/{total} — {title}[/bold]", style="blue"))
    console.print()


# ── Ollama section ─────────────────────────────────────────────────────────


def _setup_ollama() -> bool:
    """Guide the user through Ollama setup. Returns True if Ollama ends up running."""
    _section("Local AI with Ollama", 1)

    console.print(
        "  [bold]Ollama[/bold] lets you run AI models entirely on your machine — "
        "[bold green]free, private, no API key.[/bold green]\n"
    )

    is_running = asyncio.run(_ollama_is_running())

    if is_running:
        models = asyncio.run(_ollama_list_models())
        console.print(f"  [green]✓ Ollama is already running at {OLLAMA_BASE_URL}[/green]")
        if models:
            console.print(
                f"  [green]✓ {len(models)} model(s) available: {', '.join(models[:5])}[/green]"
            )
            console.print()
            return True
        else:
            console.print("  [yellow]No models pulled yet.[/yellow]")
            _guide_pull_model()
            return True

    # Not running — show install instructions
    console.print("  [yellow]Ollama is not running.[/yellow]\n")
    instructions = _ollama_install_instructions()
    console.print(
        Panel(
            "\n".join(instructions),
            title="Install Ollama",
            border_style="yellow",
            padding=(1, 2),
        )
    )
    console.print()
    console.print("  After installing, start Ollama:")
    console.print("    [cyan]ollama serve[/cyan]   (or just launch the desktop app)\n")

    wait = (
        console.input(
            "  [bold]Press Enter once Ollama is running, or type [cyan]skip[/cyan] to skip: [/bold]"
        )
        .strip()
        .lower()
    )

    if wait == "skip":
        console.print("\n  [dim]Skipping Ollama — you can set it up later.[/dim]\n")
        return False

    # Re-check
    console.print("\n  [dim]Checking for Ollama...[/dim]")
    for attempt in range(3):
        time.sleep(1)
        if asyncio.run(_ollama_is_running()):
            console.print(f"  [green]✓ Ollama is running at {OLLAMA_BASE_URL}[/green]\n")
            _guide_pull_model()
            return True
        if attempt < 2:
            console.print("  [dim]Not yet — retrying...[/dim]")

    console.print("  [red]Could not reach Ollama.[/red]")
    console.print("  [dim]You can finish setup later. Run: agentbreeder setup[/dim]\n")
    return False


def _guide_pull_model() -> None:
    """Show model picker and pull a starter model."""
    console.print()
    console.print("  [bold]Choose a starter model to pull:[/bold]\n")

    table = Table(show_header=True, header_style="bold dim", box=None, padding=(0, 2))
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Model")
    table.add_column("Size", style="dim")
    table.add_column("Best for", style="dim")

    for i, (name, size, use) in enumerate(STARTER_MODELS, 1):
        table.add_row(str(i), name, size, use)

    console.print(table)
    console.print()

    choice = console.input(
        f"  Select [1-{len(STARTER_MODELS)}] or press Enter for [cyan]{STARTER_MODELS[0][0]}[/cyan] "
        "(or type a custom model name): "
    ).strip()

    if not choice:
        model_name = STARTER_MODELS[0][0]
    elif choice.isdigit():
        idx = int(choice) - 1
        model_name = (
            STARTER_MODELS[idx][0] if 0 <= idx < len(STARTER_MODELS) else STARTER_MODELS[0][0]
        )
    else:
        model_name = choice

    console.print()
    console.print(
        Panel(
            f"  Run this in a new terminal:\n\n"
            f"  [bold cyan]ollama pull {model_name}[/bold cyan]\n\n"
            f"  [dim]This downloads the model to your machine (one-time).\n"
            f"  It may take a few minutes depending on your connection.[/dim]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    console.input("\n  [bold]Press Enter once the model is downloaded (or now to skip): [/bold]")

    models = asyncio.run(_ollama_list_models())
    if model_name.split(":")[0] in " ".join(models):
        console.print(f"  [green]✓ {model_name} is ready[/green]")
    else:
        console.print("  [dim]Model not confirmed yet — that's fine, continue.[/dim]")
    console.print()


# ── Cloud providers section ────────────────────────────────────────────────


def _setup_cloud_providers(providers: dict) -> dict:
    """Walk through each cloud provider. Returns updated providers dict."""
    _section("Cloud LLM Providers", 2)

    console.print(
        "  Cloud providers let your agents use powerful hosted models.\n"
        "  [dim]Press Enter to skip any provider.[/dim]\n"
    )

    for provider_id, meta in CLOUD_PROVIDERS.items():
        _setup_one_provider(provider_id, meta, providers)

    return providers


def _setup_one_provider(provider_id: str, meta: dict, providers: dict) -> None:
    existing_key = _read_env_key(meta["env_key"])
    already_ok = providers.get(provider_id, {}).get("status") == "active"

    if existing_key and already_ok:
        console.print(
            f"  [green]✓[/green] [bold]{meta['name']}[/bold] — "
            f"already configured ([dim]{_mask(existing_key)}[/dim])"
        )
        reconfig = console.input("    Reconfigure? (y/N): ").strip().lower()
        if reconfig != "y":
            console.print()
            return
    else:
        console.print(f"\n  ┌─ [bold]{meta['name']}[/bold]")
        console.print(f"  │  {meta['why']}")
        console.print(f"  │  Models: [dim]{', '.join(meta['models'][:2])}[/dim]")
        console.print("  │")
        console.print("  │  Get your API key:")
        console.print(f"  │  [bold cyan]{meta['key_url']}[/bold cyan]")
        console.print("  │")

    raw_key = console.input(f"  └─ [bold]{meta['env_key']}[/bold] (or Enter to skip): ").strip()

    if not raw_key:
        console.print("     [dim]Skipped.[/dim]\n")
        return

    # Basic format check
    prefix = meta.get("prefix", "")
    if prefix and not _validate_api_key_format(raw_key, prefix):
        console.print(
            f"  [yellow]⚠ Key doesn't look like a {meta['name']} key "
            f"(expected prefix: {prefix}...)[/yellow]"
        )
        proceed = console.input("     Save anyway? (y/N): ").strip().lower()
        if proceed != "y":
            console.print("     [dim]Skipped.[/dim]\n")
            return

    # Live connection test
    console.print("     [dim]Testing connection...[/dim]", end="")
    tester = _KEY_TESTERS.get(provider_id)
    if tester:
        success = asyncio.run(tester(raw_key))
        if success:
            console.print(f"\r     [green]✓ Connected to {meta['name']}[/green]          ")
        else:
            console.print("\r     [red]✗ Connection failed — key may be invalid or inactive[/red]")
            keep = console.input("     Save anyway? (y/N): ").strip().lower()
            if keep != "y":
                console.print("     [dim]Skipped.[/dim]\n")
                return
    else:
        console.print("\r     [dim]Saved (connection test not available for this provider)[/dim]")

    # Persist
    _write_env_key(meta["env_key"], raw_key)
    providers[provider_id] = {
        "name": meta["name"],
        "provider_type": provider_id,
        "status": "active",
        "masked_key": _mask(raw_key),
        "model_count": len(meta["models"]),
    }
    _save_providers(providers)
    console.print(f"     [green]✓[/green] Key saved to [dim]{ENV_FILE}[/dim]\n")


# ── Final summary ──────────────────────────────────────────────────────────


def _print_summary(providers: dict) -> None:
    _section("You're ready", 3)

    ollama_ok = asyncio.run(_ollama_is_running())
    ollama_models = asyncio.run(_ollama_list_models()) if ollama_ok else []
    cloud_count = sum(1 for p in providers.values() if p.get("status") == "active")

    lines: list[str] = []

    if ollama_ok and ollama_models:
        lines.append(
            f"  [green]✓[/green] Ollama running — "
            f"{len(ollama_models)} model(s): [dim]{', '.join(ollama_models[:3])}[/dim]"
        )
    elif ollama_ok:
        lines.append("  [green]✓[/green] Ollama running — no models pulled yet")
    else:
        lines.append("  [dim]○ Ollama not running (run: ollama serve)[/dim]")

    for _pid, p in providers.items():
        if p.get("status") == "active":
            lines.append(
                f"  [green]✓[/green] {p['name']} — [dim]{p.get('masked_key', 'configured')}[/dim]"
            )

    if not lines or (not ollama_ok and cloud_count == 0):
        lines.append("  [yellow]No providers configured yet.[/yellow]")
        lines.append("  [dim]Run [bold]agentbreeder setup[/bold] any time to add one.[/dim]")

    console.print(
        Panel("\n".join(lines), title="Setup Complete", border_style="green", padding=(1, 2))
    )
    console.print()

    # Next steps
    next_steps: list[str] = []

    if ollama_ok and ollama_models:
        next_steps.append(
            f"[bold cyan]agentbreeder chat my-agent --local[/bold cyan]"
            f"    [dim]# chat with {ollama_models[0]} right now[/dim]"
        )
    elif not ollama_ok:
        next_steps.append(
            "[bold cyan]ollama serve[/bold cyan]                          "
            "[dim]# then: agentbreeder chat my-agent --local[/dim]"
        )

    if cloud_count > 0:
        next_steps.append(
            "[bold cyan]agentbreeder init[/bold cyan]                      "
            "[dim]# scaffold a new agent project[/dim]"
        )
        next_steps.append(
            "[bold cyan]agentbreeder deploy --target local[/bold cyan]     "
            "[dim]# deploy and run your agent[/dim]"
        )

    next_steps.append(
        "[bold cyan]agentbreeder provider list[/bold cyan]             "
        "[dim]# see all configured providers[/dim]"
    )

    if next_steps:
        console.print("  [bold]Next steps:[/bold]\n")
        for step in next_steps:
            console.print(f"    {step}")
        console.print()


# ── Entry point ────────────────────────────────────────────────────────────


def setup(
    providers_only: bool = typer.Option(
        False,
        "--providers-only",
        "-p",
        help="Skip Ollama setup and go straight to cloud API keys",
    ),
    ollama_only: bool = typer.Option(
        False,
        "--ollama-only",
        "-o",
        help="Only set up Ollama, skip cloud providers",
    ),
) -> None:
    """Interactive setup wizard — configure Ollama and cloud LLM providers.

    Guides you through installing Ollama for free local AI, and/or adding
    API keys for Anthropic, OpenAI, Google, and OpenRouter.

    Examples:
        agentbreeder setup
        agentbreeder setup --ollama-only
        agentbreeder setup --providers-only
    """
    providers = _load_providers()

    _print_header()
    _print_status_overview(providers)

    skip_ollama = providers_only
    skip_cloud = ollama_only

    if not skip_ollama:
        _setup_ollama()
    else:
        _section("Local AI with Ollama", 1)
        console.print("  [dim]Skipped (--providers-only)[/dim]\n")

    if not skip_cloud:
        providers = _setup_cloud_providers(providers)
    else:
        _section("Cloud LLM Providers", 2)
        console.print("  [dim]Skipped (--ollama-only)[/dim]\n")

    _print_summary(providers)
