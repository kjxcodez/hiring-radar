from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table
from typing import Optional

from app.cli.common import get_container
from app.runtime.state import ExecutionStatus
from app.runtime.triggers import TriggerSource

console = Console()


def jobs_list() -> None:
    """List currently active running and queued background jobs."""
    container = get_container()
    runtime = container.runtime
    
    active = runtime.list_active()
    queued = runtime.queue.list_queued()
    
    if not active and not queued:
        console.print("[yellow]No active or queued jobs.[/yellow]")
        return
        
    table = Table(title="Active & Queued Background Jobs")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Workflow", style="green")
    table.add_column("Status", style="bold yellow")
    table.add_column("Trigger", style="magenta")
    table.add_column("Submitted At", style="blue")
    
    for job in active:
        table.add_row(
            job.id,
            job.workflow_name,
            job.status.value.upper(),
            job.trigger.value.upper(),
            job.submitted_at.isoformat(),
        )
    for job in queued:
        table.add_row(
            job.id,
            job.workflow_name,
            job.status.value.upper(),
            job.trigger.value.upper(),
            job.submitted_at.isoformat(),
        )
        
    console.print(table)


def jobs_history(
    limit: int = typer.Option(20, help="Maximum number of historical executions to display.")
) -> None:
    """Display execution history of background jobs."""
    container = get_container()
    runtime = container.runtime
    
    history = list(runtime.history.load_all().values())
    if not history:
        console.print("[yellow]No execution history found.[/yellow]")
        return
        
    # Sort by submitted_at descending
    history.sort(key=lambda x: x.submitted_at, reverse=True)
    history = history[:limit]
    
    table = Table(title="Job Execution History")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Workflow", style="green")
    table.add_column("Status", style="bold")
    table.add_column("Trigger", style="magenta")
    table.add_column("Submitted At", style="blue")
    table.add_column("Duration", style="yellow")
    table.add_column("Error", style="red")
    
    for job in history:
        if job.status == ExecutionStatus.COMPLETED:
            status_str = f"[green]{job.status.value.upper()}[/green]"
        elif job.status == ExecutionStatus.FAILED:
            status_str = f"[red]{job.status.value.upper()}[/red]"
        else:
            status_str = f"[yellow]{job.status.value.upper()}[/yellow]"
            
        duration_str = f"{job.duration:.2f}s" if job.duration is not None else "-"
        error_str = job.error or "-"
        if len(error_str) > 40:
            error_str = error_str[:37] + "..."
            
        table.add_row(
            job.id,
            job.workflow_name,
            status_str,
            job.trigger.value.upper(),
            job.submitted_at.isoformat(),
            duration_str,
            error_str,
        )
        
    console.print(table)


def jobs_cancel(
    job_id: str = typer.Argument(..., help="Full or prefix UUID of the target job to cancel.")
) -> None:
    """Cancel a running or queued background execution."""
    container = get_container()
    runtime = container.runtime
    
    # Try exact match or prefix match in history
    history = runtime.history.load_all()
    target_id = None
    for eid in history:
        if eid.startswith(job_id):
            target_id = eid
            break
            
    if not target_id:
        console.print(f"[red]Error: Job with ID '{job_id}' not found in history.[/red]")
        raise typer.Exit(code=1)
        
    if runtime.cancel(target_id):
        console.print(f"[green]Successfully cancelled job {target_id}[/green]")
    else:
        console.print(f"[red]Error: Could not cancel job {target_id} (might be completed or already cancelled).[/red]")
        raise typer.Exit(code=1)


def jobs_retry(
    job_id: str = typer.Argument(..., help="Full or prefix UUID of the failed job to retry.")
) -> None:
    """Retry a failed background execution."""
    container = get_container()
    runtime = container.runtime
    
    history = runtime.history.load_all()
    target_exec = None
    for eid, execution in history.items():
        if eid.startswith(job_id):
            target_exec = execution
            break
            
    if not target_exec:
        console.print(f"[red]Error: Job with ID '{job_id}' not found.[/red]")
        raise typer.Exit(code=1)
        
    if target_exec.status != ExecutionStatus.FAILED:
        console.print(f"[yellow]Job {target_exec.id} is not in FAILED state (current: {target_exec.status.value}).[/yellow]")
        raise typer.Exit(code=1)
        
    new_job = runtime.submit(
        target_exec.workflow_name,
        trigger=TriggerSource.MANUAL,
        **target_exec.metadata
    )
    console.print(f"[green]Retrying job {target_exec.id} -> Submitted new job with ID {new_job.id}[/green]")
