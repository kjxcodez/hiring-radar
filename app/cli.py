"""hiring-radar CLI entrypoint.

Run as:
    python -m app.cli <command>      # always works, no install needed
    hiring-radar <command>           # after `pip install -e .` (see pyproject.toml)
"""

from __future__ import annotations

import re
import os
import time
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Optional, Any

import orjson
import json
import typer
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.prompt import Prompt

from app.config import settings, yaml_config
from app.discover import SOURCE_REGISTRY
from app.models import Company, ApplicationStatus, Application
from app.exporters import export_csv, export_json
from app.resume.parser import load_resume_text
from app.resume.versions import resolve_resume_version, list_resume_versions
from app.resume.suggestions import suggest_resume_tailoring
from app.tracker.status import load_applications, save_applications, set_status
from app.discover.seed import resolve_seed_companies, load_seed_slugs
from app.saved_search import SavedSearch, load_saved_searches
from app.utils import setup_logging
from app.services.config import ServiceContainer

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="hiring-radar",
    help="Discover hiring companies and structure data for cold outreach.",
    add_completion=False,
    no_args_is_help=True,
)

search_app = typer.Typer(
    name="search",
    help="Manage and execute saved search configurations.",
    no_args_is_help=True,
)
app.add_typer(search_app, name="search")

console = Console()

_container: Optional[ServiceContainer] = None

def get_container() -> ServiceContainer:
    global _container
    if _container is None:
        _container = ServiceContainer()

    from unittest.mock import Mock
    if isinstance(settings, Mock):
        _container.settings = settings
        from app.repositories import CompanyRepository, ApplicationRepository, MemoryRepository
        _container.company_repo = CompanyRepository(settings.output_dir / "companies.json")
        _container.application_repo = ApplicationRepository(settings.output_dir / "applications.json")
        _container.memory_repo = MemoryRepository(settings.output_dir / "agent_memory.json")
        _container._discovery_service = None
        _container._scraping_service = None
        _container._research_service = None
        _container._resume_service = None
        _container._outreach_service = None
        _container._tracker_service = None
        _container._recommendation_service = None
        _container._dashboard_service = None
        _container._health_service = None

    return _container


@app.callback()
def _bootstrap() -> None:
    """Initialise logging before every command."""
    setup_logging()


def resolve_resume_path(resume_arg: Optional[str]) -> Optional[Path]:
    """Resolve a resume option (label or path string) to a Path, falling back to settings.resume_path."""
    if not resume_arg:
        return settings.resume_path

    p = Path(resume_arg)
    if p.exists() and p.is_file():
        return p

    return resolve_resume_version(resume_arg)


def _run_discovery(
    sources: str,
    seed_file: Optional[Path],
    limit: int,
    profile: Optional[str],
    remote: Optional[bool],
    country: Optional[str],
    keyword: Optional[str],
    exclude: Optional[str],
    days: Optional[int],
    new_only: bool = False,
) -> dict[str, Any]:
    container = get_container()
    loaded_prof = None
    if profile:
        loaded_prof = container.profile_repo.load_profile(profile)

    seed_companies = []
    if seed_file and seed_file.exists():
        seed_companies = resolve_seed_companies(seed_file)

    res = container.discovery_service.discover(
        sources=sources,
        limit=limit,
        profile=loaded_prof,
        remote=remote,
        country=country,
        keyword=keyword,
        exclude=exclude,
        days=days,
        seed_companies=seed_companies,
    )
    return {
        "sources_queried": len(res["source_list"]),
        "new_companies_found": res["all_new_count"],
        "companies_before_filters": res["before_filter_count"],
        "total_companies_written": res["final_count"],
        "total_jobs": res["total_jobs"],
        "new_companies_written": len(res["new_companies_list"]),
        "unchanged_companies_not_shown": res["unchanged_companies_count"],
        "new_jobs": res["new_jobs"],
    }


# ---------------------------------------------------------------------------
# 1. discover
# ---------------------------------------------------------------------------

@app.command()
def discover(
    sources: Annotated[
        str,
        typer.Option(
            "--sources",
            help="Comma-separated list of ATS platforms / feeds to query. Default: 'greenhouse,lever,remoteok,wwr'.",
        ),
    ] = "greenhouse,lever,remoteok,wwr",
    seed_file: Annotated[
        Optional[Path],
        typer.Option(
            "--seed-file",
            help="Optional file of manually-noted company names to resolve on ATS platforms. Default: None.",
            exists=False,
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum number of companies to collect and output. Default: 100."),
    ] = 100,
    profile: Annotated[
        Optional[str],
        typer.Option(
            "--profile",
            help="Apply criteria from a specific profile (defined in profiles/<name>.yaml). Default: None.",
        ),
    ] = None,
    remote: Annotated[
        Optional[bool],
        typer.Option(
            "--remote/--no-remote",
            help="Filter remote jobs only (True), non-remote jobs only (False), or all (None). Default: None.",
            show_default=False,
        ),
    ] = None,
    country: Annotated[
        Optional[str],
        typer.Option(
            "--country",
            help="Filter jobs by location substring. Default: None.",
        ),
    ] = None,
    keyword: Annotated[
        Optional[str],
        typer.Option(
            "--keyword",
            help="Filter jobs by title substring. Default: None.",
        ),
    ] = None,
    exclude: Annotated[
        Optional[str],
        typer.Option(
            "--exclude",
            help="Filter out jobs matching this title substring. Default: None.",
        ),
    ] = None,
    days: Annotated[
        Optional[int],
        typer.Option(
            "--days",
            help="Filter jobs posted within this many days. Default: None.",
        ),
    ] = None,
    new_only: Annotated[
        bool,
        typer.Option(
            "--new-only",
            help="Report only new companies found in this run.",
        ),
    ] = False,
) -> None:
    """Collect hiring companies from public ATS APIs and job boards."""
    container = get_container()

    # --- Load Search Profile if provided ---
    loaded_prof = None
    if profile:
        try:
            loaded_prof = container.profile_repo.load_profile(profile)
            console.print()
            console.print(f"[bold green]✓ Loaded search profile: [cyan]{profile}[/cyan][/bold green]")
            console.print(f"  [dim]Keywords:[/dim]  {loaded_prof.keywords}")
            console.print(f"  [dim]Remote:[/dim]    {loaded_prof.remote}")
            console.print(f"  [dim]Countries:[/dim] {loaded_prof.countries}")
            console.print(f"  [dim]Exclude:[/dim]   {loaded_prof.exclude}")
            console.print()
        except Exception as exc:
            console.print(
                f"[red]Error: Failed to load search profile '{profile}': {exc}[/red]\n"
                "What to do next: Verify that profiles/{profile}.yaml exists and is valid YAML, or list profiles."
            )
            raise typer.Exit(code=1) from exc

    # --- Seed file name resolution ---
    seed_companies = []
    if seed_file:
        if seed_file.exists():
            console.print(f"  [dim]Resolving names in seed file:[/dim] {seed_file}…")
            seed_companies = resolve_seed_companies(seed_file)
            console.print(f"  [green]✓[/green]  Resolved {len(seed_companies)} company/companies from seed file")
        else:
            console.print(f"  [red]✗[/red]  Seed file not found: {seed_file}")

    # --- Event Callback for real-time printing ---
    def event_callback(event_type: str, data: dict[str, Any]) -> None:
        if event_type == "query_start":
            console.print(f"  Querying [bold]{data['source']}[/bold]…")
        elif event_type == "no_slugs":
            console.print(
                f"  [yellow]⚠[/yellow]  No slugs for [bold]{data['source']}[/bold] — "
                f"add them to [dim]output/seed_slugs_{data['source']}.txt[/dim] and re-run."
            )
        elif event_type == "slugs_loaded":
            console.print(f"    ({data['count']} slug(s) loaded)")
        elif event_type == "query_success":
            console.print(f"  [green]✓[/green]  {data['source']}: {data['count']} company/companies found")
        elif event_type == "query_error":
            console.print(f"  [red]✗[/red]  {data['source']}: error during discovery — {data['error']}")
        elif event_type == "existing_loaded":
            console.print(f"  [dim]Loaded {data['count']} existing company/companies from {data['filepath']}[/dim]")
        elif event_type == "existing_load_failed":
            console.print(f"  [yellow]⚠[/yellow]  Could not load existing data ({data['error']}) — starting fresh.")

    # --- Run discovery service ---
    try:
        res = container.discovery_service.discover(
            sources=sources,
            limit=limit,
            profile=loaded_prof,
            remote=remote,
            country=country,
            keyword=keyword,
            exclude=exclude,
            days=days,
            seed_companies=seed_companies,
            event_callback=event_callback,
        )
    except Exception as exc:
        console.print(f"[red]Failed to execute discovery: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    # --- Summary table ---
    console.print()
    source_list = res["source_list"]
    new_companies_written = res["new_companies_list"]
    unchanged_count = res["unchanged_companies_count"]
    total_new_jobs = res["new_jobs"]
    total_jobs = res["total_jobs"]
    before_filter_count = res["before_filter_count"]
    final_count = res["final_count"]

    if new_only:
        table = Table(title="discover — results (new only)", show_header=True)
        table.add_column("Metric", style="bold cyan", no_wrap=True)
        table.add_column("Value", justify="right", style="bold white")
        table.add_row("Sources queried", str(len(source_list)))
        table.add_row("New companies written", f"{len(new_companies_written)} new ({unchanged_count} total unchanged, not shown)")
        table.add_row("New job listings", str(total_new_jobs))
        console.print(table)
    else:
        table = Table(title="discover — results", show_header=True)
        table.add_column("Metric", style="bold cyan", no_wrap=True)
        table.add_column("Value", justify="right", style="bold white")
        table.add_row("Sources queried", str(len(source_list)))
        table.add_row("New companies found", str(res["all_new_count"]))
        table.add_row("Companies before filters", str(before_filter_count))
        table.add_row("Total companies written", str(final_count))
        table.add_row("Total job listings", str(total_jobs))
        console.print(table)

    console.print(f"\n  [dim]Output:[/dim] {container.company_repo.filepath}\n")


# ---------------------------------------------------------------------------
# 2. scrape
# ---------------------------------------------------------------------------

@app.command()
def scrape(
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    company: Annotated[
        Optional[str],
        typer.Option(
            "--company",
            help="Filters run to a single company name (case-insensitive substring) for targeted debugging. Default: None.",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force/--no-force",
            help="Force scraper to re-process companies even if they already have contact data or were scraped in the last 7 days. Default: False.",
        ),
    ] = False,
) -> None:
    """Fetch career-page data and extract contact hints for each discovered company."""
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

    # --- Load checks ---
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' first to collect companies and populate the database."
        )
        raise typer.Exit(code=1)

    container = get_container()
    scraping_service = container.scraping_service

    # Custom repository if path overridden
    if input != container.company_repo.filepath:
        from app.repositories.company import CompanyRepository
        from app.services.scraping import ScrapingService
        scraping_service = ScrapingService(CompanyRepository(input), container.settings)

    # --- Process progress ---
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Scraping", total=0)

        def progress_callback(name: str, idx: int, total: int):
            progress.update(task, total=total)
            progress.update(task, description=f"[bold cyan]{name[:40]}", completed=idx)

        res = scraping_service.scrape(
            company_filter=company,
            force=force,
            progress_callback=progress_callback,
        )

    if res["processed"] == 0 and res["skipped"] == 0:
        console.print(f"[yellow]No company matching '{company}' found in {input}.[/yellow]")
        raise typer.Exit(code=0)

    if company and res["processed"] > 0:
        console.print(f"  Filtered to {res['processed']} company/companies matching '{company}'.")

    # --- Summary ---
    console.print()
    table = Table(title="scrape — results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="bold cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="bold white")
    table.add_row("Companies processed", str(res["processed"]))
    table.add_row("Companies skipped (fresh)", str(res["skipped"]))
    table.add_row("Companies with new emails", str(res["new_emails"]))
    table.add_row("Companies with scrape failures", str(res["failures"]))
    console.print(table)
    console.print(f"\n  [dim]Updated:[/dim] {input}\n")


# ---------------------------------------------------------------------------
# 3. enrich
# ---------------------------------------------------------------------------

@app.command()
def enrich(
    input: Annotated[
        Path,
        typer.Option("--input", help="Path to the JSON database/source file. Default: output/companies.json."),
    ] = settings.output_dir / "companies.json",
    provider: Annotated[
        str,
        typer.Option("--provider", help="AI LLM provider to utilize. Default: 'openrouter'."),
    ] = "openrouter",
    model: Annotated[
        Optional[str],
        typer.Option("--model", help="Override the default LLM model specified in Settings. Default: None."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--no-dry-run", help="Preview prompt templates and logs without making OpenRouter calls. Default: False."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force/--no-force",
            help="Force LLM enrichment even for companies that already have AI summaries. Default: False.",
        ),
    ] = False,
) -> None:
    """Generate AI summaries and talking points for each company via an LLM."""
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

    provider_lower = provider.lower().strip()
    if provider_lower != "openrouter":
        console.print(
            f"[red]Error: Supported provider is only 'openrouter', got '{provider_lower}'.[/red]\n"
            "What to do next: Please specify '--provider openrouter' or omit the option."
        )
        raise typer.Exit(code=1)

    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' before attempting enrichment."
        )
        raise typer.Exit(code=1)

    container = get_container()
    scraping_service = container.scraping_service

    # Custom repository if path overridden
    if input != container.company_repo.filepath:
        from app.repositories.company import CompanyRepository
        from app.services.scraping import ScrapingService
        scraping_service = ScrapingService(CompanyRepository(input), container.settings)

    # --- Process progress ---
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Enriching", total=0)

        def progress_callback(name: str, idx: int, total: int):
            progress.update(task, total=total)
            progress.update(task, description=f"[bold cyan]{name[:40]}", completed=idx)

        res = scraping_service.enrich(
            model=model,
            dry_run=dry_run,
            force=force,
            progress_callback=progress_callback,
        )

    if not res["targets"]:
        console.print()
        console.print("[bold green]All companies already enriched.[/bold green]")
        console.print(f"  Skipped {res['skipped_count']} company/companies (use --force to re-enrich).")
        console.print()
        raise typer.Exit(code=0)

    if dry_run:
        console.print()
        console.print("[bold yellow]⚠ Dry Run Complete[/bold yellow]")
        console.print(f"  Prompts generated/logged for [bold]{len(res['targets'])}[/bold] companies.")
        console.print("  [dim]No API requests were made and the output file was not updated.[/dim]")
        console.print()
    else:
        # Print summary
        console.print()
        table = Table(title="enrich — results", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="bold cyan", no_wrap=True)
        table.add_column("Count", justify="right", style="bold white")
        table.add_row("Companies enriched", str(res["n_enriched"]))
        table.add_row("Companies skipped (already enriched)", str(res["skipped_count"]))
        table.add_row("Companies with enrichment failures", str(res["n_failures"]))
        console.print(table)
        console.print(f"\n  [dim]Updated:[/dim] {input}\n")


