"""Hiring Intelligence Monitoring CLI commands."""

from __future__ import annotations

import typer
from rich.table import Table
from rich.panel import Panel

from app.cli.common import console, get_container

# Create Typer sub-app
monitor_app = typer.Typer(
    name="monitor",
    help="Continuous hiring intelligence monitoring, change detection, alerts & digests.",
    no_args_is_help=False,
)


@monitor_app.callback(invoke_without_command=True)
def monitor_callback(
    ctx: typer.Context,
) -> None:
    """Hiring intelligence monitoring command group callback."""
    if ctx.invoked_subcommand is not None:
        return
    # If no subcommand, show the daily digest
    view_digest()


@monitor_app.command(name="run")
def run_monitoring(
    force: bool = typer.Option(False, "--force", help="Force monitoring pipeline run and recalculate alerts."),
) -> None:
    """Execute change detection pipeline on all companies, jobs, recommendations, and CRM statuses."""
    container = get_container()
    console.print("[bold green]Executing Change Detection and Monitoring Engine...[/bold green]")
    try:
        events = container.monitoring_engine.run_monitoring(force=force)
        console.print(f"\n[green]✓ Monitoring execution completed successfully.[/green]")
        console.print(f"  [bold]Events detected today:[/bold] {len(events)}")
    except Exception as exc:
        console.print(f"[red]Error during monitoring pipeline run: {exc}[/red]")
        raise typer.Exit(code=1)


@monitor_app.command(name="events")
def list_events() -> None:
    """List all detected change events."""
    container = get_container()
    events = container.monitoring_repo.load_events()
    if not events:
        console.print("[yellow]No change events found in repository.[/yellow]")
        console.print("  Run [bold]hiring-radar monitor run[/bold] first to analyze changes.")
        return

    table = Table(title="Detected Hiring Change Events", show_header=True, header_style="bold magenta")
    table.add_column("Timestamp", style="dim white")
    table.add_column("Company", style="bold cyan")
    table.add_column("Event Type", style="bold white")
    table.add_column("Change details", style="italic dim white")
    table.add_column("Severity", style="bold yellow")

    for ev in events:
        details = "—"
        if ev.get("previous_value") is not None or ev.get("current_value") is not None:
            details = f"{ev.get('previous_value')} -> {ev.get('current_value')}"
        elif ev.get("metadata", {}).get("title"):
            details = ev.get("metadata", {}).get("title")

        table.add_row(
            ev.get("timestamp", "")[:16].replace("T", " "),
            ev.get("company_name", "—"),
            ev.get("event_type", "—"),
            details,
            ev.get("severity", "—"),
        )

    console.print()
    console.print(table)
    console.print()


@monitor_app.command(name="alerts")
def list_alerts() -> None:
    """List all prioritized hiring intelligence alerts."""
    container = get_container()
    alerts = container.monitoring_repo.load_alerts()
    if not alerts:
        console.print("[yellow]No alerts found in repository.[/yellow]")
        return

    table = Table(title="Hiring Intelligence Alert Board", show_header=True, header_style="bold red")
    table.add_column("Severity", style="bold yellow")
    table.add_column("Company", style="bold cyan")
    table.add_column("Alert Title", style="bold white")
    table.add_column("Description", style="dim white")

    # Sort alerts by severity priority
    sev_priority = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Informational": 4}
    sorted_alerts = sorted(alerts, key=lambda a: sev_priority.get(a.get("severity", "Informational"), 5))

    for a in sorted_alerts:
        table.add_row(
            a.get("severity", "—"),
            a.get("company_name", "—"),
            a.get("title", "—"),
            a.get("description", "—"),
        )

    console.print()
    console.print(table)
    console.print()


@monitor_app.command(name="digest")
def view_digest() -> None:
    """Show the latest AI summarized daily hiring intelligence digest."""
    container = get_container()
    digest = container.monitoring_repo.load_digest()
    if not digest:
        console.print("[yellow]No daily digest found in repository.[/yellow]")
        console.print("  Run [bold]hiring-radar monitor run[/bold] first to analyze changes.")
        return

    console.print()
    console.print(Panel(
        f"[bold yellow]Executive Summary:[/bold yellow]\n{digest.get('executive_summary', '—')}\n\n"
        f"[bold cyan]Top Opportunities:[/bold cyan]\n" + ("\n".join(f"  • {item}" for item in digest.get("top_opportunities", [])) or "  • None") + "\n\n"
        f"[bold green]New Remote Roles:[/bold green]\n" + ("\n".join(f"  • {item}" for item in digest.get("new_remote_roles", [])) or "  • None") + "\n\n"
        f"[bold magenta]Hiring Trends:[/bold magenta]\n" + ("\n".join(f"  • {item}" for item in digest.get("biggest_hiring_trends", [])) or "  • None") + "\n\n"
        f"[bold white]Suggested Actions:[/bold white]\n" + ("\n".join(f"  • {item}" for item in digest.get("suggested_actions", [])) or "  • None"),
        title="AI Daily Hiring Intelligence Digest",
        border_style="cyan"
    ))
    console.print()


