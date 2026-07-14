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
from app.exporters import export_csv, export_json
from app.enrich import enrich as _enrich_ai
from app.scraper.company import scrape_company_page
from app.scraper.contacts import extract_contacts
from app.profiles import load_profile
from app.filters import apply_filters
from app.outreach import generate_email, send_test_email
from app.saved_search import SavedSearch, load_saved_searches, save_saved_searches
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
    """Collect hiring companies from public ATS APIs and job boards."""
    _run_discovery(
        sources=sources,
        seed_file=seed_file,
        limit=limit,
        profile=profile,
        remote=remote,
        country=country,
        keyword=keyword,
        exclude=exclude,
        days=days,
    )


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
) -> None:
    # --- Load Search Profile if provided ---
    loaded_prof = None
    if profile:
        try:
            loaded_prof = load_profile(profile)
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

    source_list = [s.strip() for s in sources.split(",") if s.strip()]

    # --- Validate sources ---
    unknown = [s for s in source_list if s not in SOURCE_REGISTRY]
    if unknown:
        console.print(
            f"[red]Error: Unknown source(s): {', '.join(unknown)}[/red]\n"
            "What to do next: Use only valid sources: greenhouse, lever, remoteok, wwr, ashby, workable, bamboohr."
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

    # --- Apply Filters ---
    before_filter_count = len(merged)
    filtered = apply_filters(
        list(merged.values()),
        profile=loaded_prof if loaded_prof else None,
        remote=remote,
        country=country,
        keyword=keyword,
        exclude=exclude,
        days=days,
    )
    final: list[Company] = filtered[:limit]

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
    table.add_row("Companies before filters", str(before_filter_count))
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

    # --- Load ---
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' first to collect companies and populate the database."
        )
        raise typer.Exit(code=1)

    try:
        all_companies: list[Company] = [
            Company.model_validate(c)
            for c in orjson.loads(input.read_bytes())
        ]
    except Exception as exc:  # noqa: BLE001
        console.print(
            f"[red]Error: Failed to read database from '{input}': {exc}[/red]\n"
            "What to do next: Ensure the JSON file is not corrupted or rerun 'hiring-radar discover'."
        )
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

    # 1. Load companies
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' before attempting enrichment."
        )
        raise typer.Exit(code=1)

    try:
        all_companies: list[Company] = [
            Company.model_validate(c)
            for c in orjson.loads(input.read_bytes())
        ]
    except Exception as exc:  # noqa: BLE001
        console.print(
            f"[red]Error: Failed to read database from '{input}': {exc}[/red]\n"
            "What to do next: Ensure the JSON file is not corrupted or rerun 'hiring-radar discover'."
        )
        raise typer.Exit(code=1) from exc

    # 2. Filter companies to enrich
    targets: list[Company] = []
    skipped_count = 0
    for company in all_companies:
        if force or not company.ai_summary:
            targets.append(company)
        else:
            skipped_count += 1

    if not targets:
        console.print()
        console.print("[bold green]All companies already enriched.[/bold green]")
        console.print(f"  Skipped {skipped_count} company/companies (use --force to re-enrich).")
        console.print()
        raise typer.Exit(code=0)

    # 3. Process companies
    n_enriched = 0
    n_failures = 0

    rate_limiter = RateLimiter()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Enriching", total=len(targets))

        for co in targets:
            progress.update(task, description=f"[bold cyan]{co.name[:40]}", advance=1)

            # Apply rate limiting to OpenRouter API (using a pseudo-domain name)
            if not dry_run:
                rate_limiter.wait("https://openrouter.ai")

            try:
                _enrich_ai(co, model=model, dry_run=dry_run)

                # Check for failure note
                if any(n.startswith("enrich_failed") for n in co.notes):
                    n_failures += 1
                else:
                    n_enriched += 1
            except Exception as exc:  # noqa: BLE001
                n_failures += 1
                co.notes.append(f"enrich_failed: unexpected error — {exc}")
                logger.warning("enrich/{name}: unexpected error — {exc}", name=co.name, exc=exc)

    # 4 & 5. Dry run check / write back
    if dry_run:
        console.print()
        console.print("[bold yellow]⚠ Dry Run Complete[/bold yellow]")
        console.print(f"  Prompts generated/logged for [bold]{len(targets)}[/bold] companies.")
        console.print("  [dim]No API requests were made and the output file was not updated.[/dim]")
        console.print()
    else:
        # Re-merge updated targets with skipped ones
        updated_map = {c.dedupe_key(): c for c in targets}
        final = [updated_map.get(c.dedupe_key(), c) for c in all_companies]

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

        # 6. Print summary
        console.print()
        table = Table(title="enrich — results", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="bold cyan", no_wrap=True)
        table.add_column("Count", justify="right", style="bold white")
        table.add_row("Companies enriched", str(n_enriched))
        table.add_row("Companies skipped (already enriched)", str(skipped_count))
        table.add_row("Companies with enrichment failures", str(n_failures))
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

    # 1. Load companies from settings.output_dir / "companies.json"
    companies_file = settings.output_dir / "companies.json"
    if not companies_file.exists():
        console.print()
        console.print("[bold red]Error: No data to export.[/bold red]")
        console.print(
            f"  [dim]{companies_file}[/dim] does not exist.\n"
            "  What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' first to gather data before exporting."
        )
        console.print()
        raise typer.Exit(code=1)

    try:
        raw_list: list[dict] = orjson.loads(companies_file.read_bytes())
    except Exception as exc:  # noqa: BLE001
        console.print(
            f"[red]Error: Failed to read database from '{companies_file}': {exc}[/red]\n"
            "What to do next: Ensure the JSON database file is not corrupted."
        )
        raise typer.Exit(code=1) from exc

    if not isinstance(raw_list, list):
        console.print(
            f"[red]Error: Expected a JSON array in '{companies_file}'.[/red]\n"
            "What to do next: Ensure the file is not corrupted."
        )
        raise typer.Exit(code=1)

    # 2. Validate into list[Company]
    companies: list[Company] = []
    parse_errors = 0
    for raw in raw_list:
        try:
            companies.append(Company.model_validate(raw))
        except Exception:  # noqa: BLE001
            parse_errors += 1

    if parse_errors:
        console.print(
            f"  [yellow]⚠[/yellow]  Skipped {parse_errors} malformed record(s) during validation."
        )

    # 3. Determine output path
    if output:
        output_path = output
    else:
        output_path = settings.output_dir / f"hiring-radar-export.{format_lower}"

    # 4. Warn/Ignore granularity for JSON format
    if format_lower == "json" and granularity_lower != "company":
        console.print(
            "[yellow]⚠  Warning: --granularity is ignored for JSON format "
            "(JSON export is always full-fidelity).[/yellow]"
        )

    # 5. Call exporter
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

    # 6. Print Rich confirmation
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
# 6. examples
# ---------------------------------------------------------------------------

