"""Company Intelligence CLI command definitions."""

from typing import Annotated, Dict, Optional
import typer
from rich.table import Table

from app.cli.common import console, get_container
from app.config import settings


intelligence_app = typer.Typer(
    name="intelligence",
    help="Continuous Company Intelligence Engine & Knowledge Graph manager.",
    no_args_is_help=False,
)


@intelligence_app.callback(invoke_without_command=True)
def intelligence_default(
    ctx: typer.Context,
    force: Annotated[
        bool,
        typer.Option("--force", help="Wipe caches and force full re-enrichment of all companies."),
    ] = False,
) -> None:
    """Enrich all companies and rebuild the Knowledge Graph."""
    if ctx is not None and ctx.invoked_subcommand is not None:
        return

    container = get_container()
    console.print("[bold green]Starting Company Intelligence Enrichment Pipeline...[/bold green]")
    
    container.workflow_engine.run("intelligence", force=force)
    
    console.print("[bold green]✓ Enrichment pipeline execution finished successfully.[/bold green]")
    console.print()


@intelligence_app.command(name="company")
def show_company_intelligence(
    name: str = typer.Argument(..., help="Name of the company to view (case-insensitive substring match)."),
) -> None:
    """Show detailed company intelligence profile."""
    container = get_container()
    try:
        co = container.company_repo.find_by_name(name)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1)

    if not co.intelligence:
        console.print(f"[yellow]No intelligence profile available for '{co.name}'.[/yellow]")
        console.print("  Run [bold]hiring-radar intelligence[/bold] to enrich companies.")
        return

    intel = co.intelligence

    console.print()
    console.print(f"[bold cyan]Company Intelligence Profile: {co.name}[/bold cyan]")
    console.print(f"  [dim]Domain:[/dim] {co.domain or '—'} | [dim]Size:[/dim] {co.company_size or '—'}")
    console.print()

    # 1. Business
    table_bus = Table(title="Business Info", show_header=False, title_justify="left")
    table_bus.add_row("Industry", intel.business.industry or "—")
    table_bus.add_row("Category", intel.business.category or "—")
    table_bus.add_row("Headquarters", intel.business.headquarters or "—")
    table_bus.add_row("Remote Policy", intel.business.remote_policy or "—")
    table_bus.add_row("Founded Year", str(intel.business.founded_year or "—"))
    console.print(table_bus)
    console.print()

    # 2. Engineering Stack
    table_eng = Table(title="Engineering Stack", show_header=True)
    table_eng.add_column("Category", style="bold white")
    table_eng.add_column("Technologies", style="bold green")
    table_eng.add_row("Languages", ", ".join(intel.engineering.languages) or "—")
    table_eng.add_row("Frameworks", ", ".join(intel.engineering.frameworks) or "—")
    table_eng.add_row("Cloud", ", ".join(intel.engineering.cloud) or "—")
    table_eng.add_row("Databases", ", ".join(intel.engineering.databases) or "—")
    table_eng.add_row("CI/CD", ", ".join(intel.engineering.ci_cd) or "—")
    table_eng.add_row("AI Stack", ", ".join(intel.engineering.ai_stack) or "—")
    console.print(table_eng)
    console.print()

    # 3. Hiring Trends
    table_hir = Table(title="Hiring Trends", show_header=False, title_justify="left")
    table_hir.add_row("Hiring Velocity", intel.hiring.hiring_velocity.upper())
    table_hir.add_row("Open Roles Count", str(intel.hiring.open_roles))
    table_hir.add_row("Active Departments", ", ".join(intel.hiring.departments) or "—")
    
    seniority_str = ", ".join(f"{k}: {int(v*100)}%" for k, v in intel.hiring.seniority_distribution.items() if v > 0)
    table_hir.add_row("Seniority Mix", seniority_str or "—")
    table_hir.add_row("Locations", ", ".join(intel.hiring.geographic_distribution) or "—")
    console.print(table_hir)
    console.print()

    # 4. GitHub OSS
    table_git = Table(title="GitHub Activity", show_header=False, title_justify="left")
    table_git.add_row("Org Name", intel.github.organization or "—")
    table_git.add_row("Total Stars", str(intel.github.stars))
    table_git.add_row("Activity Level", intel.github.activity.upper())
    table_git.add_row("Primary Languages", ", ".join(intel.github.languages) or "—")
    table_git.add_row("Estimated Contributors", str(intel.github.contributors))
    console.print(table_git)
    console.print()


