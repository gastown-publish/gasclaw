"""Host CLI for managing gasclaw instances outside Docker container.

This module provides commands that run on the host computer to manage
gasclaw containers, configuration, and lifecycle.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from gasclaw import __version__

app = typer.Typer(help="Gasclaw Host CLI — manage gasclaw containers from the host.")
console = Console()

DEFAULT_CONTAINER_NAME = "gasclaw"
DEFAULT_PROJECT_DIR = "."


def _is_inside_container() -> bool:
    """Detect if running inside a Docker container."""
    # Check for .dockerenv file
    if Path("/.dockerenv").exists():
        return True
    # Check cgroup for docker
    try:
        cgroup = Path("/proc/self/cgroup").read_text()
        return "docker" in cgroup or "containerd" in cgroup
    except (FileNotFoundError, PermissionError):
        pass
    return False


def _get_docker_compose_cmd() -> list[str]:
    """Get the docker compose command (v2 preferred, fallback to v1)."""
    # Try docker compose (v2) first
    result = subprocess.run(
        ["docker", "compose", "version"],
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return ["docker", "compose"]
    # Fallback to docker-compose (v1)
    return ["docker-compose"]


def _run_docker(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a docker command and return the result."""
    cmd = ["docker"] + args
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _run_docker_compose(
    args: list[str],
    project_dir: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run docker compose command in the specified project directory."""
    cmd = _get_docker_compose_cmd() + args
    cwd = project_dir if project_dir else Path.cwd()
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, check=check)


def _container_exists(name: str = DEFAULT_CONTAINER_NAME) -> bool:
    """Check if a container with the given name exists."""
    result = _run_docker(["ps", "-a", "--format", "{{.Names}}"], check=False)
    return name in result.stdout.splitlines()


def _container_running(name: str = DEFAULT_CONTAINER_NAME) -> bool:
    """Check if a container with the given name is running."""
    result = _run_docker(
        ["ps", "--format", "{{.Names}}", "--filter", f"name={name}"],
        check=False,
    )
    return name in result.stdout.splitlines()


def _get_container_status(name: str = DEFAULT_CONTAINER_NAME) -> dict[str, str]:
    """Get detailed status of a container."""
    result = _run_docker(
        [
            "inspect",
            "--format",
            "{{.State.Status}}|{{.State.Health.Status}}|{{.Config.Image}}",
            name,
        ],
        check=False,
    )
    if result.returncode != 0:
        return {"exists": "false", "status": "not_found"}

    parts = result.stdout.strip().split("|")
    return {
        "exists": "true",
        "status": parts[0] if len(parts) > 0 else "unknown",
        "health": parts[1] if len(parts) > 1 else "unknown",
        "image": parts[2] if len(parts) > 2 else "unknown",
    }


@app.callback()
def host_callback() -> None:
    """Host CLI callback — detect if inside container and warn."""
    if _is_inside_container():
        console.print(
            "[yellow]Warning: You appear to be running inside a Docker container.[/yellow]\n"
            "Host CLI commands manage containers from the outside.\n"
            "Use the regular 'gasclaw' command inside the container instead."
        )
        raise typer.Exit(code=1)


@app.command()
def init(
    project_dir: Annotated[
        Path,
        typer.Option(help="Directory to initialize gasclaw project"),
    ] = Path("."),
    skip_wizard: Annotated[
        bool,
        typer.Option("--skip-wizard", help="Skip interactive wizard, create default config"),
    ] = False,
) -> None:
    """Initialize a new gasclaw project with onboarding wizard."""
    console.print(Panel.fit("[bold blue]🦀 Gasclaw Initialization Wizard[/bold blue]"))
    console.print()

    project_path = project_dir.resolve()
    project_path.mkdir(parents=True, exist_ok=True)

    # Check if already initialized
    env_file = project_path / ".env"
    compose_file = project_path / "docker-compose.yml"

    if (env_file.exists() or compose_file.exists()) and not Confirm.ask(
        f"[yellow]Gasclaw files already exist in {project_path}.[/yellow] Overwrite?",
        default=False,
    ):
        console.print("[yellow]Initialization cancelled.[/yellow]")
        raise typer.Exit(code=0)

    if skip_wizard:
        _create_default_config(project_path)
        console.print(f"[green]✅ Default config created in {project_path}[/green]")
        return

    # Interactive wizard
    console.print("[bold]Let's set up your gasclaw instance...[/bold]\n")

    # 1. Project type / GitHub setup
    console.print("[bold cyan]Step 1: Project Setup[/bold cyan]")
    project_choice = Prompt.ask(
        "Do you want to create a new GitHub project or use an existing one?",
        choices=["new", "existing"],
        default="new",
    )

    github_repo = None
    if project_choice == "new":
        repo_name = Prompt.ask("Enter name for new GitHub repository", default="my-gasclaw-project")
        console.print(f"[dim]Repository '{repo_name}' will be created when gasclaw starts[/dim]")
        github_repo = repo_name
    else:
        github_repo = Prompt.ask("Enter existing GitHub repository URL or path")

    # 2. Kimi API Keys
    console.print("\n[bold cyan]Step 2: Kimi API Configuration[/bold cyan]")
    console.print("You need Kimi API keys from https://platform.kimi.com/")

    gastown_keys = []
    while True:
        key = Prompt.ask(
            "Enter Kimi API key for Gastown agents",
            password=True,
        )
        if key.startswith("sk-"):
            gastown_keys.append(key)
            break
        console.print("[red]Invalid key format. Key should start with 'sk-'[/red]")

    while Confirm.ask("Add another Gastown agent key?", default=False):
        key = Prompt.ask("Enter additional Kimi API key", password=True)
        if key.startswith("sk-"):
            gastown_keys.append(key)
        else:
            console.print("[red]Invalid key format. Skipping.[/red]")

    openclaw_key = None
    while True:
        key = Prompt.ask(
            "Enter Kimi API key for OpenClaw (overseer)",
            password=True,
        )
        if key.startswith("sk-"):
            openclaw_key = key
            break
        console.print("[red]Invalid key format. Key should start with 'sk-'[/red]")

    # 3. Telegram Bot Setup
    console.print("\n[bold cyan]Step 3: Telegram Bot Setup[/bold cyan]")
    console.print("Create a bot with @BotFather on Telegram and get your token")

    bot_token = Prompt.ask("Enter Telegram bot token (format: 123456:ABC-DEF)")
    owner_id = IntPrompt.ask("Enter your Telegram user ID (get it from @userinfobot)")

    # 4. Agent Configuration
    console.print("\n[bold cyan]Step 4: Agent Configuration[/bold cyan]")
    agent_count = IntPrompt.ask("Number of crew workers", default=6)
    monitor_interval = IntPrompt.ask(
        "Health check interval (seconds)",
        default=300,
    )
    activity_deadline = IntPrompt.ask(
        "Max seconds between commits (activity compliance)",
        default=3600,
    )

    # 5. Generate files
    console.print("\n[bold cyan]Step 5: Generating Configuration Files...[/bold cyan]")

    # Create .env file
    env_content = f"""# Gasclaw Environment Configuration
# Generated by gasclaw init

# Required: Colon-separated Kimi API keys for Gastown agents
GASTOWN_KIMI_KEYS={':'.join(gastown_keys)}

# Required: Kimi API key for OpenClaw LLM (separate pool)
OPENCLAW_KIMI_KEY={openclaw_key}

# Required: Telegram bot token
TELEGRAM_BOT_TOKEN={bot_token}

# Required: Telegram user ID for allowlist
TELEGRAM_OWNER_ID={owner_id}

# Optional: Git URL or path for the rig
GT_RIG_URL={github_repo if github_repo else '/project'}

# Optional: Number of crew workers
GT_AGENT_COUNT={agent_count}

# Optional: Health check interval in seconds
MONITOR_INTERVAL={monitor_interval}

# Optional: Max seconds between commits/PRs
ACTIVITY_DEADLINE={activity_deadline}

# Optional: Log level - DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
"""

    env_file.write_text(env_content)
    console.print(f"[green]✅ Created {env_file}[/green]")

    # Create docker-compose.yml
    compose_content = """services:
  gasclaw:
    image: ghcr.io/gastown-publish/gasclaw:latest
    container_name: gasclaw
    ports:
      - "18789:18789"
    volumes:
      - ./project:/project
    env_file:
      - .env
    restart: unless-stopped
"""

    compose_file.write_text(compose_content)
    console.print(f"[green]✅ Created {compose_file}[/green]")

    # Create gasclaw.yaml config
    yaml_config = f"""# Gasclaw Configuration File
# Place this file at gasclaw.yaml or specify via GASCLAW_CONFIG env var

# Gastown agent settings
gastown:
  agent_count: {agent_count}
  rig_url: "{github_repo if github_repo else '/project'}"

# File paths
paths:
  project_dir: "/project"

# Maintenance loop settings
maintenance:
  monitor_interval: {monitor_interval}
  activity_deadline: {activity_deadline}

# Service ports
services:
  dolt_port: 3307
  gateway_port: 18789

# Telegram configuration
telegram:
  allow_ids:
    - "{owner_id}"

# Agent identity customization
agent:
  id: "main"
  name: "Gasclaw Overseer"
  emoji: "🏭"
"""

    yaml_file = project_path / "gasclaw.yaml"
    yaml_file.write_text(yaml_config)
    console.print(f"[green]✅ Created {yaml_file}[/green]")

    # Create project directory structure
    project_subdir = project_path / "project"
    project_subdir.mkdir(exist_ok=True)
    (project_subdir / ".gitkeep").write_text("")

    console.print("[green]✅ Created project directory structure[/green]")

    # Summary
    console.print("\n" + "=" * 50)
    console.print("[bold green]🎉 Initialization Complete![/bold green]")
    console.print("=" * 50)
    console.print(f"\nProject location: [cyan]{project_path}[/cyan]")
    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  1. cd {project_path}")
    console.print("  2. Review the generated .env file")
    console.print("  3. Run 'gasclaw start' to launch your instance")
    console.print("\n[dim]For help: gasclaw --help[/dim]")


def _create_default_config(project_path: Path) -> None:
    """Create default configuration files without wizard."""
    # Copy example files
    env_example = Path(__file__).parent / ".." / ".." / ".env.example"
    compose_example = Path(__file__).parent / ".." / ".." / "docker-compose.yml"

    # Create .env template
    env_file = project_path / ".env"
    if env_example.exists():
        env_file.write_text(env_example.read_text())
    else:
        env_file.write_text("# Copy from .env.example and fill in your values\n")

    # Create docker-compose.yml
    compose_file = project_path / "docker-compose.yml"
    if compose_example.exists():
        compose_file.write_text(compose_example.read_text())
    else:
        compose_file.write_text("# Copy from docker-compose.yml.example\n")

    # Create project directory
    (project_path / "project").mkdir(exist_ok=True)


@app.command(name="start")
def start(
    project_dir: Annotated[
        Path,
        typer.Option("--project-dir", "-p", help="Project directory containing docker-compose.yml"),
    ] = Path("."),
    build: Annotated[
        bool,
        typer.Option("--build", "-b", help="Build image before starting"),
    ] = False,
    detach: Annotated[
        bool,
        typer.Option("--detach", "-d", help="Run in detached mode"),
    ] = True,
) -> None:
    """Start the gasclaw container."""
    project_path = project_dir.resolve()
    compose_file = project_path / "docker-compose.yml"

    if not compose_file.exists():
        console.print(f"[red]Error: No docker-compose.yml found in {project_path}[/red]")
        console.print("Run 'gasclaw init' first to create a project.")
        raise typer.Exit(code=1)

    # Check if already running
    if _container_running():
        console.print("[yellow]Gasclaw container is already running.[/yellow]")
        console.print("Use 'gasclaw logs' to view output or 'gasclaw stop' to stop.")
        return

    console.print("[bold]Starting gasclaw...[/bold]")

    args = ["up"]
    if detach:
        args.append("-d")
    if build:
        args.append("--build")

    result = _run_docker_compose(args, project_dir=project_path, check=False)

    if result.returncode != 0:
        console.print("[red]Failed to start gasclaw:[/red]")
        console.print(result.stderr)
        raise typer.Exit(code=1)

    console.print("[green]✅ Gasclaw started successfully[/green]")

    if detach:
        console.print("\nUseful commands:")
        console.print("  gasclaw logs    # View logs")
        console.print("  gasclaw status  # Check status")
        console.print("  gasclaw stop    # Stop container")


@app.command(name="stop")
def stop(
    project_dir: Annotated[
        Path,
        typer.Option("--project-dir", "-p", help="Project directory containing docker-compose.yml"),
    ] = Path("."),
    remove: Annotated[
        bool,
        typer.Option("--remove", "-r", help="Remove container after stopping"),
    ] = False,
) -> None:
    """Stop the gasclaw container."""
    project_path = project_dir.resolve()

    if not _container_exists():
        console.print("[yellow]Gasclaw container does not exist.[/yellow]")
        return

    if not _container_running():
        console.print("[yellow]Gasclaw container is not running.[/yellow]")
        if remove:
            _run_docker(["rm", DEFAULT_CONTAINER_NAME], check=False)
            console.print("[green]Container removed.[/green]")
        return

    console.print("[bold]Stopping gasclaw...[/bold]")

    args = ["down"] if remove else ["stop"]
    result = _run_docker_compose(args, project_dir=project_path, check=False)

    if result.returncode != 0:
        # Fallback to direct docker commands
        result = _run_docker(["stop", DEFAULT_CONTAINER_NAME], check=False)
        if result.returncode != 0:
            console.print(f"[red]Failed to stop gasclaw:[/red] {result.stderr}")
            raise typer.Exit(code=1)

    console.print("[green]✅ Gasclaw stopped[/green]")


@app.command(name="status")
def status(
    project_dir: Annotated[
        Path,
        typer.Option("--project-dir", "-p", help="Project directory"),
    ] = Path("."),
) -> None:
    """Show gasclaw container status."""
    container_status = _get_container_status()

    table = Table(title="Gasclaw Container Status")
    table.add_column("Property", style="bold")
    table.add_column("Value")

    exists = container_status.get("exists") == "true"
    status_val = container_status.get("status", "unknown")
    health = container_status.get("health", "unknown")
    image = container_status.get("image", "unknown")

    # Status with color
    if status_val == "running":
        status_display = f"[green]{status_val}[/green]"
    elif status_val == "not_found":
        status_display = "[dim]not created[/dim]"
    else:
        status_display = f"[yellow]{status_val}[/yellow]"

    # Health with color
    if health == "healthy":
        health_display = f"[green]{health}[/green]"
    elif health == "unhealthy":
        health_display = f"[red]{health}[/red]"
    elif health == "unknown":
        health_display = "[dim]unknown[/dim]"
    else:
        health_display = health

    table.add_row("Container", "gasclaw")
    table.add_row("Exists", "[green]yes[/green]" if exists else "[red]no[/red]")
    table.add_row("Status", status_display)
    table.add_row("Health", health_display)
    table.add_row("Image", image)

    console.print(table)

    # Check config files
    project_path = project_dir.resolve()
    config_table = Table(title="Configuration Files")
    config_table.add_column("File")
    config_table.add_column("Status")

    env_file = project_path / ".env"
    compose_file = project_path / "docker-compose.yml"

    for f, label in [(env_file, ".env"), (compose_file, "docker-compose.yml")]:
        if f.exists():
            config_table.add_row(label, "[green]exists[/green]")
        else:
            config_table.add_row(label, "[red]missing[/red]")

    console.print(config_table)


@app.command()
def logs(
    project_dir: Annotated[
        Path,
        typer.Option("--project-dir", "-p", help="Project directory"),
    ] = Path("."),
    follow: Annotated[
        bool,
        typer.Option("--follow", "-f", help="Follow log output"),
    ] = False,
    tail: Annotated[
        int | None,
        typer.Option("--tail", "-n", help="Number of lines to show from end"),
    ] = None,
    source: Annotated[
        str | None,
        typer.Argument(help="Log source filter (optional)"),
    ] = None,
) -> None:
    """View gasclaw container logs."""
    project_path = project_dir.resolve()

    if not _container_exists():
        console.print("[red]Gasclaw container does not exist.[/red]")
        console.print("Run 'gasclaw start' first.")
        raise typer.Exit(code=1)

    args = ["logs"]
    if follow:
        args.append("-f")
    if tail is not None:
        args.extend(["--tail", str(tail)])
    args.append(DEFAULT_CONTAINER_NAME)

    # For logs, we stream directly to console instead of capturing
    cmd = _get_docker_compose_cmd() + args
    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]\n")

    try:
        subprocess.run(cmd, cwd=project_path, check=False)
    except KeyboardInterrupt:
        console.print("\n[yellow]Log streaming stopped.[/yellow]")


@app.command(name="config")
def config_cmd(
    key: Annotated[
        str | None,
        typer.Argument(help="Configuration key to get/set"),
    ] = None,
    value: Annotated[
        str | None,
        typer.Argument(help="Value to set (omit to get current value)"),
    ] = None,
    project_dir: Annotated[
        Path,
        typer.Option("--project-dir", "-p", help="Project directory"),
    ] = Path("."),
) -> None:
    """Get or set configuration values in .env file.

    Examples:
        gasclaw config                    # Show all config
        gasclaw config GASTOWN_KIMI_KEYS  # Get specific value
        gasclaw config GT_AGENT_COUNT 8   # Set value
    """
    project_path = project_dir.resolve()
    env_file = project_path / ".env"

    if not env_file.exists():
        console.print(f"[red]Error: {env_file} not found[/red]")
        console.print("Run 'gasclaw init' first.")
        raise typer.Exit(code=1)

    # Read current env file
    env_content = env_file.read_text()
    env_vars = _parse_env_file(env_content)

    # Show all config
    if key is None:
        table = Table(title="Gasclaw Configuration")
        table.add_column("Key", style="bold")
        table.add_column("Value")

        for k, v in sorted(env_vars.items()):
            # Mask sensitive values
            if "KEY" in k or "TOKEN" in k or "SECRET" in k:
                v = "***" if v else "(not set)"
            table.add_row(k, v)

        console.print(table)
        return

    # Get specific value
    if value is None:
        if key in env_vars:
            v = env_vars[key]
            # Mask sensitive values
            if "KEY" in key or "TOKEN" in key or "SECRET" in key:
                v = "***" if v else "(not set)"
            console.print(f"{key}={v}")
        else:
            console.print(f"[yellow]Key '{key}' not found in .env[/yellow]")
        return

    # Set value
    env_vars[key] = value
    new_content = _format_env_file(env_vars)
    env_file.write_text(new_content)
    console.print(f"[green]✅ Set {key}={value}[/green]")

    # Check if container is running and warn
    if _container_running():
        console.print(
            "[yellow]Note: Changes will take effect after restart:[/yellow] gasclaw restart"
        )


def _parse_env_file(content: str) -> dict[str, str]:
    """Parse .env file content into a dictionary."""
    env_vars = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            env_vars[key] = val
    return env_vars


def _format_env_file(env_vars: dict[str, str]) -> str:
    """Format env vars back to .env file content."""
    lines = ["# Gasclaw Environment Configuration\n"]
    for key, value in sorted(env_vars.items()):
        lines.append(f"{key}={value}\n")
    return "".join(lines)


@app.command(name="maintenance")
def maintenance_cmd(
    action: Annotated[
        str | None,
        typer.Argument(help="Action: trigger, pause, resume, or status"),
    ] = None,
    project_dir: Annotated[
        Path,
        typer.Option("--project-dir", "-p", help="Project directory"),
    ] = Path("."),
) -> None:
    """Control gasclaw maintenance mode.

    Examples:
        gasclaw maintenance         # Show maintenance status
        gasclaw maintenance trigger # Trigger a maintenance cycle
        gasclaw maintenance pause   # Pause automatic maintenance
        gasclaw maintenance resume  # Resume automatic maintenance
    """
    if not _container_running():
        console.print("[red]Gasclaw container is not running.[/red]")
        raise typer.Exit(code=1)

    # Map actions to commands inside container
    action_map = {
        "trigger": ["gasclaw", "maintain", "--once"],
        "pause": ["touch", "/tmp/gasclaw_maintenance_paused"],
        "resume": ["rm", "-f", "/tmp/gasclaw_maintenance_paused"],
        "status": ["test", "-f", "/tmp/gasclaw_maintenance_paused"],
    }

    if action is None or action == "status":
        # Check if paused
        result = _run_docker(
            ["exec", DEFAULT_CONTAINER_NAME, "test", "-f", "/tmp/gasclaw_maintenance_paused"],
            check=False,
        )
        is_paused = result.returncode == 0

        # Get maintenance info from container
        info_result = _run_docker(
            ["exec", DEFAULT_CONTAINER_NAME, "cat", "/tmp/gasclaw_maintenance_info.json"],
            check=False,
        )

        table = Table(title="Maintenance Status")
        table.add_column("Property", style="bold")
        table.add_column("Value")

        table.add_row("Status", "[yellow]PAUSED[/yellow]" if is_paused else "[green]ACTIVE[/green]")

        if info_result.returncode == 0:
            try:
                info = json.loads(info_result.stdout)
                table.add_row("Last Run", info.get("last_run", "unknown"))
                table.add_row("Next Run", info.get("next_run", "unknown"))
                table.add_row("Cycles", str(info.get("cycles", 0)))
            except json.JSONDecodeError:
                pass

        console.print(table)
        return

    if action not in action_map:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print(f"Valid actions: {', '.join(action_map.keys())}")
        raise typer.Exit(code=1)

    # Execute action in container
    cmd = action_map[action]
    result = _run_docker(["exec", DEFAULT_CONTAINER_NAME] + cmd, check=False)

    if result.returncode == 0:
        console.print(f"[green]✅ Maintenance {action} successful[/green]")
    else:
        # For status check, non-zero means not paused (active)
        if action == "status":
            console.print("[green]Maintenance is ACTIVE[/green]")
        else:
            console.print(f"[red]Failed to {action} maintenance:[/red] {result.stderr}")
            raise typer.Exit(code=1)


@app.command()
def restart(
    project_dir: Annotated[
        Path,
        typer.Option("--project-dir", "-p", help="Project directory"),
    ] = Path("."),
) -> None:
    """Restart the gasclaw container."""
    stop(project_dir=project_dir)
    console.print()
    start(project_dir=project_dir)


@app.command()
def update(
    project_dir: Annotated[
        Path,
        typer.Option("--project-dir", "-p", help="Project directory"),
    ] = Path("."),
    pull: Annotated[
        bool,
        typer.Option("--pull", "-u", help="Pull latest image before updating"),
    ] = True,
) -> None:
    """Update gasclaw to the latest version."""
    project_path = project_dir.resolve()

    console.print("[bold]Updating gasclaw...[/bold]")

    # Stop container if running
    was_running = _container_running()
    if was_running:
        console.print("Stopping container...")
        stop(project_dir=project_path)

    # Pull latest image
    if pull:
        console.print("Pulling latest image...")
        result = _run_docker(["pull", "ghcr.io/gastown-publish/gasclaw:latest"], check=False)
        if result.returncode != 0:
            console.print("[yellow]Warning: Failed to pull latest image[/yellow]")

    # Restart if was running
    if was_running:
        console.print("Restarting container...")
        start(project_dir=project_path)

    console.print("[green]✅ Update complete[/green]")


@app.command(name="version")
def version() -> None:
    """Show gasclaw version."""
    console.print(f"gasclaw {__version__}")


# Command aliases for convenience
@app.command(name="up", hidden=True)
def up(
    project_dir: Annotated[
        Path,
        typer.Option("--project-dir", "-p", help="Project directory containing docker-compose.yml"),
    ] = Path("."),
    build: Annotated[
        bool,
        typer.Option("--build", "-b", help="Build image before starting"),
    ] = False,
    detach: Annotated[
        bool,
        typer.Option("--detach", "-d", help="Run in detached mode"),
    ] = True,
) -> None:
    """Alias for 'start' - Start the gasclaw container."""
    start(project_dir=project_dir, build=build, detach=detach)


@app.command(name="down", hidden=True)
def down(
    project_dir: Annotated[
        Path,
        typer.Option("--project-dir", "-p", help="Project directory containing docker-compose.yml"),
    ] = Path("."),
    remove: Annotated[
        bool,
        typer.Option("--remove", "-r", help="Remove container after stopping"),
    ] = False,
) -> None:
    """Alias for 'stop' - Stop the gasclaw container."""
    stop(project_dir=project_dir, remove=remove)


@app.command(name="ps", hidden=True)
def ps(
    project_dir: Annotated[
        Path,
        typer.Option("--project-dir", "-p", help="Project directory"),
    ] = Path("."),
) -> None:
    """Alias for 'status' - Show gasclaw container status."""
    status(project_dir=project_dir)


@app.command(name="v", hidden=True)
def v() -> None:
    """Alias for 'version' - Show gasclaw version."""
    version()


def main() -> None:
    """Entry point for host CLI."""
    app()


if __name__ == "__main__":
    main()