@app.command()
def examples() -> None:
    """Show common CLI command invocations and examples."""
    from rich.panel import Panel

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
        "[dim]Export all processed results to CSV formatted with one row per job[/dim]\n\n"
        "[bold cyan]hiring-radar status[/bold cyan]\n"
        "[dim]View data collection metrics and top 5 most recently discovered companies[/dim]"
    )

    panel = Panel(
        examples_text,
        title="[bold magenta]hiring-radar CLI Examples[/bold magenta]",
        expand=False,
        border_style="cyan"
    )
    console.print()
    console.print(panel)
    console.print()


# ---------------------------------------------------------------------------
# 7. search subcommands
# ---------------------------------------------------------------------------

search_app = typer.Typer(
    help="Manage and run saved search configurations."
)
app.add_typer(search_app, name="search")


@search_app.command(name="save")
def search_save(
    name: str,
    sources: Annotated[
        str,
        typer.Option(
            "--sources",
            help="Comma-separated list of ATS platforms / feeds to query. Default: 'greenhouse,lever,remoteok,wwr'.",
        ),
    ] = "greenhouse,lever,remoteok,wwr",
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum number of companies to collect and output. Default: 100."),
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
    source_list = [s.strip() for s in sources.split(",") if s.strip()]
    unknown = [s for s in source_list if s not in SOURCE_REGISTRY]
    if unknown:
        console.print(
            f"[red]Error: Unknown source(s): {', '.join(unknown)}[/red]\n"
            "What to do next: Use only valid sources: greenhouse, lever, remoteok, wwr, ashby, workable, bamboohr."
        )
        raise typer.Exit(code=1)

    searches = load_saved_searches()
    if name in searches:
        confirm = typer.confirm(f"Saved search '{name}' already exists. Overwrite?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(code=0)

    s = SavedSearch(
        name=name,
        profile=profile,
        sources=source_list,
        remote=remote,
        country=country,
        keyword=keyword,
        exclude=exclude,
        days=days,
        limit=limit,
    )
    searches[name] = s
    save_saved_searches(searches)
    console.print(f"[bold green]✓ Saved search '{name}' successfully![/bold green]")


@search_app.command(name="run")
def search_run(name: str) -> None:
    """Run a saved search configuration by name."""
    searches = load_saved_searches()
    if name not in searches:
        console.print(
            f"[red]Error: Saved search '{name}' not found.[/red]\n"
            f"What to do next: Use 'hiring-radar search list' to view available saved searches."
        )
        raise typer.Exit(code=1)

    s = searches[name]
    console.print(f"[bold green]Running saved search: {name}[/bold green]")

    _run_discovery(
        sources=",".join(s.sources),
        seed_file=None,
        limit=s.limit,
        profile=s.profile,
        remote=s.remote,
        country=s.country,
        keyword=s.keyword,
        exclude=s.exclude,
        days=s.days,
    )


@search_app.command(name="list")
def search_list() -> None:
    """List all currently saved search configurations."""
    searches = load_saved_searches()
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
    from rich.panel import Panel

    # 1. Load companies from input
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' before attempting preview."
        )
        raise typer.Exit(code=1)

    try:
        all_companies: list[Company] = [
            Company.model_validate(c)
            for c in orjson.loads(input.read_bytes())
        ]
    except Exception as exc:  # noqa: BLE001
        console.print(
            f"[red]Error: Failed to read database from '{input}': {exc}[/red]\n"
            "What to do next: Ensure the JSON file is not corrupted."
        )
        raise typer.Exit(code=1) from exc

    # 2. Find matching company
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

    # 3. Generate email (not dry run)
    console.print(f"Generating email for [bold cyan]{co.name}[/bold cyan] using template '{template}'…")
    try:
        res = generate_email(co, template_name=template, model=model, dry_run=False)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error: Failed to generate email: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not res["body"]:
        console.print("[red]Error: Generated email body was empty. Check OpenRouter API key and settings.[/red]")
        raise typer.Exit(code=1)

    # 4. Display output
    recipient = co.recruiter_email or (co.generic_emails[0] if co.generic_emails else "(no email found — see `jobs scrape`)")

    content = (
        f"[bold]To:[/bold] {recipient}\n"
        f"[bold]Subject:[/bold] {res['subject']}\n\n"
        f"{res['body']}"
    )

    panel = Panel(
        content,
        title=f"[bold magenta]Outreach Preview: {co.name}[/bold magenta]",
        subtitle=f"[dim]Template: {res['template_used']}[/dim]",
        expand=False,
        border_style="cyan"
    )
    console.print()
    console.print(panel)
    console.print()


# ---------------------------------------------------------------------------
# 9. test-smtp
# ---------------------------------------------------------------------------

@app.command(name="test-smtp")
def test_smtp(
    email: str = typer.Argument(..., help="Recipient email address to send the test message to."),
) -> None:
    """Send a test email to verify SMTP and App Password settings."""
    console.print(f"Sending SMTP connection test email to [bold cyan]{email}[/bold cyan]…")
    try:
        success = send_test_email(email)
        if success:
            console.print("[bold green]✓ Test email sent successfully![/bold green] Please check your inbox.")
        else:
            console.print("[bold red]✗ Failed to send test email.[/bold red] Review the error details in the logs.")
            raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error configuring SMTP connection:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Allows:  python -m app.cli <command>
    # The `hiring-radar` console script (pyproject.toml) calls app() directly.
    app()