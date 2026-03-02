"""Gasclaw CLI — start, stop, status, update."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from gasclaw import __version__
from gasclaw.bootstrap import bootstrap, monitor_loop
from gasclaw.config import load_config
from gasclaw.gastown.lifecycle import stop_all
from gasclaw.health import check_agent_activity, check_health
from gasclaw.kimigas.key_pool import KeyPool
from gasclaw.logging_config import get_logger, setup_logging
from gasclaw.maintenance import maintenance_loop, run_maintenance_cycle
from gasclaw.updater.applier import apply_updates
from gasclaw.updater.checker import check_versions

# Initialize logging on module import
setup_logging()
logger = get_logger(__name__)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"gasclaw {__version__}")
        raise typer.Exit()


app = typer.Typer(help="Gasclaw — Gastown + OpenClaw + KimiGas in one container.")
console = Console()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Gasclaw CLI."""
    pass


@app.command()
def start(
    gt_root: Path = typer.Option(Path("/workspace/gt"), help="Gastown root directory"),
    project_dir: Path | None = typer.Option(
        None, help="Project directory for activity checks (overrides config)"
    ),
) -> None:
    """Start gasclaw: bootstrap all services and enter monitor loop."""
    try:
        config = load_config()
        logger.info("Configuration loaded successfully")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(code=1) from None

    # Override project_dir if provided via CLI
    if project_dir is not None:
        config.project_dir = str(project_dir)
        logger.debug(f"Project directory overridden to: {project_dir}")

    console.print("[bold]Starting gasclaw...[/bold]")
    logger.info("Starting gasclaw bootstrap sequence")
    try:
        bootstrap(config, gt_root=gt_root)
        logger.info("Bootstrap completed successfully")
    except Exception as e:
        logger.exception("Bootstrap failed")
        console.print(f"[red]Bootstrap failed:[/red] {e}")
        raise typer.Exit(code=1) from None
    console.print("[green]All services started. Entering monitor loop.[/green]")
    try:
        monitor_loop(config)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        console.print("\n[yellow]Shutting down...[/yellow]")


@app.command()
def stop() -> None:
    """Stop all gasclaw services."""
    console.print("Stopping all services...")
    stop_all()
    console.print("[green]All services stopped.[/green]")


@app.command()
def status() -> None:
    """Show health status of all subsystems."""
    report = check_health()

    try:
        config = load_config()
        activity = check_agent_activity(
            project_dir=config.project_dir,
            deadline_seconds=config.activity_deadline,
        )
        report.activity = activity
        pool = KeyPool(config.gastown_kimi_keys)
        report.key_pool = pool.status()
    except ValueError:
        # Config not loaded, skip optional fields
        pass

    table = Table(title="Gasclaw Status")
    table.add_column("Service", style="bold")
    table.add_column("Status")

    for svc in ["dolt", "daemon", "mayor", "openclaw"]:
        val = getattr(report, svc, "unknown")
        style = "green" if val == "healthy" else "red"
        table.add_row(svc, f"[{style}]{val}[/{style}]")

    table.add_row("agents", str(len(report.agents)))
    if report.key_pool:
        avail = report.key_pool.get("available", "?")
        total = report.key_pool.get("total", "?")
        table.add_row("key pool", f"{avail}/{total} available")
    if report.activity:
        compliant = report.activity.get("compliant", False)
        style = "green" if compliant else "red"
        status = "compliant" if compliant else "NOT COMPLIANT"
        table.add_row("activity", f"[{style}]{status}[/{style}]")

    console.print(table)


@app.command()
def update() -> None:
    """Check and apply updates to all dependencies."""
    console.print("[bold]Checking versions...[/bold]")
    versions = check_versions()
    for name, ver in versions.items():
        console.print(f"  {name}: {ver}")

    console.print("\n[bold]Applying updates...[/bold]")
    results = apply_updates()
    for name, result in results.items():
        style = "green" if result == "updated" else "yellow"
        console.print(f"  {name}: [{style}]{result}[/{style}]")


@app.command()
def version() -> None:
    """Show gasclaw version."""
    console.print(f"gasclaw {__version__}")


@app.command()
def maintain(
    once: bool = typer.Option(False, help="Run once and exit (don't loop)"),
    interval: int = typer.Option(300, help="Seconds between cycles (default: 300)"),
) -> None:
    """Run maintenance loop: check and merge PRs, monitor issues."""
    console.print("[bold]Starting maintenance...[/bold]")

    if once:
        console.print("Running single maintenance cycle...")
        try:
            results = run_maintenance_cycle()
            console.print(f"[green]Cycle complete:[/green] {results}")
        except Exception as e:
            logger.exception("Maintenance cycle failed")
            console.print(f"[red]Maintenance failed:[/red] {e}")
            raise typer.Exit(code=1) from None
    else:
        console.print(f"[green]Entering maintenance loop (interval={interval}s)...[/green]")
        console.print("Press Ctrl+C to stop")
        try:
            maintenance_loop(interval=interval)
        except KeyboardInterrupt:
            console.print("\n[yellow]Maintenance loop stopped[/yellow]")