@monitor_app.command(name="company")
def monitor_company(
    name: str = typer.Argument(..., help="Name of the company to view changes for."),
) -> None:
    """View events and alerts for a single target company."""
    container = get_container()
    events = container.monitoring_repo.load_events()
    alerts = container.monitoring_repo.load_alerts()

    matched_events = [e for e in events if name.lower() in e.get("company_name", "").lower()]
    matched_alerts = [a for a in alerts if name.lower() in a.get("company_name", "").lower()]

    if not matched_events and not matched_alerts:
        console.print(f"[yellow]No monitoring details found for company '{name}'.[/yellow]")
        return

    console.print(f"\n[bold cyan]Hiring Intelligence Report: {name}[/bold cyan]\n")
    if matched_alerts:
        console.print("[bold red]Active Alerts:[/bold red]")
        for a in matched_alerts:
            console.print(f"  [{a.get('severity')}] [bold]{a.get('title')}[/bold] - {a.get('description')}")
        console.print()

    if matched_events:
        console.print("[bold white]Change Event Log:[/bold white]")
        for e in matched_events:
            ts = e.get("timestamp", "")[:16].replace("T", " ")
            details = f"{e.get('previous_value')} -> {e.get('current_value')}" if e.get("previous_value") else e.get("metadata", {}).get("title", "")
            console.print(f"  {ts} | [bold]{e.get('event_type')}[/bold] - {details}")
        console.print()


@monitor_app.command(name="job")
def monitor_job(
    job_url: str = typer.Argument(..., help="URL of the job opening to view changes for."),
) -> None:
    """View events for a single job opening by URL."""
    container = get_container()
    events = container.monitoring_repo.load_events()
    matched_events = [e for e in events if e.get("job_url") == job_url]

    if not matched_events:
        console.print(f"[yellow]No event logs found for job URL '{job_url}'.[/yellow]")
        return

    console.print(f"\n[bold cyan]Job Event Log: {job_url}[/bold cyan]\n")
    for e in matched_events:
        ts = e.get("timestamp", "")[:16].replace("T", " ")
        details = f"{e.get('previous_value')} -> {e.get('current_value')}" if e.get("previous_value") else e.get("metadata", {}).get("title", "")
        console.print(f"  {ts} | [bold]{e.get('event_type')}[/bold] - {details}")
    console.print()


@monitor_app.command(name="recommendation")
def monitor_recommendation() -> None:
    """View recommendation score and rank shift events."""
    container = get_container()
    events = container.monitoring_repo.load_events()
    matched = [e for e in events if e.get("event_type") == "RecommendationChanged"]

    if not matched:
        console.print("[yellow]No recommendation score change events found.[/yellow]")
        return

    table = Table(title="Recommendation Shifts Log", show_header=True)
    table.add_column("Timestamp", style="dim white")
    table.add_column("Company", style="bold cyan")
    table.add_column("Score Shift", style="bold green")

    for e in matched:
        table.add_row(
            e.get("timestamp", "")[:16].replace("T", " "),
            e.get("company_name", "—"),
            f"{e.get('previous_value')} -> {e.get('current_value')}",
        )
    console.print(table)


@monitor_app.command(name="application")
def monitor_application() -> None:
    """View CRM application stage transition events."""
    container = get_container()
    events = container.monitoring_repo.load_events()
    matched = [e for e in events if e.get("event_type") == "ApplicationStatusChanged"]

    if not matched:
        console.print("[yellow]No CRM application status change events found.[/yellow]")
        return

    table = Table(title="CRM Application Phase Transitions Log", show_header=True)
    table.add_column("Timestamp", style="dim white")
    table.add_column("Company", style="bold cyan")
    table.add_column("Status Change", style="bold green")

    for e in matched:
        table.add_row(
            e.get("timestamp", "")[:16].replace("T", " "),
            e.get("company_name", "—"),
            f"{e.get('previous_value')} -> {e.get('current_value')}",
        )
    console.print(table)


@monitor_app.command(name="clear-cache")
def clear_cache() -> None:
    """Wipe monitoring snapshots and reset cache, clear alerts and digests."""
    container = get_container()
    console.print("[bold yellow]Wiping monitoring database files and snapshots cache...[/bold yellow]")
    
    # 1. Clear repo
    container.monitoring_repo.clear()

    # 2. Clear snapshots
    snap_engine = container.monitoring_engine
    for path in [snap_engine.companies_snap_path, snap_engine.recs_snap_path, snap_engine.apps_snap_path]:
        if path.exists():
            path.unlink()

    console.print("[green]✓ Monitoring cache cleared successfully.[/green]")
