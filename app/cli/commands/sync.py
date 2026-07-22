"""Sync CLI command group definitions for Typer."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Optional
import typer
from rich.table import Table

from app.cli.common import console, get_container
from app.config import settings


sync_app = typer.Typer(
    name="sync",
    help="Incremental discovery, change detection, and synchronization engine.",
    no_args_is_help=False,
)


@sync_app.callback(invoke_without_command=True)
def sync_default(
    ctx: typer.Context,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum companies to fetch per provider. Default: 100."),
    ] = 100,
) -> None:
    """Synchronize all providers incrementally and detect changes."""
    if ctx.invoked_subcommand is not None:
        return

    container = get_container()
    from app.discover.seed import load_seed_slugs
    from app.discovery.registry import ProviderRegistry
    
    # Get all registered providers
    sources = ProviderRegistry.all_names()
    seed_map = load_seed_slugs(sources)

    console.print("[bold green]Starting incremental synchronization for all providers...[/bold green]")
    metrics_list = container.sync_engine.sync_all(sources, seed_map, limit)

    table = Table(title="Synchronization Results Summary", show_header=True)
    table.add_column("Provider", style="bold cyan")
    table.add_column("Duration", justify="right")
    table.add_column("Co. New", justify="right", style="green")
    table.add_column("Co. Upd", justify="right", style="yellow")
    table.add_column("Co. Del", justify="right", style="red")
    table.add_column("Jobs New", justify="right", style="green")
    table.add_column("Jobs Del", justify="right", style="red")
    table.add_column("HTTP Req", justify="right")
    table.add_column("Cache Hit", justify="right")

    for m in metrics_list:
        table.add_row(
            m.provider,
            f"{m.duration:.2f}s",
            str(m.companies_discovered),
            str(m.companies_updated),
            str(m.companies_removed),
            str(m.jobs_added),
            str(m.jobs_removed),
            str(m.http_requests),
            "YES" if m.cache_hits > 0 else "NO",
        )
    console.print(table)
    console.print()


@sync_app.command(name="provider")
def sync_provider(
    name: str = typer.Argument(..., help="Name of the provider to sync (e.g. greenhouse, lever)."),
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum companies to fetch. Default: 100."),
    ] = 100,
) -> None:
    """Synchronize a specific provider only."""
    container = get_container()
    from app.discover.seed import load_seed_slugs
    from app.discovery.registry import ProviderRegistry

    if not ProviderRegistry.has(name):
        console.print(f"[red]Error: Unknown provider '{name}'.[/red]")
        raise typer.Exit(code=1)

    seed_map = load_seed_slugs([name])

    console.print(f"[bold green]Starting synchronization for provider '{name}'...[/bold green]")
    m = asyncio.run(container.sync_engine.sync_provider(name, seed_map.get(name, []), limit))

    table = Table(title=f"Sync Results: {name}", show_header=True)
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", justify="right")
    table.add_row("Duration", f"{m.duration:.2f}s")
    table.add_row("Companies Discovered", str(m.companies_discovered))
    table.add_row("Companies Updated", str(m.companies_updated))
    table.add_row("Companies Removed (Soft-deleted)", str(m.companies_removed))
    table.add_row("Jobs Added", str(m.jobs_added))
    table.add_row("Jobs Removed", str(m.jobs_removed))
    table.add_row("HTTP Requests Made", str(m.http_requests))
    table.add_row("Cache Hits (Skipped)", str(m.cache_hits))
    console.print(table)
    console.print()


@sync_app.command(name="status")
def sync_status() -> None:
    """Show the current status of checkpoints for all registered providers."""
    container = get_container()
    from app.discovery.registry import ProviderRegistry
    
    checkpoints = container.sync_engine.sync_storage.load_all_checkpoints()
    
    table = Table(title="Provider Synchronization Checkpoints", show_header=True)
    table.add_column("Provider", style="bold cyan")
    table.add_column("Last Successful Run", style="green")
    table.add_column("Last Failed Run", style="red")
    table.add_column("Last Duration", justify="right")
    table.add_column("Processed Pages", justify="right")

    for name in ProviderRegistry.all_names():
        cp = checkpoints.get(name)
        if cp:
            last_ok = cp.last_successful_run.strftime("%Y-%m-%d %H:%M:%S") if cp.last_successful_run else "Never"
            last_fail = cp.last_failed_run.strftime("%Y-%m-%d %H:%M:%S") if cp.last_failed_run else "Never"
            dur = f"{cp.duration:.2f}s"
            pages = str(cp.processed_pages)
        else:
            last_ok = "Never"
            last_fail = "Never"
            dur = "0.00s"
            pages = "0"
            
        table.add_row(name, last_ok, last_fail, dur, pages)
        
    console.print(table)
    console.print()


@sync_app.command(name="history")
def sync_history() -> None:
    """Show history log of past synchronization runs."""
    container = get_container()
    history_entries = container.sync_engine.history.load_all()
    
    if not history_entries:
        console.print("[yellow]No synchronization history found.[/yellow]")
        return
        
    table = Table(title="Synchronization Execution History Log", show_header=True)
    table.add_column("Timestamp", style="bold white")
    table.add_column("Provider", style="bold cyan")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Co (New/Upd/Del)")
    table.add_column("Jobs (New/Del)")
    table.add_column("Error Message", style="dim red")

    for e in reversed(history_entries[-20:]):
        ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        status_str = "[green]SUCCESS[/green]" if e.status == "success" else "[red]FAILED[/red]"
        co_stats = f"{e.added_companies}/{e.updated_companies}/{e.removed_companies}"
        job_stats = f"{e.added_jobs}/{e.removed_jobs}"
        err = e.error_message or ""
        table.add_row(ts, e.provider, status_str, f"{e.duration:.2f}s", co_stats, job_stats, err)
        
    console.print(table)
    console.print()


@sync_app.command(name="reset")
def sync_reset() -> None:
    """Wipe checkpoints, snapshots, and execution history to start fresh."""
    container = get_container()
    container.sync_engine.sync_storage.reset()
    container.sync_engine.history.clear()
    console.print("[bold green]✓ Synchronization state and history reset successfully.[/bold green]")
