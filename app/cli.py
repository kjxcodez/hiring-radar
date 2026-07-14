"""hiring-radar CLI entrypoint.

Run as:
    python -m app.cli <command>      # always works, no install needed
    hiring-radar <command>           # after `pip install -e .` (see pyproject.toml)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Optional

import orjson
import typer
from rich.console import Console
from rich.table import Table

from app.config import settings
from app.discover import SOURCE_REGISTRY
from app.discover import remoteok as _remoteok_mod
from app.discover import wwr as _wwr_mod
from app.discover.seed import load_seed_slugs, resolve_seed_companies
from app.models import Company
from app.scraper.company import scrape_company_page
from app.scraper.contacts import extract_contacts
from app.utils import RateLimiter, get_http_client, setup_logging

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="hiring-radar",
    help="Discover hiring companies and structure data for cold outreach.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


@app.callback()
def _bootstrap() -> None:
    """Initialise logging before every command."""
    setup_logging()


# ---------------------------------------------------------------------------
# 1. discover
# ---------------------------------------------------------------------------

@app.command()
def discover(
    sources: Annotated[
        str,
        typer.Option(
            "--sources",
            help="Comma-separated list of sources to query.",
        ),
    ] = "greenhouse,lever,remoteok,wwr",
    seed_file: Annotated[
        Optional[Path],
        typer.Option(
            "--seed-file",
            help="Optional file of known company slugs/domains to start from.",
            exists=False,   # allow non-existent path at parse time; validate in impl
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum number of companies to collect."),
    ] = 100,
) -> None:
    """Collect hiring companies from public ATS APIs and job boards."""
    source_list = [s.strip() for s in sources.split(",") if s.strip()]

    # --- Validate sources ---
    unknown = [s for s in source_list if s not in SOURCE_REGISTRY]
    if unknown:
        console.print(
            f"[red]Unknown source(s): {', '.join(unknown)}[/red]\n"
            f"Available: {', '.join(SOURCE_REGISTRY)}"
        )
        raise typer.Exit(code=1)

    # --- Load seed slugs ---
    seed_map: dict[str, list[str]] = load_seed_slugs(source_list)

    # --- Load seed file and resolve manually-noted company names ---
    seed_companies: list[Company] = []
    if seed_file:
        if seed_file.exists():
            console.print(f"  [dim]Resolving names in seed file:[/dim] {seed_file}…")
            seed_companies = resolve_seed_companies(seed_file)
            console.print(f"  [green]✓[/green]  Resolved {len(seed_companies)} company/companies from seed file")
        else:
            console.print(f"  [red]✗[/red]  Seed file not found: {seed_file}")

    # --- Discover per source ---
    all_new: list[Company] = []
    for src in source_list:
        console.print(f"  Querying [bold]{src}[/bold]…")
        try:
            # --- feed-based sources: single global feed, limit-based signature ---
            # remoteok and wwr both expose discover(limit: int) rather than
            # discover(slugs: list[str]).  Branch explicitly — don't force a
            # unified signature.
            if src == "remoteok":
                discovered = _remoteok_mod.discover(limit=limit)
            elif src == "wwr":
                discovered = _wwr_mod.discover(limit=limit)

            # --- slug-based ATS sources (greenhouse, lever, …) ---
            else:
                slugs = seed_map.get(src, [])
                if not slugs:
                    console.print(
                        f"  [yellow]⚠[/yellow]  No slugs for [bold]{src}[/bold] — "
                        f"add them to [dim]output/seed_slugs_{src}.txt[/dim] and re-run."
                    )
                    continue
                console.print(f"    ({len(slugs)} slug(s) loaded)")
                discovered = SOURCE_REGISTRY[src](slugs)

            all_new.extend(discovered)
            console.print(f"  [green]✓[/green]  {src}: {len(discovered)} company/companies found")
        except Exception as exc:  # noqa: BLE001
            console.print(f"  [red]✗[/red]  {src}: error during discovery — {exc}")

    # --- Merge resolved seed companies ---
    if seed_companies:
        all_new.extend(seed_companies)

    # --- Load existing companies.json (for incremental runs) ---
    companies_file = settings.output_dir / "companies.json"
    existing: list[Company] = []
    if companies_file.exists():
        try:
            raw = orjson.loads(companies_file.read_bytes())
            existing = [Company.model_validate(c) for c in raw]
            console.print(f"  [dim]Loaded {len(existing)} existing company/companies from {companies_file}[/dim]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"  [yellow]⚠[/yellow]  Could not load existing data ({exc}) — starting fresh.")

    # --- Deduplicate and merge ---
    merged: dict[str, Company] = {c.dedupe_key(): c for c in existing}
    for new_co in all_new:
        key = new_co.dedupe_key()
        if key in merged:
            # Merge job lists, preferring new jobs (by URL uniqueness)
            existing_urls = {j.job_url for j in merged[key].jobs}
            merged[key].jobs.extend(j for j in new_co.jobs if j.job_url not in existing_urls)
            merged[key].last_updated = new_co.last_updated
        else:
            merged[key] = new_co

    final: list[Company] = list(merged.values())[:limit]

    # --- Write output ---
    total_jobs = sum(len(c.jobs) for c in final)
    try:
        companies_file.write_bytes(
            orjson.dumps(
                [c.model_dump(mode="json") for c in final],
                option=orjson.OPT_INDENT_2,
            )
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to write {companies_file}: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    # --- Summary ---
    console.print()
    table = Table(title="discover — results", show_header=True)
    table.add_column("Metric", style="bold cyan", no_wrap=True)
    table.add_column("Value", justify="right", style="bold white")
    table.add_row("Sources queried", str(len(source_list)))
    table.add_row("New companies found", str(len(all_new)))
    table.add_row("Total companies written", str(len(final)))
    table.add_row("Total job listings", str(total_jobs))
    console.print(table)
    console.print(f"\n  [dim]Output:[/dim] {companies_file}\n")


# ---------------------------------------------------------------------------
# 2. scrape
# ---------------------------------------------------------------------------

@app.command()
def scrape(
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to companies.json produced by `discover`.",
        ),
    ] = settings.output_dir / "companies.json",
    company: Annotated[
        Optional[str],
        typer.Option(
            "--company",
            help="Single company name (case-insensitive substring) for targeted debugging.",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force/--no-force",
            help="Re-scrape even companies that already have contact data.",
        ),
    ] = False,
) -> None:
    """Fetch career-page data and extract contact hints for each discovered company."""
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

    # --- Load ---
    if not input.exists():
        console.print(f"[red]Input file not found:[/red] {input}")
        raise typer.Exit(code=1)

    try:
        all_companies: list[Company] = [
            Company.model_validate(c)
            for c in orjson.loads(input.read_bytes())
        ]
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to load {input}:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # --- Filter ---
    targets: list[Company] = all_companies
    if company:
        targets = [c for c in all_companies if company.lower() in c.name.lower()]
        if not targets:
            console.print(f"[yellow]No company matching '{company}' found in {input}.[/yellow]")
            raise typer.Exit(code=0)
        console.print(f"  Filtered to {len(targets)} company/companies matching '{company}'.")

    # --- Counters ---
    n_processed = 0
    n_skipped = 0
    n_new_emails = 0
    n_failures = 0
    stale_threshold = timedelta(days=7)

    # --- Shared HTTP resources ---
    rate_limiter = RateLimiter()

    with get_http_client() as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Scraping", total=len(targets))

            for co in targets:
                progress.update(task, description=f"[bold cyan]{co.name[:40]}", advance=1)

                # --- Skip logic (unless --force) ---
                if not force:
                    has_contacts = bool(co.generic_emails or co.recruiter_email)
                    recently_scraped = (
                        (datetime.now() - co.last_updated) < stale_threshold
                    )
                    if has_contacts and recently_scraped:
                        n_skipped += 1
                        logger.debug(
                            "{name}: skipped (has contacts, scraped within 7 days)",
                            name=co.name,
                        )
                        continue

                # --- Scrape + extract ---
                try:
                    emails_before = len(co.generic_emails) + (1 if co.recruiter_email else 0)

                    co, page_text = scrape_company_page(co, client, rate_limiter)

                    if page_text is not None:
                        extract_contacts(co, page_text)

                    emails_after = len(co.generic_emails) + (1 if co.recruiter_email else 0)
                    if emails_after > emails_before:
                        n_new_emails += 1

                    n_processed += 1

                    # Check for failure notes
                    if any(n.startswith("scrape_failed") for n in co.notes):
                        n_failures += 1

                except Exception as exc:  # noqa: BLE001
                    n_failures += 1
                    n_processed += 1
                    co.notes.append(f"scrape_failed: unexpected error — {exc}")
                    logger.warning("{name}: unexpected error — {exc}", name=co.name, exc=exc)

    # --- Write back (full list, preserving untouched companies) ---
    # Build a map of updated companies by dedupe_key, then re-merge.
    updated_map: dict[str, Company] = {c.dedupe_key(): c for c in targets}
    final: list[Company] = [
        updated_map.get(c.dedupe_key(), c) for c in all_companies
    ]

    try:
        input.write_bytes(
            orjson.dumps(
                [c.model_dump(mode="json") for c in final],
                option=orjson.OPT_INDENT_2,
            )
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to write {input}:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # --- Summary ---
    console.print()
    table = Table(title="scrape — results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="bold cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="bold white")
    table.add_row("Companies processed", str(n_processed))
    table.add_row("Companies skipped (fresh)", str(n_skipped))
    table.add_row("Companies with new emails", str(n_new_emails))
    table.add_row("Companies with scrape failures", str(n_failures))
    console.print(table)
    console.print(f"\n  [dim]Updated:[/dim] {input}\n")


# ---------------------------------------------------------------------------
# 3. enrich
# ---------------------------------------------------------------------------

@app.command()
def enrich(
    input: Annotated[
        Path,
        typer.Option("--input", help="Path to companies.json to enrich."),
    ] = settings.output_dir / "companies.json",
    provider: Annotated[
        str,
        typer.Option("--provider", help="LLM provider to use."),
    ] = "openrouter",
    model: Annotated[
        Optional[str],
        typer.Option("--model", help="Override the LLM model (default from settings)."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--no-dry-run", help="Preview without writing output."),
    ] = False,
) -> None:
    """Generate AI summaries and talking points for each company via an LLM."""
    console.print()
    console.print("[bold yellow]⚠  enrich — not implemented yet[/bold yellow]")
    console.print()
    console.print(f"  [dim]Input:[/dim]    {input}")
    console.print(f"  [dim]Provider:[/dim] {provider}")
    console.print(f"  [dim]Model:[/dim]    {model or settings.openrouter_model}")
    console.print(f"  [dim]Dry-run:[/dim]  {dry_run}")
    console.print()
    console.print(
        "  This command will call the LLM for each company without an"
        " ai_summary and write the results back to the input file."
    )
    console.print()
    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# 4. export
# ---------------------------------------------------------------------------

@app.command()
def export(
    format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Output format: 'csv' or 'json'.",
            case_sensitive=False,
        ),
    ] = "json",
    output: Annotated[
        Optional[Path],
        typer.Option("--output", help="Destination file (default: auto-named in output/)."),
    ] = None,
    granularity: Annotated[
        str,
        typer.Option(
            "--granularity",
            help="Export unit: 'company' (one row per company) or 'job' (one row per job).",
            case_sensitive=False,
        ),
    ] = "company",
) -> None:
    """Export structured data to CSV or JSON for outreach tooling."""
    if format not in ("csv", "json"):
        console.print(f"[red]Error:[/red] --format must be 'csv' or 'json', got '{format}'.")
        raise typer.Exit(code=1)
    if granularity not in ("company", "job"):
        console.print(
            f"[red]Error:[/red] --granularity must be 'company' or 'job', got '{granularity}'."
        )
        raise typer.Exit(code=1)

    console.print()
    console.print("[bold yellow]⚠  export — not implemented yet[/bold yellow]")
    console.print()
    console.print(f"  [dim]Format:[/dim]      {format}")
    console.print(f"  [dim]Granularity:[/dim] {granularity}")
    if output:
        console.print(f"  [dim]Output:[/dim]      {output}")
    console.print()
    console.print(
        "  This command will read companies.json and write a flat"
        f" [bold]{format.upper()}[/bold] file, one record per [bold]{granularity}[/bold]."
    )
    console.print()
    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# 5. status  (real implementation)
# ---------------------------------------------------------------------------

@app.command()
def status() -> None:
    """Show a rich summary of locally collected data (read-only)."""
    companies_file = settings.output_dir / "companies.json"

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

    try:
        raw_list: list[dict] = orjson.loads(companies_file.read_bytes())
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to read {companies_file}:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not isinstance(raw_list, list):
        console.print(f"[red]Expected a JSON array in {companies_file}.[/red]")
        raise typer.Exit(code=1)

    # Parse into typed models so all field access is safe and validated.
    companies: list[Company] = []
    parse_errors = 0
    for raw in raw_list:
        try:
            companies.append(Company.model_validate(raw))
        except Exception:  # noqa: BLE001
            parse_errors += 1

    if parse_errors:
        console.print(
            f"  [yellow]⚠[/yellow]  Skipped {parse_errors} malformed record(s) during parsing."
        )

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
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Allows:  python -m app.cli <command>
    # The `hiring-radar` console script (pyproject.toml) calls app() directly.
    app()