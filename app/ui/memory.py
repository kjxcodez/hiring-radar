"""UI Dashboard panel displaying active memory statistics."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from app.memory.store import global_memory_store

console = Console()


def show_memory_dashboard() -> None:
    """Print a rich visual summary of agent long-term memory."""
    store = global_memory_store
    
    episodic = store.load_records("episodic")
    working = store.load_records("working")
    profile = store.load_profile()
    prefs = store.load_preferences()
    summaries = store.load_summaries()
    
    table = Table(title="🧠 Hiring Radar Long-Term Memory Dashboard", show_header=True)
    table.add_column("Category", style="cyan")
    table.add_column("Metric / Status", style="white")
    table.add_column("Value / Details", style="yellow")
    
    table.add_row("Working Memory", "Current Session", f"{len(working)} records active")
    table.add_row("Episodic Memory", "Persisted Events", f"{len(episodic)} records saved")
    table.add_row("Evolving Profile", "User Preferences", f"{len(profile.tech_stack)} stack keywords, {len(profile.preferred_locations)} locations")
    table.add_row("Free-Form Preferences", "Settings Dictionary", f"{len(prefs.preferences)} keys recorded")
    table.add_row("Summaries Archive", "Compressed Conversations", f"{len(summaries)} summaries saved")
    
    retrieval_count = sum(r.retrieval_count for r in episodic)
    table.add_row("Memory Retrievals", "Recall Frequency", f"{retrieval_count} total hits")
    
    console.print(Panel(table, border_style="purple"))
