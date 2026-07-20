"""Data management commands: scrape, enrich, export, status, examples."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.panel import Panel
from rich.table import Table

from app.cli.common import console, get_container
from app.config import settings
from app.exporters import export_csv, export_json

# ---------------------------------------------------------------------------
# 2. scrape
# ---------------------------------------------------------------------------


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
    from app.cli.common import track_progress
    with track_progress("Scraping") as progress_callback:
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
    from app.cli.common import track_progress
    with track_progress("Enriching") as progress_callback:
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

    # ATS platform breakdown (None -> "none")
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
            border_style="cyan",
        )
    )
    console.print()
