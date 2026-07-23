"""UI Dashboard panel displaying background execution queue and workers statistics."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from app.cli.common import get_container

console = Console()


def show_runtime_dashboard() -> None:
    """Print a rich visual panel summarising background execution engine status."""
    container = get_container()
    if not container or not hasattr(container, "runtime") or not container.runtime:
        console.print("[red]Autonomous Runtime Engine is not initialized.[/red]")
        return
        
    runtime = container.runtime
    queue_list = runtime.queue.list_queued()
    active_wf = runtime.list_active()
    schedules = runtime.scheduler.load_schedules()
    history = list(runtime.history.load_all().values())

    table = Table(title="🤖 Hiring Radar Agent Runtime & Task Queue Dashboard", show_header=True)
    table.add_column("Indicator", style="cyan")
    table.add_column("Current Status", style="white")
    table.add_column("Metrics / Details", style="yellow")

    table.add_row("Background Workers", "Active Daemon", f"{getattr(runtime.settings, 'background_workers', 2)} workers running")
    table.add_row("Queue Size", "Pending Queue", f"{len(queue_list)} jobs queued")
    table.add_row("Running Workflows", "Executing", f"{len(active_wf)} active graphs")
    table.add_row("Scheduler Service", "Cron / Intervals", f"{len(schedules)} recurring jobs scheduled")
    
    completed_cnt = len([x for x in history if getattr(x, "status", "") == "completed"])
    failed_cnt = len([x for x in history if getattr(x, "status", "") == "failed"])
    table.add_row("Execution History", "Processed Runs", f"✓ {completed_cnt} completed | ✗ {failed_cnt} failed")

    console.print(Panel(table, border_style="purple"))