# ---------------------------------------------------------------------------
# 4. export
# ---------------------------------------------------------------------------

@app.command()
def export(
    format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Export format: 'csv' or 'json'. Default: 'json'.",
            case_sensitive=False,
        ),
    ] = "json",
    output: Annotated[
        Optional[Path],
        typer.Option("--output", help="Destination file path. Default: auto-named in output/."),
    ] = None,
    granularity: Annotated[
        str,
        typer.Option(
            "--granularity",
            help="Export unit (CSV only): 'company' (one row per company) or 'job' (one row per job). Default: 'company'.",
            case_sensitive=False,
        ),
    ] = "company",
) -> None:
    """Export structured data to CSV or JSON for outreach tooling."""
    format_lower = format.lower().strip()
    granularity_lower = granularity.lower().strip()

    if format_lower not in ("csv", "json"):
        console.print(
            f"[red]Error: --format must be 'csv' or 'json', got '{format_lower}'.[/red]\n"
            "What to do next: Specify '--format csv' or '--format json'."
        )
        raise typer.Exit(code=1)
    if granularity_lower not in ("company", "job"):
        console.print(
            f"[red]Error: --granularity must be 'company' or 'job', got '{granularity_lower}'.[/red]\n"
            "What to do next: Specify '--granularity company' or '--granularity job'."
        )
        raise typer.Exit(code=1)

    container = get_container()
    companies_file = container.company_repo.filepath

    if not companies_file.exists():
        console.print()
        console.print("[bold red]Error: No data to export.[/bold red]")
        console.print(
            f"  [dim]{companies_file}[/dim] does not exist.\n"
            "  What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' first to gather data before exporting."
        )
        console.print()
        raise typer.Exit(code=1)

    companies = container.company_repo.load_all()

    # Determine output path
    if output:
        output_path = output
    else:
        output_path = settings.output_dir / f"hiring-radar-export.{format_lower}"

    # Warn/Ignore granularity for JSON format
    if format_lower == "json" and granularity_lower != "company":
        console.print(
            "[yellow]⚠  Warning: --granularity is ignored for JSON format "
            "(JSON export is always full-fidelity).[/yellow]"
        )

    # Call exporter
    if format_lower == "json":
        try:
            export_json(companies, output_path)
            entry_count = len(companies)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Failed to export JSON to {output_path}:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    else:
        try:
            export_csv(companies, output_path, granularity=granularity_lower)  # type: ignore[arg-type]
            if granularity_lower == "company":
                entry_count = len(companies)
            else:
                entry_count = sum(len(c.jobs) if c.jobs else 1 for c in companies)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Failed to export CSV to {output_path}:[/red] {exc}")
            raise typer.Exit(code=1) from exc

    # Print Rich confirmation
    console.print()
    console.print("[bold green]✓ Export successful![/bold green]")
    console.print(f"  [dim]Destination:[/dim]   [white]{output_path}[/white]")
    console.print(f"  [dim]Companies:[/dim]     {len(companies)}")
    if format_lower == "csv":
        console.print(f"  [dim]CSV Rows:[/dim]      {entry_count}")
    else:
        console.print(f"  [dim]JSON Entries:[/dim]  {entry_count}")
    console.print()


# ---------------------------------------------------------------------------
# 5. status
# ---------------------------------------------------------------------------

@app.command()
def status() -> None:
    """Show a rich summary of locally collected data (read-only)."""
    container = get_container()
    companies_file = container.company_repo.filepath

    # --- Load ---
    if not companies_file.exists():
        console.print()
        console.print("[bold red]No data found.[/bold red]")
        console.print(
            f"  [dim]{companies_file}[/dim] does not exist yet.\n"
            "  Run [bold]hiring-radar discover[/bold] first to collect companies."
        )
        console.print()
        raise typer.Exit(code=0)

    companies = container.company_repo.load_all()

    # --- Compute metrics ---
    total = len(companies)
    total_jobs = sum(len(c.jobs) for c in companies)
    with_jobs = sum(1 for c in companies if c.jobs)
    with_career_page = sum(1 for c in companies if c.career_page_url)
    with_email = sum(
        1 for c in companies if c.generic_emails or c.recruiter_email
    )
    with_ai = sum(1 for c in companies if c.ai_summary)

    # ATS platform breakdown (None → "none")
    platform_counts: dict[str, int] = {}
    for c in companies:
        key = c.ats_platform or "none"
        platform_counts[key] = platform_counts.get(key, 0) + 1

    # --- Main summary table ---
    table = Table(
        title="hiring-radar · local data status",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Metric", style="bold cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="bold white")

    table.add_row("Total companies", str(total))
    table.add_row("Total job postings", str(total_jobs))
    table.add_row("Companies with ≥1 job", str(with_jobs))
    table.add_row("Companies with career page URL", str(with_career_page))
    table.add_row("Companies with email found", str(with_email))
    table.add_row("Companies with AI summary", str(with_ai))
    table.add_section()  # visual separator before platform breakdown
    for platform, count in sorted(platform_counts.items()):
        table.add_row(f"  platform: {platform}", str(count))

    console.print()
    console.print(table)

    # --- Top 5 most recently discovered ---
    if companies:
        recent = sorted(companies, key=lambda c: c.discovered_at, reverse=True)[:5]
        console.print("\n  [bold]5 most recently discovered:[/bold]")
        for i, c in enumerate(recent, start=1):
            ts = c.discovered_at.strftime("%Y-%m-%d %H:%M")
            platform_label = f"[dim]{c.ats_platform or 'feed'}[/dim]"
            job_count = f"{len(c.jobs)} job(s)"
            console.print(
                f"  {i}. [bold white]{c.name}[/bold white]  "
                f"{platform_label}  [dim]{job_count}[/dim]  [dim italic]{ts}[/dim italic]"
            )

    console.print(f"\n  [dim]Source:[/dim] {companies_file}")
    console.print()


