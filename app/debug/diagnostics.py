"""Developer diagnostics and debugging tools for Hiring Radar."""

from __future__ import annotations

from pathlib import Path
from rich.table import Table
from app.cli.common import console, get_container
from app.config import settings
from app.agent.state_validator import validate_system_state


def run_doctor() -> None:
    """Check health, keys, configuration files, and backups."""
    console.print("\n[bold purple]🔍 Hiring Radar System Health Diagnostics[/bold purple]\n")
    
    # 1. API Keys
    api_key_status = "[green]OK[/green]" if settings.openrouter_api_key else "[red]Missing (OPENROUTER_API_KEY)[/red]"
    console.print(f"- OpenRouter Key: {api_key_status}")
    
    # 2. Output directory
    out_dir = settings.output_dir
    dir_status = f"[green]OK ({out_dir})[/green]" if out_dir.exists() else f"[yellow]Not Created ({out_dir})[/yellow]"
    console.print(f"- Output Directory: {dir_status}")
    
    # 3. Resume
    resume_path = settings.resume_path
    resume_status = f"[green]OK ({resume_path})[/green]" if resume_path and resume_path.exists() else f"[yellow]Missing ({resume_path})[/yellow]"
    console.print(f"- Active Resume: {resume_status}")
    
    # 4. Backup Snapshots check
    backup_exists = (out_dir / "companies.json.backup").exists()
    backup_status = "[green]Present[/green]" if backup_exists else "[yellow]None[/yellow]"
    console.print(f"- Database Backups: {backup_status}")

    # 5. Run Cross-Repository validation warnings
    warnings = validate_system_state()
    if warnings:
        console.print("\n[bold yellow]⚠️  State Mismatches / Warnings found:[/bold yellow]")
        for w in warnings:
            console.print(f"  - {w}")
    else:
        console.print("\n[bold green]✓ No system state warnings detected. All repositories are synchronized![/bold green]")


def inspect_repositories() -> None:
    """Print detailed sizes, counts, and paths of all JSON database files."""
    container = get_container()
    table = Table(title="Repository Diagnostics", show_header=True, header_style="bold cyan")
    table.add_column("Repository", style="magenta")
    table.add_column("Path", style="dim white")
    table.add_column("Size (Bytes)", style="yellow")
    table.add_column("Records Count", style="green")

    repos = [
        ("Companies", container.company_repo.filepath, lambda: len(container.company_repo.load_all())),
        ("Applications", container.application_repo.filepath, lambda: len(container.application_repo.load_all())),
        ("Agent Memory", container.memory_repo.filepath, lambda: len(container.memory_repo.load().get("preferences", {}))),
        ("Saved Searches", container.saved_search_repo.filepath, lambda: len(container.saved_search_repo.load_all())),
        ("Monitoring Events", container.monitoring_repo.events_path, lambda: len(container.monitoring_repo.load_events())),
    ]

    for name, path, count_fn in repos:
        p = Path(path)
        size_str = str(p.stat().st_size) if p.exists() else "0 (N/A)"
        try:
            count = count_fn()
        except Exception:
            count = "Error"
        table.add_row(name, str(p), size_str, str(count))

    console.print(table)


def inspect_memory_state() -> None:
    """Print the contents of the agent persistent memory."""
    container = get_container()
    mem = container.memory_repo.load()
    
    console.print("\n[bold purple]🧠 Persistent Memory State Summary[/bold purple]\n")
    console.print("[bold cyan]Preferences:[/bold cyan]")
    prefs = mem.get("preferences", {})
    if not prefs:
        console.print("  None")
    for k, v in prefs.items():
        console.print(f"  {k}: {v}")

    console.print("\n[bold cyan]Rejected Companies:[/bold cyan]")
    rejected = mem.get("rejected_companies", [])
    if not rejected:
        console.print("  None")
    for r in rejected:
        console.print(f"  - {r}")

    console.print("\n[bold cyan]Past Decisions Audit (Last 5):[/bold cyan]")
    decisions = mem.get("past_decisions", [])
    if not decisions:
        console.print("  None")
    for d in decisions[-5:]:
        console.print(f"  [{d.get('date')}] {d.get('action') or d.get('summary')}")