@intelligence_app.command(name="summary")
def show_company_summary(
    name: str = typer.Argument(..., help="Name of the company to view (case-insensitive substring match)."),
) -> None:
    """Show AI-generated executive and technical outreach summaries."""
    container = get_container()
    try:
        co = container.company_repo.find_by_name(name)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1)

    console.print()
    console.print(f"[bold cyan]AI Summary Briefing: {co.name}[/bold cyan]")
    console.print()
    console.print(f"[bold white]Executive Summary:[/bold white]")
    console.print(f"  {co.ai_summary or '—'}")
    console.print()

    if co.intelligence:
        console.print(f"[bold white]Engineering Overview:[/bold white]")
        console.print(f"  {co.intelligence.signals.funding_stage or '—'} Startup ({co.intelligence.signals.startup_maturity.upper()})")
        console.print(f"  OSS Friendliness: {int(co.intelligence.signals.oss_friendliness * 100)}% | AI Adoption: {int(co.intelligence.signals.ai_adoption * 100)}%")
        console.print()

    console.print(f"[bold white]Outreach Talking Points:[/bold white]")
    if co.ai_talking_points:
        for pt in co.ai_talking_points:
            console.print(f"  • {pt}")
    else:
        console.print("  —")
    console.print()


@intelligence_app.command(name="technologies")
def list_technologies() -> None:
    """List detected technologies sorted by frequency."""
    container = get_container()
    companies = container.company_repo.load_all()
    
    freq: Dict[str, int] = {}
    for co in companies:
        if co.intelligence:
            intel = co.intelligence
            # Aggregate all tech fields
            all_techs = (
                intel.engineering.languages
                + intel.engineering.frameworks
                + intel.engineering.infrastructure
                + intel.engineering.cloud
                + intel.engineering.databases
                + intel.engineering.ci_cd
                + intel.engineering.ai_stack
            )
            for t in all_techs:
                freq[t] = freq.get(t, 0) + 1

    if not freq:
        console.print("[yellow]No technology indicators detected yet.[/yellow]")
        return

    table = Table(title="Detected Technology Index", show_header=True)
    table.add_column("Technology", style="bold cyan")
    table.add_column("Mentions / Companies Using", justify="right", style="bold green")

    for tech, count in sorted(freq.items(), key=lambda x: x[1], reverse=True):
        table.add_row(tech, str(count))

    console.print()
    console.print(table)
    console.print()


@intelligence_app.command(name="refresh")
def force_refresh() -> None:
    """Wipe cache signatures and force full re-enrichment of all companies."""
    container = get_container()
    console.print("[bold green]Refreshing company intelligence cache...[/bold green]")
    container.workflow_engine.run("intelligence", force=True)
    console.print("[bold green]✓ Company intelligence refreshed.[/bold green]")


@intelligence_app.command(name="graph")
def show_graph_metrics() -> None:
    """Show structural metrics for the Knowledge Graph index."""
    container = get_container()
    from app.intelligence.graph import KnowledgeGraph
    
    graph_path = container.settings.output_dir / "knowledge_graph.json"
    graph = KnowledgeGraph()
    graph.load(graph_path, container.company_repo.storage)

    total_nodes = len(graph.nodes)
    total_edges = len(graph.edges)

    node_types: Dict[str, int] = {}
    for n in graph.nodes.values():
        node_types[n.label] = node_types.get(n.label, 0) + 1

    console.print()
    console.print("[bold cyan]Knowledge Graph Index Metrics[/bold cyan]")
    console.print(f"  [dim]Index Path:[/dim] {graph_path}")
    console.print()
    console.print(f"  Total Vertices (Nodes): [bold]{total_nodes}[/bold]")
    console.print(f"  Total Links (Edges):    [bold]{total_edges}[/bold]")
    console.print()
    
    table = Table(title="Node Type Distribution", show_header=True)
    table.add_column("Node Label", style="bold cyan")
    table.add_column("Count", justify="right", style="bold white")
    for lbl, cnt in sorted(node_types.items(), key=lambda x: x[1], reverse=True):
        table.add_row(lbl, str(cnt))
    console.print(table)
    console.print()