# ---------------------------------------------------------------------------
# 6. examples
# ---------------------------------------------------------------------------

@app.command()
def examples() -> None:
    """Show common CLI command invocations and examples."""
    examples_text = (
        "[bold cyan]hiring-radar discover --profile frontend[/bold cyan]\n"
        "[dim]Discover hiring companies using a search profile named 'frontend'[/dim]\n\n"
        "[bold cyan]hiring-radar discover --sources greenhouse,lever --limit 50[/bold cyan]\n"
        "[dim]Limit discovery to Greenhouse & Lever sources, scraping up to 50 companies[/dim]\n\n"
        "[bold cyan]hiring-radar scrape --company linear[/bold cyan]\n"
        "[dim]Fetch career page details and contacts for 'linear' company only[/dim]\n\n"
        "[bold cyan]hiring-radar enrich --dry-run[/bold cyan]\n"
        "[dim]Dry-run AI enrichment to preview OpenRouter prompt formatting[/dim]\n\n"
        "[bold cyan]hiring-radar export --format csv --granularity job[/bold cyan]\n"
        "[dim]Export active jobs data to a CSV document split by role details[/dim]\n\n"
        "[bold cyan]hiring-radar recommend --top 3[/bold cyan]\n"
        "[dim]Display the top 3 recommended companies based on your search settings[/dim]\n\n"
        "[bold cyan]hiring-radar dashboard --open[/bold cyan]\n"
        "[dim]Compile hiring pipeline metrics and view them locally in your browser[/dim]\n"
    )
    console.print()
    console.print(
        Panel(
            examples_text,
            title="[bold magenta]Common Command Examples[/bold magenta]",
            expand=False,
            border_style="cyan"
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# 7. search (sub-commands)
# ---------------------------------------------------------------------------

@search_app.command(name="save")
def search_save(
    name: str = typer.Argument(..., help="Unique name descriptor identifier to assign to this preset."),
    sources: Annotated[
        str,
        typer.Option(
            "--sources",
            help="Comma-separated list of ATS platforms / feeds to query. Default: 'greenhouse,lever,remoteok,wwr'.",
        ),
    ] = "greenhouse,lever,remoteok,wwr",
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum number of companies to collect. Default: 100."),
    ] = 100,
    profile: Annotated[
        Optional[str],
        typer.Option(
            "--profile",
            help="Name of search profile to use for filtering (e.g. 'frontend'). Default: None.",
        ),
    ] = None,
    remote: Annotated[
        Optional[bool],
        typer.Option(
            "--remote/--no-remote",
            help="Filter remote jobs only (True), non-remote jobs only (False), or all (None). Default: None.",
            show_default=False,
        ),
    ] = None,
    country: Annotated[
        Optional[str],
        typer.Option(
            "--country",
            help="Filter jobs by location substring. Default: None.",
        ),
    ] = None,
    keyword: Annotated[
        Optional[str],
        typer.Option(
            "--keyword",
            help="Filter jobs by title substring. Default: None.",
        ),
    ] = None,
    exclude: Annotated[
        Optional[str],
        typer.Option(
            "--exclude",
            help="Filter out jobs matching this title substring. Default: None.",
        ),
    ] = None,
    days: Annotated[
        Optional[int],
        typer.Option(
            "--days",
            help="Filter jobs posted within this many days. Default: None.",
        ),
    ] = None,
) -> None:
    """Save a named combination of search query parameters."""
    container = get_container()
    try:
        container.discovery_service.save_saved_search(
            name=name,
            sources=sources,
            limit=limit,
            profile=profile,
            remote=remote,
            country=country,
            keyword=keyword,
            exclude=exclude,
            days=days,
        )
        console.print(f"[bold green]✓ Saved search '{name}' successfully![/bold green]")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@search_app.command(name="run")
def search_run(
    name: str,
    new_only: Annotated[
        bool,
        typer.Option(
            "--new-only",
            help="Report only new companies found in this run.",
        ),
    ] = False,
) -> None:
    """Run a saved search configuration by name."""
    container = get_container()
    searches = container.discovery_service.load_saved_searches()
    if name not in searches:
        console.print(
            f"[red]Error: Saved search '{name}' not found.[/red]\n"
            f"What to do next: Use 'hiring-radar search list' to view available saved searches."
        )
        raise typer.Exit(code=1)

    s = searches[name]
    console.print(f"[bold green]Running saved search: {name}[/bold green]")

    # Resolve SearchProfile if present
    loaded_prof = None
    if s.profile:
        loaded_prof = container.profile_repo.load_profile(s.profile)

    # --- Call discover ---
    def event_callback(event_type: str, data: dict[str, Any]) -> None:
        if event_type == "query_start":
            console.print(f"  Querying [bold]{data['source']}[/bold]…")
        elif event_type == "no_slugs":
            console.print(
                f"  [yellow]⚠[/yellow]  No slugs for [bold]{data['source']}[/bold] — "
                f"add them to [dim]output/seed_slugs_{data['source']}.txt[/dim] and re-run."
            )
        elif event_type == "slugs_loaded":
            console.print(f"    ({data['count']} slug(s) loaded)")
        elif event_type == "query_success":
            console.print(f"  [green]✓[/green]  {data['source']}: {data['count']} company/companies found")
        elif event_type == "query_error":
            console.print(f"  [red]✗[/red]  {data['source']}: error during discovery — {data['error']}")
        elif event_type == "existing_loaded":
            console.print(f"  [dim]Loaded {data['count']} existing company/companies from {data['filepath']}[/dim]")
        elif event_type == "existing_load_failed":
            console.print(f"  [yellow]⚠[/yellow]  Could not load existing data ({data['error']}) — starting fresh.")

    res = container.discovery_service.discover(
        sources=",".join(s.sources),
        limit=s.limit,
        profile=loaded_prof,
        remote=s.remote,
        country=s.country,
        keyword=s.keyword,
        exclude=s.exclude,
        days=s.days,
        new_only=new_only,
        event_callback=event_callback,
    )

    # --- Summary ---
    console.print()
    source_list = res["source_list"]
    new_companies_written = res["new_companies_list"]
    unchanged_count = res["unchanged_companies_count"]
    total_new_jobs = res["new_jobs"]
    total_jobs = res["total_jobs"]
    before_filter_count = res["before_filter_count"]
    final_count = res["final_count"]

    if new_only:
        table = Table(title="discover — results (new only)", show_header=True)
        table.add_column("Metric", style="bold cyan", no_wrap=True)
        table.add_column("Value", justify="right", style="bold white")
        table.add_row("Sources queried", str(len(source_list)))
        table.add_row("New companies written", f"{len(new_companies_written)} new ({unchanged_count} total unchanged, not shown)")
        table.add_row("New job listings", str(total_new_jobs))
        console.print(table)
    else:
        table = Table(title="discover — results", show_header=True)
        table.add_column("Metric", style="bold cyan", no_wrap=True)
        table.add_column("Value", justify="right", style="bold white")
        table.add_row("Sources queried", str(len(source_list)))
        table.add_row("New companies found", str(res["all_new_count"]))
        table.add_row("Companies before filters", str(before_filter_count))
        table.add_row("Total companies written", str(final_count))
        table.add_row("Total job listings", str(total_jobs))
        console.print(table)

    console.print(f"\n  [dim]Output:[/dim] {container.company_repo.filepath}\n")


@search_app.command(name="list")
def search_list() -> None:
    """List all currently saved search configurations."""
    container = get_container()
    searches = container.discovery_service.load_saved_searches()
    if not searches:
        console.print()
        console.print("[yellow]No saved searches found.[/yellow]")
        console.print("  Run [bold]hiring-radar search save <name>[/bold] to create one.")
        console.print()
        raise typer.Exit(code=0)

    table = Table(title="hiring-radar · saved searches", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Sources", style="bold white")
    table.add_column("Profile", style="bold white")
    table.add_column("Filters", style="bold white")
    table.add_column("Limit", justify="right", style="bold white")

    for name, s in sorted(searches.items()):
        filters_list = []
        if s.remote is not None:
            filters_list.append(f"remote={s.remote}")
        if s.country:
            filters_list.append(f"country={s.country}")
        if s.keyword:
            filters_list.append(f"keyword={s.keyword}")
        if s.exclude:
            filters_list.append(f"exclude={s.exclude}")
        if s.days:
            filters_list.append(f"days={s.days}")
        filters_str = ", ".join(filters_list) or "None"

        table.add_row(
            name,
            ", ".join(s.sources),
            s.profile or "None",
            filters_str,
            str(s.limit),
        )

    console.print()
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# 8. preview
# ---------------------------------------------------------------------------

@app.command()
def preview(
    company_name: str = typer.Argument(..., help="Name of the company to preview the email for (case-insensitive substring match)."),
    template: Annotated[
        str,
        typer.Option(
            "--template",
            help="Email template name to use (e.g. 'startup', 'founder'). Default: 'startup'.",
        ),
    ] = "startup",
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            help="LLM model override for OpenRouter calls. Default: None.",
        ),
    ] = None,
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
) -> None:
    """Generate and display a cold email preview for a single company."""
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' before attempting preview."
        )
        raise typer.Exit(code=1)

    container = get_container()
    outreach_service = container.outreach_service

    # Custom repository if path overridden
    if input != container.company_repo.filepath:
        from app.repositories.company import CompanyRepository
        from app.services.outreach import OutreachService
        outreach_service = OutreachService(CompanyRepository(input), container.settings, container.yaml_config)

    console.print(f"Generating email for [bold cyan]{company_name}[/bold cyan] using template '{template}'…")
    try:
        res = outreach_service.generate_outreach_draft(
            company_name=company_name,
            template=template,
            model=model,
            dry_run=False,
        )
    except Exception as exc:
        console.print(f"[red]Error: Failed to generate email: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not res["body"]:
        console.print("[red]Error: Generated email body was empty. Check OpenRouter API key and settings.[/red]")
        raise typer.Exit(code=1)

    _render_preview_panel(res["company"].name, res["recipient"], res["subject"], res["body"], res["template_used"])


def _render_preview_panel(company_name: str, recipient: str, subject: str, body: str, template_used: str) -> None:
    content = (
        f"[bold]To:[/bold] {recipient}\n"
        f"[bold]Subject:[/bold] {subject}\n\n"
        f"{body}"
    )
    panel = Panel(
        content,
        title=f"[bold magenta]Outreach Preview: {company_name}[/bold magenta]",
        subtitle=f"[dim]Template: {template_used}[/dim]",
        expand=False,
        border_style="cyan"
    )
    console.print()
    console.print(panel)
    console.print()


# ---------------------------------------------------------------------------
# 9. research
# ---------------------------------------------------------------------------

@app.command(name="research")
def research_cli(
    company_name: str = typer.Argument(..., help="Name of the company to research (case-insensitive substring match)."),
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            help="LLM model override for OpenRouter calls. Default: None.",
        ),
    ] = None,
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="If True, shows prompt preview and exits without calling OpenRouter.",
        ),
    ] = False,
) -> None:
    """Perform deeper corporate intelligence on a company (website & organization GitHub profiles)."""
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' first."
        )
        raise typer.Exit(code=1)

    container = get_container()
    research_service = container.research_service

    # Custom repository if path overridden
    if input != container.company_repo.filepath:
        from app.repositories.company import CompanyRepository
        from app.services.research import ResearchService
        research_service = ResearchService(CompanyRepository(input), container.settings)

    console.print(f"Performing deeper corporate research on [bold cyan]{company_name}[/bold cyan]…")
    try:
        co = research_service.research(
            company_name=company_name,
            model=model,
            dry_run=dry_run,
        )
    except Exception as exc:
        console.print(f"[red]Error: Research failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title=f"Deeper AI Research: {co.name}", show_header=True, header_style="bold magenta")
    table.add_column("Fact/Metric", style="bold cyan", no_wrap=True)
    table.add_column("Value Details", style="bold white")

    table.add_row("Website URL", co.website or "—")
    table.add_row("Domain Name", co.domain or "—")
    table.add_row("Github Organization", co.github_url or "—")
    table.add_row("ATS Platform", co.ats_platform or "—")
    table.add_row("AI Summary", co.ai_summary or "—")

    # Fetch notes for deep details
    tech_stack = "—"
    growth_signals = "—"
    for note in reversed(co.notes):
        if note.startswith("tech_stack: "):
            tech_stack = note[len("tech_stack: "):]
        elif note.startswith("growth_signals: "):
            growth_signals = note[len("growth_signals: "):]

    table.add_row("Inferred Tech Stack", tech_stack)
    table.add_row("Growth/Hiring Signals", growth_signals)

    console.print()
    console.print(table)
    console.print()

    if not dry_run:
        console.print(f"Database successfully updated: [dim]{input}[/dim]\n")


# ---------------------------------------------------------------------------
# 10. score-company
# ---------------------------------------------------------------------------

@app.command(name="score-company")
def score_company_cli(
    company_name: str = typer.Argument(..., help="Name of the company (case-insensitive substring match)."),
    resume: Annotated[
        Optional[str],
        typer.Option(
            "--resume",
            help="Resume version label or path to parse to include keyword alignment heuristics.",
        ),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            help="LLM model override for OpenRouter calls. Default: None.",
        ),
    ] = None,
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="If True, shows prompt preview and exits without calling OpenRouter.",
        ),
    ] = False,
) -> None:
    """Evaluate a company's desirability and attractiveness across five axes."""
    container = get_container()

    # Load target resume version if passed
    if resume:
        try:
            resume_p = container.resume_service.resolve_version_path(resume)
            if resume_p:
                container.resume_service.parse_resume(resume_p)
        except Exception as exc:
            console.print(f"[red]Error loading resume version '{resume}': {exc}[/red]")
            raise typer.Exit(code=1) from exc

    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' first."
        )
        raise typer.Exit(code=1)

    # Resolve company matching
    companies = container.company_repo.load_all()
    matches = [c for c in companies if company_name.lower() in c.name.lower()]
    if not matches:
        suggestions = [
            c.name for c in companies
            if company_name.lower() in c.name.lower() or c.name.lower() in company_name.lower()
        ]
        console.print(f"[red]Error: Company '{company_name}' not found.[/red]")
        if suggestions:
            console.print(f"Did you mean one of these? {', '.join(suggestions)}")
        raise typer.Exit(code=1)
    if len(matches) > 1:
        console.print(f"[red]Error: Multiple companies match '{company_name}':[/red]")
        for m in matches:
            console.print(f"  - {m.name}")
        console.print("Please specify a more precise name.")
        raise typer.Exit(code=1)

    co = matches[0]

    console.print(f"Evaluating attractiveness for [bold cyan]{co.name}[/bold cyan]...")
    try:
        from app.enrich.company_score import score_company_attractiveness
        co = score_company_attractiveness(co, model=model, dry_run=dry_run)
    except Exception as exc:
        console.print(f"[red]Error: Attractiveness evaluation failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title=f"Company Attractiveness Report: {co.name}", show_header=True, header_style="bold magenta")
    table.add_column("Axis", style="bold cyan", no_wrap=True)
    table.add_column("Rating (1-10)", justify="right", style="bold white")

    scores = co.company_scores or {}
    table.add_row("Growth Trajectory", str(scores.get("growth", "—")))
    table.add_row("Engineering Culture", str(scores.get("engineering_culture", "—")))
    table.add_row("Remote Friendliness", str(scores.get("remote_friendliness", "—")))
    table.add_row("Open Source Presence", str(scores.get("open_source_presence", "—")))
    table.add_row("Hiring Urgency", str(scores.get("hiring_urgency", "—")))
    table.add_section()
    table.add_row("Overall Desirability Score", f"{co.company_score_overall or '—':.2f}" if co.company_score_overall is not None else "—")

    console.print()
    console.print(table)

    rationale = "—"
    for note in reversed(co.notes):
        if note.startswith("score_rationale: "):
            rationale = note[len("score_rationale: "):]
            break
    console.print(f"[bold]Rationale:[/bold] {rationale}\n")

    if not dry_run:
        # Save back updated company
        for idx, item in enumerate(companies):
            if item.dedupe_key() == co.dedupe_key():
                companies[idx] = co
                break
        container.company_repo.save_all(companies)
        console.print(f"Database successfully updated: [dim]{input}[/dim]\n")


# ---------------------------------------------------------------------------
# 11. tailor
# ---------------------------------------------------------------------------

@app.command(name="tailor")
def tailor_cli(
    company_name: str = typer.Argument(..., help="Name of the company to tailor the resume for (case-insensitive substring match)."),
    resume: Annotated[
        Optional[str],
        typer.Option(
            "--resume",
            help="Resume version label or path to override default resume.",
        ),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            help="LLM model override for OpenRouter calls. Default: None.",
        ),
    ] = None,
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="If True, shows prompt preview and exits without calling OpenRouter.",
        ),
    ] = False,
) -> None:
    """Generate advisory, non-destructive suggestions to tailor your resume for a specific company."""
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' first."
        )
        raise typer.Exit(code=1)

    container = get_container()
    resume_service = container.resume_service

    # Custom repository if path overridden
    if input != container.company_repo.filepath:
        from app.repositories.company import CompanyRepository
        from app.services.resume import ResumeService
        resume_service = ResumeService(CompanyRepository(input), container.profile_repo, container.settings)

    console.print(f"Analyzing resume fit and generating tailoring guidelines for [bold cyan]{company_name}[/bold cyan]...")
    try:
        res = resume_service.suggest_tailoring(
            company_name=company_name,
            resume_label=resume,
            model=model,
            dry_run=dry_run,
        )
    except Exception as exc:
        console.print(f"[red]Error: Suggestions generation failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    sug = res["suggestions"]
    missing_str = ", ".join(sug.get("missing_keywords") or []) or "None"
    projects_list = "\n".join(f"- {p}" for p in (sug.get("projects_to_emphasize") or [])) or "None"

    group = Group(
        Panel(Text(missing_str, style="bold red"), title="[bold cyan]Missing Keywords[/bold cyan]", border_style="red"),
        Panel(Text(projects_list, style="white"), title="[bold cyan]Projects/Experience to Foreground[/bold cyan]", border_style="green"),
        Panel(Text(sug.get("summary_suggestion") or "—", style="italic white"), title="[bold cyan]Tailored Summary/Objective[/bold cyan]", border_style="magenta"),
        Panel(Text(sug.get("reorder_suggestion") or "—", style="white"), title="[bold cyan]Skills Reordering Advice[/bold cyan]", border_style="blue"),
    )

    console.print()
    console.print(Panel(group, title=f"[bold magenta]Resume Tailoring Guide: {res['company'].name}[/bold magenta]", expand=False))
    console.print()

    if not dry_run:
        console.print(f"Database successfully updated: [dim]{input}[/dim]\n")


# ---------------------------------------------------------------------------
# 12. apply
# ---------------------------------------------------------------------------

@app.command(name="apply")
def apply_cli(
    company_name: str = typer.Argument(..., help="Name of the company to apply to (case-insensitive substring match)."),
    status: Annotated[
        ApplicationStatus,
        typer.Option(
            "--status",
            help="The new status to set for the application.",
        ),
    ] = "applied",
    resume: Annotated[
        Optional[str],
        typer.Option(
            "--resume",
            help="Resume version label to record (e.g. 'v1', 'tailored-react').",
        ),
    ] = None,
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON companies database. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    apps_path: Annotated[
        Path,
        typer.Option(
            "--apps-path",
            help="Path to the JSON applications database. Default: output/applications.json.",
        ),
    ] = settings.output_dir / "applications.json",
) -> None:
    """Record or update a job application status for a specific company."""
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' first."
        )
        raise typer.Exit(code=1)

    try:
        all_companies: list[Company] = [
            Company.model_validate(c)
            for c in orjson.loads(input.read_bytes())
        ]
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error: Failed to read database from '{input}': {exc}[/red]")
        raise typer.Exit(code=1) from exc

    matches = [c for c in all_companies if company_name.lower() in c.name.lower()]

    if not matches:
        suggestions = [
            c.name for c in all_companies
            if company_name.lower() in c.name.lower() or c.name.lower() in company_name.lower()
        ]
        console.print(f"[red]Error: Company '{company_name}' not found.[/red]")
        if suggestions:
            console.print(f"Did you mean one of these? {', '.join(suggestions)}")
        raise typer.Exit(code=1)

    if len(matches) > 1:
        console.print(f"[red]Error: Multiple companies match '{company_name}':[/red]")
        for m in matches:
            console.print(f"  - {m.name}")
        console.print("Please specify a more precise name.")
        raise typer.Exit(code=1)

    co = matches[0]
    key = co.dedupe_key()

    if resume:
        try:
            resolve_resume_version(resume)
        except ValueError as exc:
            console.print(f"[red]Error: {exc}[/red]")
            raise typer.Exit(code=1) from exc

    apps = load_applications(apps_path)
    old_app = apps.get(key)
    old_status = old_app.status if old_app else "none"

    app_record = set_status(apps, key, status)
    if resume:
        app_record.resume_version = resume

    try:
        save_applications(apps, apps_path)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error: Failed to save applications to '{apps_path}': {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]✓ Successfully updated application for [bold cyan]{co.name}[/bold cyan][/green]\n"
        f"  [bold]Company key:[/bold] {key}\n"
        f"  [bold]Status transition:[/bold] {old_status} -> {status}\n"
    )
    if resume:
        console.print(f"  [bold]Resume version set to:[/bold] '{resume}'\n")
    console.print(f"  [dim]Applications file updated:[/dim] {apps_path}\n")


# ---------------------------------------------------------------------------
# 13. note
# ---------------------------------------------------------------------------

@app.command(name="note")
def note_cli(
    company_name: str = typer.Argument(..., help="Name of the company (case-insensitive substring match)."),
    add: Annotated[
        Optional[str],
        typer.Option(
            "--add",
            help="Text of the note to append.",
        ),
    ] = None,
    list_notes: Annotated[
        Optional[bool],
        typer.Option(
            "--list/--no-list",
            help="Whether to list all notes for this company.",
        ),
    ] = None,
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON companies database. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    apps_path: Annotated[
        Path,
        typer.Option(
            "--apps-path",
            help="Path to the JSON applications database. Default: output/applications.json.",
        ),
    ] = settings.output_dir / "applications.json",
) -> None:
    """Add or list free-text notes on a company application."""
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' first."
        )
        raise typer.Exit(code=1)

    try:
        all_companies: list[Company] = [
            Company.model_validate(c)
            for c in orjson.loads(input.read_bytes())
        ]
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error: Failed to read database from '{input}': {exc}[/red]")
        raise typer.Exit(code=1) from exc

    matches = [c for c in all_companies if company_name.lower() in c.name.lower()]

    if not matches:
        suggestions = [
            c.name for c in all_companies
            if company_name.lower() in c.name.lower() or c.name.lower() in company_name.lower()
        ]
        console.print(f"[red]Error: Company '{company_name}' not found.[/red]")
        if suggestions:
            console.print(f"Did you mean one of these? {', '.join(suggestions)}")
        raise typer.Exit(code=1)

    if len(matches) > 1:
        console.print(f"[red]Error: Multiple companies match '{company_name}':[/red]")
        for m in matches:
            console.print(f"  - {m.name}")
        console.print("Please specify a more precise name.")
        raise typer.Exit(code=1)

    co = matches[0]
    key = co.dedupe_key()

    apps = load_applications(apps_path)

    if key not in apps:
        app_record = Application(
            company_key=key,
            status="discovered",
            status_history=[{"status": "discovered", "date": date.today().isoformat()}],
        )
        apps[key] = app_record
    else:
        app_record = apps[key]

    should_add = add is not None
    should_list = list_notes if list_notes is not None else (not should_add)

    if should_add:
        note_entry = f"{date.today().isoformat()}: {add}"
        app_record.notes.append(note_entry)
        try:
            save_applications(apps, apps_path)
            console.print(f"[green]✓ Note added successfully to {co.name}[/green]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error: Failed to save applications to '{apps_path}': {exc}[/red]")
            raise typer.Exit(code=1) from exc

    if should_list:
        console.print()
        console.print(f"[bold magenta]Notes for {co.name}:[/bold magenta]")
        if not app_record.notes:
            console.print("  [dim]No notes yet.[/dim]")
        else:
            for note in app_record.notes:
                console.print(f"  • {note}")
        console.print()


# ---------------------------------------------------------------------------
# 14. followups
# ---------------------------------------------------------------------------

@app.command(name="followups")
def followups(
    days: Annotated[
        int,
        typer.Option(
            "--days",
            help="Number of days since last contact to trigger follow-up warning.",
        ),
    ] = 7,
    send: Annotated[
        bool,
        typer.Option(
            "--send/--no-send",
            help="Post a formatted 'Follow-ups due' digest to Telegram if configured.",
        ),
    ] = False,
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON companies database. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    apps_path: Annotated[
        Path,
        typer.Option(
            "--apps-path",
            help="Path to the JSON applications database. Default: output/applications.json.",
        ),
    ] = settings.output_dir / "applications.json",
) -> None:
    """Surface applications that need a follow-up based on last contact date."""
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' first."
        )
        raise typer.Exit(code=1)

    try:
        all_companies: list[Company] = [
            Company.model_validate(c)
            for c in orjson.loads(input.read_bytes())
        ]
        co_map = {c.dedupe_key(): c.name for c in all_companies}
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error: Failed to read database from '{input}': {exc}[/red]")
        raise typer.Exit(code=1) from exc

    apps = load_applications(apps_path)
    if not apps:
        console.print("[yellow]No applications tracked yet. Use 'jobs apply <company>' to track applications.[/yellow]\n")
        return

    today = date.today()
    candidates = []
    for key, app in apps.items():
        if app.status not in ("applied", "interviewing"):
            continue
        if not app.last_contact_date:
            continue

        days_since = (today - app.last_contact_date).days
        if days_since >= days:
            candidates.append({
                "key": key,
                "name": co_map.get(key, key),
                "status": app.status,
                "days_since": days_since,
                "applied_date": app.applied_date,
            })

    candidates.sort(key=lambda x: x["days_since"], reverse=True)

    if not candidates:
        console.print(f"\n[green]✓ All caught up! No applications are overdue for follow-up (threshold: {days} days).[/green]\n")
    else:
        table = Table(title="Applications Needing Follow-up", show_header=True, header_style="bold red")
        table.add_column("Company Name", style="bold cyan")
        table.add_column("Status", style="bold white")
        table.add_column("Days Since Contact", justify="right", style="bold yellow")
        table.add_column("Applied Date", style="dim white")

        for cand in candidates:
            applied_str = cand["applied_date"].isoformat() if cand["applied_date"] else "—"
            table.add_row(
                cand["name"],
                cand["status"],
                str(cand["days_since"]),
                applied_str,
            )

        console.print()
        console.print(table)
        console.print()

    if send and candidates:
        digest_lines = ["*Follow-ups Due Digest*"]
        for cand in candidates:
            applied_str = cand["applied_date"].isoformat() if cand["applied_date"] else "—"
            digest_lines.append(
                f"• *{cand['name']}*: Overdue by {cand['days_since']} days "
                f"(Status: {cand['status']}, Applied: {applied_str})"
            )
        text_content = "\n".join(digest_lines)

        try:
            from app.notify import send_telegram_message
            if settings.telegram_bot_token and yaml_config.telegram.chat_id:
                send_telegram_message(text_content)
                console.print("[green]✓ Sent follow-up digest to Telegram.[/green]\n")
            else:
                console.print("[yellow]Telegram notification not configured. Skipping notification.[/yellow]\n")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error sending Telegram notification: {exc}[/red]\n")


# ---------------------------------------------------------------------------
# 15. recommend
# ---------------------------------------------------------------------------

@app.command(name="recommend")
def recommend_cli(
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    top: Annotated[
        int,
        typer.Option(
            "--top",
            help="Number of top recommended companies to display.",
        ),
    ] = 5,
    resume: Annotated[
        Optional[str],
        typer.Option(
            "--resume",
            help="Resume version label or path to override default resume.",
        ),
    ] = None,
) -> None:
    """Recommend the best companies to apply to, based on desirability and resume fit."""
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' first."
        )
        raise typer.Exit(code=1)

    container = get_container()
    recommendation_service = container.recommendation_service

    # Custom repository if path overridden
    if input != container.company_repo.filepath:
        from app.repositories.company import CompanyRepository
        from app.services.recommendation import RecommendationService
        recommendation_service = RecommendationService(CompanyRepository(input), container.profile_repo, container.settings)

    # Call service
    recs = recommendation_service.get_recommendations(top=top, resume_label=resume)

    resume_text = None
    resume_path = None
    try:
        resume_path = resolve_resume_path(resume)
        if resume_path and resume_path.exists():
            resume_text = load_resume_text(resume_path)
    except Exception:
        pass

    has_resume = resume_text is not None

    if has_resume:
        console.print(f"Loaded resume from [bold cyan]{resume_path}[/bold cyan] to evaluate keyword-fit.")

    table = Table(title="Top Company Recommendations", show_header=True, header_style="bold magenta")
    table.add_column("Rank", justify="right", style="bold yellow")
    table.add_column("Company", style="bold cyan")
    table.add_column("Score", justify="right", style="bold white")
    if has_resume:
        table.add_column("Resume Fit (Overlap)", justify="right", style="bold green")
    table.add_column("Top Job Opening", style="bold white")
    table.add_column("Why / Rationale", style="italic dim white")

    for i, item in enumerate(recs, 1):
        co = item["company"]
        score_val = f"{item['overall']:.2f}" if item["is_scored"] else "unscored"

        # Get top job title
        job_title = "—"
        if co.jobs:
            jobs_sorted = sorted(
                co.jobs,
                key=lambda j: datetime.combine(j.posted_date, datetime.min.time()) if j.posted_date else datetime.min,
                reverse=True
            )
            if jobs_sorted[0].job_title:
                job_title = jobs_sorted[0].job_title

        # Get rationale
        rationale = "—"
        for note in reversed(co.notes):
            if note.startswith("score_rationale: "):
                rationale = note[len("score_rationale: "):]
                break

        row = [str(i), co.name, score_val]
        if has_resume:
            row.append(str(item["fit_score"]))
        row.extend([job_title, rationale])

        table.add_row(*row)

    console.print()
    if not has_resume:
        console.print("[dim]Note: No resume configured. Ranking on overall company score alone.[/dim]\n")
    console.print(table)
    console.print()

    # Hint unscored
    companies = container.company_repo.load_all()
    unscored_count = len([x for x in companies if x.company_score_overall is None])
    if unscored_count > 0:
        console.print(
            f"[yellow]Hint: {unscored_count} companies unscored — run `jobs score-company` or a batch scorer to improve ranking quality.[/yellow]\n"
        )


# ---------------------------------------------------------------------------
# 16. send
# ---------------------------------------------------------------------------

@app.command(name="send")
def outreach_send(
    score: Annotated[
        Optional[float],
        typer.Option(
            "--score",
            help="Filter companies with a numeric score greater than or equal to this. Default: None.",
        ),
    ] = None,
    company: Annotated[
        Optional[str],
        typer.Option(
            "--company",
            help="Filter run to a single company name (case-insensitive substring match). Default: None.",
        ),
    ] = None,
    template: Annotated[
        str,
        typer.Option(
            "--template",
            help="Email template name to use (e.g. 'startup', 'founder'). Default: 'startup'.",
        ),
    ] = "startup",
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm/--no-confirm",
            help="Interactive per-email confirmation gate. If False, runs in dry-preview mode. Default: False.",
        ),
    ] = False,
    resend: Annotated[
        bool,
        typer.Option(
            "--resend/--no-resend",
            help="Resend emails even to companies already marked as sent. Default: False.",
        ),
    ] = False,
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            help="LLM model override for OpenRouter calls. Default: None.",
        ),
    ] = None,
) -> None:
    """Run batch cold email outreach with mandatory interactive confirmation."""
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' before attempting outreach."
        )
        raise typer.Exit(code=1)

    container = get_container()
    outreach_service = container.outreach_service

    # Custom repository if path overridden
    if input != container.company_repo.filepath:
        from app.repositories.company import CompanyRepository
        from app.services.outreach import OutreachService
        outreach_service = OutreachService(CompanyRepository(input), container.settings, container.yaml_config)

    all_companies = outreach_service.company_repo.load_all()

    # Filter targets
    targets = []
    skipped_no_email = 0
    skipped_already_sent = 0

    for c in all_companies:
        if company and company.lower() not in c.name.lower():
            continue

        recipient = c.recruiter_email or (c.generic_emails[0] if c.generic_emails else None)
        if not recipient:
            skipped_no_email += 1
            logger.info("outreach/send/{company}: skipped (no recipient email found)", company=c.name)
            continue

        has_sent_note = any(n.startswith("email_sent:") for n in c.notes)
        if has_sent_note and not resend:
            skipped_already_sent += 1
            logger.info("outreach/send/{company}: skipped (email already marked as sent)", company=c.name)
            continue

        targets.append(c)

    if not targets:
        console.print()
        console.print("[yellow]No target companies found matching current outreach filters.[/yellow]")
        console.print(f"  Skipped (no email):       {skipped_no_email}")
        console.print(f"  Skipped (already sent):   {skipped_already_sent}")
        console.print()
        raise typer.Exit(code=0)

    # Process batch
    previewed_count = 0
    sent_count = 0
    declined_count = 0

    from app.utils import RateLimiter
    rate_limiter = RateLimiter()

    for idx, co in enumerate(targets, start=1):
        recipient = co.recruiter_email or co.generic_emails[0]
        console.print(f"Processing target [bold cyan]{co.name}[/bold cyan] ({idx}/{len(targets)})…")

        try:
            res = outreach_service.generate_outreach_draft(
                company_name=co.name,
                template=template,
                model=model,
                dry_run=False,
            )
        except Exception as exc:
            console.print(f"[red]✗ Failed to generate email for {co.name}: {exc}[/red]")
            continue

        if not res["body"]:
            console.print(f"[red]✗ Failed to generate email body for {co.name}.[/red]")
            continue

        _render_preview_panel(co.name, recipient, res["subject"], res["body"], res["template_used"])

        if not confirm:
            previewed_count += 1
            console.print(
                f"[yellow]  (dry preview {idx}/{len(targets)} — pass --confirm to actually enable sending gate)[/yellow]\n"
            )
        else:
            send_approval = typer.confirm(f"Send this email to {recipient}?")
            if not send_approval:
                declined_count += 1
                console.print("[yellow]  Email declined by user.[/yellow]\n")
            else:
                rate_limiter.wait("smtp")
                console.print(f"  Sending email to {recipient}…")
                try:
                    success = outreach_service.send_outreach_email(recipient, res["subject"], res["body"])
                    if success:
                        sent_count += 1
                        outreach_service.mark_email_sent(co.name, template)
                        console.print("[green]  ✓ Sent successfully![/green]\n")
                    else:
                        console.print("[red]  ✗ SMTP delivery failed.[/red]\n")
                except Exception as exc:
                    console.print(f"[red]  ✗ SMTP connection failed: {exc}[/red]\n")

    # Print Summary
    console.print()
    table = Table(title="outreach send — batch results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="bold cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="bold white")
    table.add_row("Total targets matched", str(len(targets)))
    table.add_row("Emails previewed only (dry)", str(previewed_count))
    table.add_row("Emails successfully sent", str(sent_count))
    table.add_row("Emails declined by user", str(declined_count))
    table.add_row("Skipped (no email address)", str(skipped_no_email))
    table.add_row("Skipped (already sent previously)", str(skipped_already_sent))

    console.print(table)
    console.print(f"\n  [dim]Database updated:[/dim] {input}\n")


# ---------------------------------------------------------------------------
# 17. test-smtp
# ---------------------------------------------------------------------------

@app.command(name="test-smtp")
def test_smtp(
    email: str = typer.Argument(..., help="Recipient email address to send the test message to."),
) -> None:
    """Send a test email to verify SMTP and App Password settings."""
    container = get_container()
    console.print(f"Sending SMTP connection test email to [bold cyan]{email}[/bold cyan]…")
    try:
        success = container.outreach_service.send_test_email(email)
        if success:
            console.print("[bold green]✓ Test email sent successfully![/bold green] Please check your inbox.")
        else:
            console.print("[bold red]✗ Failed to send test email.[/bold red] Review the error details in the logs.")
            raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error configuring SMTP connection:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# 18. test-telegram
# ---------------------------------------------------------------------------

@app.command(name="test-telegram")
def test_telegram() -> None:
    """Send a test message to verify Telegram Bot API settings."""
    container = get_container()
    console.print("Sending Telegram test notification…")
    try:
        success = container.health_service.test_telegram()
        if success:
            console.print("[bold green]✓ Test notification sent successfully![/bold green] Please check your Telegram chat.")
        else:
            console.print("[bold red]✗ Failed to send test notification.[/bold red] Ensure that TELEGRAM_BOT_TOKEN is set in .env, telegram.enabled is true and telegram.chat_id is set in config.yaml, and verify your bot credentials.")
            raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error sending Telegram notification:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# 19. watch
# ---------------------------------------------------------------------------

@app.command(name="watch")
def watch_loop(
    interval: Annotated[
        int,
        typer.Option(
            "--interval",
            help="Polling interval in minutes. Default: 30.",
        ),
    ] = 30,
    sources: Annotated[
        str,
        typer.Option(
            "--sources",
            help="Comma-separated list of ATS platforms / feeds to query. Default: 'greenhouse,lever,remoteok,wwr'.",
        ),
    ] = "greenhouse,lever,remoteok,wwr",
    profile: Annotated[
        Optional[str],
        typer.Option(
            "--profile",
            help="Name of search profile to use for filtering (e.g. 'frontend'). Default: None.",
        ),
    ] = None,
    once: Annotated[
        bool,
        typer.Option(
            "--once/--loop",
            help="Run a single discovery pass and exit immediately. Default: False.",
        ),
    ] = False,
    alerts: Annotated[
        bool,
        typer.Option(
            "--alerts/--no-alerts",
            help="Enable filtering of Telegram alerts using rules defined in alerts.yaml. Default: True.",
        ),
    ] = True,
) -> None:
    """Watch sources continuously, notifying Telegram of new companies or job postings."""
    from app.notify import send_telegram_message, format_new_company_alert
    from app.filters import apply_filters
    from loguru import logger
    import time

    container = get_container()
    companies_file = container.company_repo.filepath

    def get_current_state() -> dict[str, Company]:
        companies = container.company_repo.load_all()
        return {c.dedupe_key(): c for c in companies}

    console.print()
    if once:
        console.print("[bold cyan]Watch mode: running a single check...[/bold cyan]")
    else:
        console.print(f"[bold cyan]Watch mode: starting polling loop (interval: {interval}m, sources: {sources})...[/bold cyan]")
        console.print("[dim]Press Ctrl+C to terminate watch loop cleanly.[/dim]\n")

    alert_rules = []
    if alerts:
        alert_rules = container.profile_repo.load_alert_rules()
        if alert_rules:
            console.print(f"[bold green]✓ Loaded {len(alert_rules)} alert rule(s) from alerts.yaml[/bold green]")
        else:
            console.print("  [dim]No alert rules found in alerts.yaml — alerting on all new discoveries.[/dim]")

    def should_alert_company(co_to_check: Company) -> bool:
        if not alerts or not alert_rules:
            return True
        for rule in alert_rules:
            filtered = apply_filters([co_to_check], profile=rule)
            if filtered:
                logger.debug("watch alert match: company '{company}' matched alert rule '{rule}'", company=co_to_check.name, rule=rule.name)
                return True
        return False

    # Resolve SearchProfile if present
    loaded_prof = None
    if profile:
        loaded_prof = container.profile_repo.load_profile(profile)

    try:
        while True:
            cycle_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"[{cycle_time}] Checking for new hiring activities…")

            previous_state = get_current_state()

            # Discovery event callback
            def event_callback(event_type: str, data: dict[str, Any]) -> None:
                pass  # Keep watch output uncluttered by sub-discover prints if desired, or duplicate

            try:
                container.discovery_service.discover(
                    sources=sources,
                    limit=100,
                    profile=loaded_prof,
                    event_callback=event_callback,
                )
            except Exception as exc:  # noqa: BLE001
                console.print(f"[red]⚠ Discovery failed this cycle: {exc}[/red]")

            new_state = get_current_state()

            # Diff and Send Alerts
            new_companies_alerted = 0
            new_jobs_alerted = 0

            for key, new_co in new_state.items():
                if key not in previous_state:
                    if should_alert_company(new_co):
                        alert_msg = format_new_company_alert(new_co)
                        console.print(f"  [green]+[/green] New company: [bold]{new_co.name}[/bold]. Sending Telegram alert…")
                        send_telegram_message(alert_msg)
                        new_companies_alerted += 1
                        time.sleep(1)
                else:
                    prev_co = previous_state[key]
                    prev_urls = {j.job_url for j in prev_co.jobs}
                    new_jobs = [j for j in new_co.jobs if j.job_url not in prev_urls]
                    if new_jobs:
                        new_jobs_co = new_co.model_copy(update={"jobs": new_jobs})
                        if should_alert_company(new_jobs_co):
                            if alerts and alert_rules:
                                matched_jobs = []
                                matched_urls = set()
                                for rule in alert_rules:
                                    filtered_res = apply_filters([new_jobs_co], profile=rule)
                                    if filtered_res:
                                        for j in filtered_res[0].jobs:
                                            if j.job_url not in matched_urls:
                                                matched_jobs.append(j)
                                                matched_urls.add(j.job_url)
                            else:
                                matched_jobs = new_jobs

                            if matched_jobs:
                                first_new_job = matched_jobs[0]
                                count_new = len(matched_jobs)
                                msg = (
                                    f"🔔 *New Job Openings at {new_co.name}*\n\n"
                                    f"💼 Added {count_new} new role(s), including:\n"
                                    f"👉 [{first_new_job.job_title}]({first_new_job.job_url})\n\n"
                                    f"#hiring #{new_co.ats_platform or 'feed'}"
                                )
                                console.print(f"  [cyan]*[/cyan] {new_co.name}: {count_new} new job(s) matching alert rules found. Sending Telegram alert…")
                                send_telegram_message(msg)
                                new_jobs_alerted += 1
                                time.sleep(1)

            logger.info(
                "watch cycle finished: previous={prev_len}, current={current_len}, "
                "new_companies={new_cos}, new_jobs={new_jbs}",
                prev_len=len(previous_state),
                current_len=len(new_state),
                new_cos=new_companies_alerted,
                new_jbs=new_jobs_alerted,
            )
            console.print(f"Cycle finished. Alerts sent: {new_companies_alerted} new companies, {new_jobs_alerted} new jobs.\n")

            if once:
                break

            console.print(f"Sleeping for {interval} minutes (next check around {datetime.now() + timedelta(minutes=interval)})…\n")
            time.sleep(interval * 60)

    except KeyboardInterrupt:
        console.print()
        console.print("[bold yellow]Watch loop interrupted by user. Exiting cleanly…[/bold yellow]")

        table = Table(title="watch — loop termination summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="bold cyan", no_wrap=True)
        table.add_column("Value", justify="right", style="bold white")
        table.add_row("Status", "Terminated")
        table.add_row("Polling Interval (minutes)", str(interval))
        table.add_row("Sources", sources)
        table.add_row("Profile", profile or "None")
        console.print(table)
        console.print()
        raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# 20. digest
# ---------------------------------------------------------------------------

@app.command(name="digest")
def outreach_digest(
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    send: Annotated[
        bool,
        typer.Option(
            "--send/--no-send",
            help="Post the generated digest to Telegram via the bot. Default: False.",
        ),
    ] = False,
) -> None:
    """Generate a daily cold outreach hiring digest and optionally send to Telegram."""
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' to collect data first."
        )
        raise typer.Exit(code=1)

    container = get_container()
    companies = container.company_repo.load_all()

    # Filter to last 24 hours
    window_start = datetime.now() - timedelta(hours=24)
    recent_companies = []
    for c in companies:
        c_time = c.discovered_at.replace(tzinfo=None) if c.discovered_at.tzinfo else c.discovered_at
        if c_time >= window_start:
            recent_companies.append(c)

    total_companies = len(recent_companies)
    total_jobs = sum(len(c.jobs) for c in recent_companies)

    ai_pattern = re.compile(r'\b(ai|ml|nlp|computer vision)\b|artificial intelligence|machine learning|deep learning', re.IGNORECASE)
    backend_pattern = re.compile(r'\b(backend|back-end|python|go|golang|rust|java|node|django|fastapi|c\+\+|c#|\.net|ruby|rails)\b', re.IGNORECASE)
    frontend_pattern = re.compile(r'\b(frontend|front-end|react|next\.js|nextjs|typescript|javascript|vue|angular|ui|ux|css|html)\b', re.IGNORECASE)

    ai_count = backend_count = frontend_count = other_count = 0
    for c in recent_companies:
        for j in c.jobs:
            title = j.job_title
            if ai_pattern.search(title):
                ai_count += 1
            elif frontend_pattern.search(title):
                frontend_count += 1
            elif backend_pattern.search(title):
                backend_count += 1
            else:
                other_count += 1

    top_picks = sorted(recent_companies, key=lambda c: len(c.jobs), reverse=True)[:5]
    top_picks_lines = [f"{idx}. {c.name} — {len(c.jobs)} new jobs" for idx, c in enumerate(top_picks, start=1)]
    top_picks_str = "\n".join(top_picks_lines) if top_picks_lines else "None"

    digest_text = (
        f"☀️ *Daily Hiring Digest*\n\n"
        f"{total_companies} new companies · {total_jobs} new jobs\n\n"
        f"🤖 AI/ML: {ai_count}\n"
        f"🔧 Backend: {backend_count}\n"
        f"🎨 Frontend: {frontend_count}\n"
        f"📋 Other: {other_count}\n\n"
        f"*Top picks:*\n"
        f"{top_picks_str}"
    )

    if send:
        console.print("Posting daily hiring digest to Telegram…")
        from app.notify.telegram import send_telegram_message
        success = send_telegram_message(digest_text)
        if success:
            console.print("[bold green]✓ Daily digest posted successfully to Telegram![/bold green]")
        else:
            console.print("[bold red]✗ Failed to post daily digest to Telegram.[/bold red]")

    panel = Panel(
        digest_text,
        title="[bold magenta]Daily Hiring Digest[/bold magenta]",
        expand=False,
        border_style="cyan"
    )
    console.print()
    console.print(panel)
    console.print()


# ---------------------------------------------------------------------------
# 21. morning-brief
# ---------------------------------------------------------------------------

@app.command(name="morning-brief")
def morning_brief(
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
) -> None:
    """Generate a daily cold outreach hiring digest and send it to Telegram."""
    bot_token = settings.telegram_bot_token
    chat_id = yaml_config.telegram.chat_id
    enabled = yaml_config.telegram.enabled

    if not bot_token or not chat_id or not enabled:
        console.print(
            "Telegram notifications are not fully configured or are disabled. "
            "Skipping morning brief execution."
        )
        raise typer.Exit(code=0)

    outreach_digest(input=input, send=True)


# ---------------------------------------------------------------------------
# 22. report
# ---------------------------------------------------------------------------

@app.command(name="report")
def activity_report(
    days: Annotated[
        int,
        typer.Option(
            "--days",
            help="Number of days in the reporting window.",
        ),
    ] = 1,
    send: Annotated[
        bool,
        typer.Option(
            "--send/--no-send",
            help="Post the generated report to Telegram via the bot. Default: False.",
        ),
    ] = False,
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    apps_path: Annotated[
        Path,
        typer.Option(
            "--apps-path",
            help="Path to the JSON applications database. Default: output/applications.json.",
        ),
    ] = settings.output_dir / "applications.json",
) -> None:
    """Generate an end-of-day summary of user activity over a reporting window."""
    window_start = datetime.now() - timedelta(days=days)
    window_start_date = window_start.date()

    container = get_container()

    # 1. Gather stats from companies.json
    new_companies_count = 0
    new_jobs_count = 0
    emails_sent_count = 0

    if input.exists():
        try:
            # Custom company repo if path overridden
            company_repo = container.company_repo
            if input != company_repo.filepath:
                from app.repositories.company import CompanyRepository
                company_repo = CompanyRepository(input)

            companies = company_repo.load_all()
            for c in companies:
                if c.discovered_at:
                    c_time = c.discovered_at.replace(tzinfo=None) if c.discovered_at.tzinfo else c.discovered_at
                    if c_time >= window_start:
                        new_companies_count += 1
                        new_jobs_count += len(c.jobs)

                for note in c.notes:
                    if note.startswith("email_sent:"):
                        match = re.search(r"email_sent:\s*([\d\-]+)", note)
                        if match:
                            try:
                                note_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
                                if note_date >= window_start_date:
                                    emails_sent_count += 1
                            except Exception:
                                pass
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Warning: Could not fully parse companies database: {exc}[/yellow]")

    # 2. Gather stats from applications.json
    applications_count = 0
    pending_followups_count = None

    if apps_path.exists():
        try:
            # Custom application repo if path overridden
            app_repo = container.application_repo
            if apps_path != app_repo.filepath:
                from app.repositories.application import ApplicationRepository
                app_repo = ApplicationRepository(apps_path)

            apps = app_repo.load_all()
            for app_key, app_dict in apps.items():
                for hist_item in app_dict.status_history:
                    if hist_item.get("status") == "applied":
                        hist_date_str = hist_item.get("date")
                        if hist_date_str:
                            try:
                                hist_date = datetime.strptime(hist_date_str, "%Y-%m-%d").date()
                                if hist_date >= window_start_date:
                                    applications_count += 1
                            except Exception:
                                pass
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Warning: Could not fully parse applications database: {exc}[/yellow]")

        # 3. Follow-ups still pending
        try:
            tracker_service = container.tracker_service
            if apps_path != container.application_repo.filepath:
                from app.repositories.application import ApplicationRepository
                from app.services.tracker import TrackerService
                tracker_service = TrackerService(ApplicationRepository(apps_path), container.company_repo)

            followups_list = tracker_service.get_followups(threshold_days=7)
            pending_followups_count = len(followups_list)
        except Exception:
            pending_followups_count = None

    # 4. Format report text
    report_lines = [
        f"📊 *Activity Report (Last {days} Days)*\n",
        f"· New companies discovered: {new_companies_count}",
        f"· New jobs added: {new_jobs_count}",
        f"· Emails drafted/sent: {emails_sent_count}",
        f"· Applications submitted: {applications_count}",
    ]
    if pending_followups_count is not None:
        report_lines.append(f"· Follow-ups pending: {pending_followups_count}")

    report_text = "\n".join(report_lines)

    if send:
        bot_token = settings.telegram_bot_token
        chat_id = yaml_config.telegram.chat_id
        enabled = yaml_config.telegram.enabled

        if not bot_token or not chat_id or not enabled:
            console.print(
                "Telegram notifications are not fully configured or are disabled. "
                "Skipping report send."
            )
        else:
            console.print("Posting activity report to Telegram…")
            from app.notify.telegram import send_telegram_message
            success = send_telegram_message(report_text)
            if success:
                console.print("[bold green]✓ Activity report posted successfully to Telegram![/bold green]")
            else:
                console.print("[bold red]✗ Failed to post activity report to Telegram.[/bold red]")

    panel = Panel(
        report_text,
        title="[bold magenta]Activity Report[/bold magenta]",
        expand=False,
        border_style="cyan"
    )
    console.print()
    console.print(panel)
    console.print()


# ---------------------------------------------------------------------------
# 23. dashboard
# ---------------------------------------------------------------------------

@app.command(name="dashboard")
def view_dashboard(
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help="Path to save the generated static HTML dashboard. Default: output/dashboard.html.",
        ),
    ] = Path("output/dashboard.html"),
    open_browser: Annotated[
        bool,
        typer.Option(
            "--open/--no-open",
            help="Open the generated HTML dashboard directly in your default browser. Default: False.",
        ),
    ] = False,
) -> None:
    """Generate a self-contained static HTML dashboard for local data review."""
    container = get_container()
    console.print(f"Generating static dashboard from [bold cyan]{input}[/bold cyan]...")
    try:
        container.dashboard_service.generate_dashboard(output_path=output, input_path=input)
        console.print(f"[bold green][OK] Dashboard generated successfully![/bold green] Saved to: [dim]{output}[/dim]")

        if open_browser:
            console.print("Opening dashboard in your default browser...")
            webbrowser.open(output.absolute().as_uri())
    except Exception as exc:
        console.print(f"[bold red]Error generating dashboard:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# 24. mcp-serve
# ---------------------------------------------------------------------------

@app.command(name="mcp-serve")
def mcp_serve(
    transport: Annotated[
        str,
        typer.Option(
            "--transport",
            help="Transport protocol to run. Options: 'stdio', 'http', or 'sse'. Default: 'stdio'.",
        ),
    ] = "stdio",
    port: Annotated[
        int,
        typer.Option(
            "--port",
            help="Port to bind the HTTP/SSE transport server. Default: 8811.",
        ),
    ] = 8811,
    host: Annotated[
        str,
        typer.Option(
            "--host",
            help="Host address to bind the HTTP/SSE transport server. Default: '0.0.0.0'.",
        ),
    ] = "0.0.0.0",
) -> None:
    """Start the Model Context Protocol (MCP) server integration."""
    os.environ["MCP_TRANSPORT"] = transport.lower()
    os.environ["MCP_HTTP_PORT"] = str(port)
    os.environ["MCP_HTTP_HOST"] = host

    console.print(f"[bold green]Starting MCP server...[/bold green]")
    console.print(f"  [dim]Transport:[/dim] {transport}")
    if transport.lower() in ("http", "sse"):
        console.print(f"  [dim]Binding:[/dim]   {host}:{port}")

    from mcp_server.server import main
    main()


# ---------------------------------------------------------------------------
# 25. agent
# ---------------------------------------------------------------------------

@app.command(name="agent")
def agent(
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            help="OpenRouter model identifier override to use for the agent loop.",
        ),
    ] = None,
) -> None:
    """Start an interactive terminal reasoning agent loop (REPL)."""
    from app.agent.planner import run_agent_turn

    console.print(
        "\n[bold purple]🤖 Hiring Radar Autonomous AI Agent REPL[/bold purple]\n"
        "Type your requests to discover, score, research, or recommend jobs.\n"
        "Type [bold red]exit[/bold red] or [bold red]quit[/bold red] to end the session.\n"
    )

    conversation_history: list[dict] = []

    while True:
        try:
            user_msg = Prompt.ask("\n[bold cyan]Agent[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Session ended.[/yellow]")
            break

        if user_msg.strip().lower() in ("exit", "quit"):
            console.print("[yellow]Goodbye![/yellow]")
            break

        if not user_msg.strip():
            continue

        user_input_to_send = user_msg
        while True:
            with console.status("[bold yellow]Thinking...[/bold yellow]"):
                try:
                    res = run_agent_turn(user_input_to_send, conversation_history, model=model)
                    conversation_history = res["updated_history"]
                except Exception as exc:  # noqa: BLE001
                    console.print(f"[bold red]Error in agent loop:[/bold red] {exc}")
                    break

            if "pending_approval" in res:
                pending = res["pending_approval"]
                tool_name = pending["tool"]
                args = pending["arguments"]
                tc_id = pending["tool_call_id"]
                desc = pending["description"]

                if res.get("tool_calls_made"):
                    tools_str = ", ".join(res["tool_calls_made"])
                    console.print(f"[dim]🔧 Tools invoked: {tools_str}[/dim]")

                console.print(f"\n[bold yellow]⚠️ Pending Approval:[/bold yellow] Agent wants to {desc}")
                approved = typer.confirm("Approve this action?")

                from app.agent.tools import execute_approved_tool
                container = get_container()
                mem = container.memory_repo.load()

                if approved:
                    mem["past_decisions"].append({
                        "date": date.today().isoformat(),
                        "action": f"Approved and executed tool '{tool_name}' with arguments {args}",
                    })
                    container.memory_repo.save(mem)
                    with console.status(f"[bold yellow]Executing {tool_name}...[/bold yellow]"):
                        tool_result = execute_approved_tool(tool_name, args)
                else:
                    mem["past_decisions"].append({
                        "date": date.today().isoformat(),
                        "action": f"Declined execution of tool '{tool_name}' with arguments {args}",
                    })
                    container.memory_repo.save(mem)
                    tool_result = {"error": "User declined to approve this action."}

                # Append tool result message
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": tool_name,
                    "content": json.dumps(tool_result),
                }
                conversation_history.append(tool_msg)

                user_input_to_send = ""
                continue
            else:
                if res.get("tool_calls_made"):
                    tools_str = ", ".join(res["tool_calls_made"])
                    console.print(f"[dim]🔧 Tools invoked: {tools_str}[/dim]")

                console.print(Markdown(res["reply"]))
                break


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()