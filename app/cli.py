"""hiring-radar CLI entrypoint.

Run as:
    python -m app.cli <command>      # always works, no install needed
    hiring-radar <command>           # after `pip install -e .` (see pyproject.toml)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Optional

import orjson
import typer
from rich.console import Console
from rich.table import Table

from app.config import settings, yaml_config
from app.discover import SOURCE_REGISTRY
from app.discover import remoteok as _remoteok_mod
from app.discover import wwr as _wwr_mod
from app.discover.seed import load_seed_slugs, resolve_seed_companies
from app.models import Company, ApplicationStatus, Application
from app.exporters import export_csv, export_json
from app.enrich import enrich as _enrich_ai
from app.enrich.research import research_company
from app.enrich.company_score import score_company_attractiveness
from app.resume.parser import load_resume_text
from app.resume.versions import resolve_resume_version, list_resume_versions
from app.resume.suggestions import suggest_resume_tailoring
from app.tracker.status import load_applications, save_applications, set_status
from app.scraper.company import scrape_company_page
from app.scraper.contacts import extract_contacts
from app.profiles import load_profile, load_alert_rules
from app.filters import apply_filters
from app.outreach import generate_email, send_test_email, send_email
from app.dashboard import build_dashboard
from app.notify import send_telegram_message, format_new_company_alert
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


def resolve_resume_path(resume_arg: Optional[str]) -> Optional[Path]:
    """Resolve a resume option (label or path string) to a Path, falling back to settings.resume_path."""
    if not resume_arg:
        return settings.resume_path

    # Try as a file path first
    p = Path(resume_arg)
    if p.exists() and p.is_file():
        return p

    # Otherwise, resolve as version label
    return resolve_resume_version(resume_arg)


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
    new_only: Annotated[
        bool,
        typer.Option(
            "--new-only",
            help="Report only new companies found in this run.",
        ),
    ] = False,
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
        new_only=new_only,
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
    new_only: bool = False,
) -> dict[str, Any]:
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
    pre_existing_keys = set(merged.keys())

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

    # --- Track new vs pre-existing in written results ---
    new_companies_written = [c for c in final if c.dedupe_key() not in pre_existing_keys]
    unchanged_count = len(final) - len(new_companies_written)
    total_new_jobs = sum(len(c.jobs) for c in new_companies_written)

    # --- Summary ---
    console.print()
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
        table.add_row("New companies found", str(len(all_new)))
        table.add_row("Companies before filters", str(before_filter_count))
        table.add_row("Total companies written", str(len(final)))
        table.add_row("Total job listings", str(total_jobs))
        console.print(table)

    console.print(f"\n  [dim]Output:[/dim] {companies_file}\n")

    summary_data = {
        "sources_queried": len(source_list),
        "new_companies_found": len(all_new),
        "companies_before_filters": before_filter_count,
        "total_companies_written": len(final),
        "total_jobs": total_jobs,
        "new_companies_written": len(new_companies_written),
        "unchanged_companies_not_shown": unchanged_count,
        "new_jobs": total_new_jobs,
    }
    return summary_data


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
        new_only=new_only,
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
    _render_preview_panel(co.name, recipient, res["subject"], res["body"], res["template_used"])


def _render_preview_panel(company_name: str, recipient: str, subject: str, body: str, template_used: str) -> None:
    from rich.panel import Panel

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
# 15. research
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
    """Perform deeper AI-based corporate research on a single company."""
    # 1. Load companies from input
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
        console.print(
            f"[red]Error: Failed to read database from '{input}': {exc}[/red]"
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

    # 3. Perform research
    console.print(f"Performing deeper AI research for [bold cyan]{co.name}[/bold cyan]...")
    rate_limiter = RateLimiter(settings.request_delay_seconds)
    try:
        with get_http_client() as client:
            co = research_company(co, client, rate_limiter, model=model, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error: Research failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    # 4. Display output
    from rich.table import Table
    table = Table(title=f"Deeper AI Research: {co.name}", show_header=True, header_style="bold magenta")
    table.add_column("Field", style="bold cyan", no_wrap=True)
    table.add_column("Details", style="bold white")

    notes = co.research_notes or {}
    table.add_row("Products", notes.get("products", "—"))
    table.add_row("Likely Customers", notes.get("likely_customers", "—"))
    table.add_row("Engineering Notes", notes.get("engineering_notes", "—"))
    table.add_row("Recent Signals", notes.get("recent_signals", "—"))
    console.print()
    console.print(table)
    console.print()

    # 5. Write back to database if not dry_run
    if not dry_run:
        try:
            input.write_bytes(
                orjson.dumps(
                    [c.model_dump(mode="json") for c in all_companies],
                    option=orjson.OPT_INDENT_2,
                )
            )
            console.print(f"Database successfully updated: [dim]{input}[/dim]\n")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Failed to update database {input}: {exc}[/red]")
            raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# 16. score-company
# ---------------------------------------------------------------------------

@app.command(name="score-company")
def score_company_cli(
    company_name: str = typer.Argument(..., help="Name of the company to evaluate attractiveness for (case-insensitive substring match)."),
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
    """Evaluate a company's desirability and attractiveness across five axes."""
    # Resolve and validate resume if given
    if resume:
        try:
            resume_p = resolve_resume_path(resume)
            if resume_p:
                load_resume_text(resume_p)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error loading resume version '{resume}': {exc}[/red]")
            raise typer.Exit(code=1) from exc

    # 1. Load companies from input
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
        console.print(
            f"[red]Error: Failed to read database from '{input}': {exc}[/red]"
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

    # 3. Perform scoring
    console.print(f"Evaluating attractiveness for [bold cyan]{co.name}[/bold cyan]...")
    try:
        co = score_company_attractiveness(co, model=model, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error: Attractiveness evaluation failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    # 4. Display output
    from rich.table import Table
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

    # Extract rationale from notes
    rationale = "—"
    for note in reversed(co.notes):
        if note.startswith("score_rationale: "):
            rationale = note[len("score_rationale: "):]
            break

    console.print(f"[bold]Rationale:[/bold] {rationale}\n")

    # 5. Write back to database if not dry_run
    if not dry_run:
        try:
            input.write_bytes(
                orjson.dumps(
                    [c.model_dump(mode="json") for c in all_companies],
                    option=orjson.OPT_INDENT_2,
                )
            )
            console.print(f"Database successfully updated: [dim]{input}[/dim]\n")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Failed to update database {input}: {exc}[/red]")
            raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# 18. tailor
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
    from rich.panel import Panel
    from rich.console import Group
    from rich.text import Text
    from datetime import date

    # 1. Load resume
    try:
        resume_p = resolve_resume_path(resume)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error resolving resume version '{resume}': {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not resume_p:
        console.print(
            "[red]Error: Resume path is not set.[/red]\n"
            "Please configure RESUME_PATH in your .env file or pass the --resume option."
        )
        raise typer.Exit(code=1)

    if not resume_p.exists():
        console.print(f"[red]Error: Resume file '{resume_p}' not found.[/red]")
        raise typer.Exit(code=1)

    try:
        resume_text = load_resume_text(resume_p)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error: Failed to load resume text from '{resume_p}': {exc}[/red]")
        raise typer.Exit(code=1)

    # 2. Load companies from input
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

    # 3. Find matching company
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

    # 4. Generate tailoring suggestions
    console.print(f"Analyzing resume fit and generating tailoring guidelines for [bold cyan]{co.name}[/bold cyan]...")
    try:
        res = suggest_resume_tailoring(co, resume_text, model=model, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error: Suggestions generation failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    # 5. Display recommendations
    missing_str = ", ".join(res.get("missing_keywords") or []) or "None"
    projects_list = "\n".join(f"- {p}" for p in (res.get("projects_to_emphasize") or [])) or "None"

    group = Group(
        Panel(Text(missing_str, style="bold red"), title="[bold cyan]Missing Keywords[/bold cyan]", border_style="red"),
        Panel(Text(projects_list, style="white"), title="[bold cyan]Projects/Experience to Foreground[/bold cyan]", border_style="green"),
        Panel(Text(res.get("summary_suggestion") or "—", style="italic white"), title="[bold cyan]Tailored Summary/Objective[/bold cyan]", border_style="magenta"),
        Panel(Text(res.get("reorder_suggestion") or "—", style="white"), title="[bold cyan]Skills Reordering Advice[/bold cyan]", border_style="blue"),
    )

    console.print()
    console.print(Panel(group, title=f"[bold magenta]Resume Tailoring Guide: {co.name}[/bold magenta]", expand=False))
    console.print()

    # 6. Append note and save back to database if not dry run
    if not dry_run:
        note_text = f"tailoring_suggested: {date.today().isoformat()}"
        if note_text not in co.notes:
            co.notes.append(note_text)
        co.last_updated = datetime.now()

        try:
            input.write_bytes(
                orjson.dumps(
                    [c.model_dump(mode="json") for c in all_companies],
                    option=orjson.OPT_INDENT_2,
                )
            )
            console.print(f"Database successfully updated: [dim]{input}[/dim]\n")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Failed to update database {input}: {exc}[/red]")
            raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# 19. apply
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
    # 1. Load companies from input
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
    key = co.dedupe_key()

    # Validate resume version if given
    if resume:
        try:
            resolve_resume_version(resume)
        except ValueError as exc:
            console.print(f"[red]Error: {exc}[/red]")
            raise typer.Exit(code=1) from exc

    # 3. Load applications database
    apps = load_applications(apps_path)

    # 4. Set application status
    old_app = apps.get(key)
    old_status = old_app.status if old_app else "none"

    app_record = set_status(apps, key, status)
    if resume:
        app_record.resume_version = resume

    # 5. Save applications database
    try:
        save_applications(apps, apps_path)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error: Failed to save applications to '{apps_path}': {exc}[/red]")
        raise typer.Exit(code=1) from exc

    # 6. Display success output
    console.print(
        f"[green]✓ Successfully updated application for [bold cyan]{co.name}[/bold cyan][/green]\n"
        f"  [bold]Company key:[/bold] {key}\n"
        f"  [bold]Status transition:[/bold] {old_status} -> {status}\n"
    )
    if resume:
        console.print(f"  [bold]Resume version set to:[/bold] '{resume}'\n")
    console.print(f"  [dim]Applications file updated:[/dim] {apps_path}\n")


# ---------------------------------------------------------------------------
# 20. note
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
    # 1. Load companies from input
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
    key = co.dedupe_key()

    # 3. Load applications database
    apps = load_applications(apps_path)

    # 4. Load or create Application entry
    if key not in apps:
        app_record = Application(
            company_key=key,
            status="discovered",
            status_history=[{"status": "discovered", "date": date.today().isoformat()}],
        )
        apps[key] = app_record
    else:
        app_record = apps[key]

    # 5. Resolve action flags
    should_add = add is not None
    should_list = list_notes if list_notes is not None else (not should_add)

    # 6. Add note if requested
    if should_add:
        note_entry = f"{date.today().isoformat()}: {add}"
        app_record.notes.append(note_entry)
        try:
            save_applications(apps, apps_path)
            console.print(f"[green]✓ Note added successfully to {co.name}[/green]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error: Failed to save applications to '{apps_path}': {exc}[/red]")
            raise typer.Exit(code=1) from exc

    # 7. List notes if requested
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
# 21. followups
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
    from rich.table import Table
    from datetime import date

    # 1. Load companies mapping for names
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

    # 2. Load applications
    apps = load_applications(apps_path)
    if not apps:
        console.print("[yellow]No applications tracked yet. Use 'jobs apply <company>' to track applications.[/yellow]\n")
        return

    # 3. Identify follow-up candidates
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

    # Sort: most overdue first
    candidates.sort(key=lambda x: x["days_since"], reverse=True)

    # 4. Render Table
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

    # 5. Optional Telegram send
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
            if settings.telegram_bot_token and settings.telegram_chat_id:
                send_telegram_message(text_content)
                console.print("[green]✓ Sent follow-up digest to Telegram.[/green]\n")
            else:
                console.print("[yellow]Telegram notification not configured. Skipping notification.[/yellow]\n")
        except ImportError:
            console.print("[yellow]Telegram notification module not available (ImportError). Skipping notification.[/yellow]\n")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error sending Telegram notification: {exc}[/red]\n")





# ---------------------------------------------------------------------------
# 17. recommend
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
    import re
    from rich.table import Table

    # 1. Load companies
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

    # 2. Exclude contacted companies (any note containing "email_sent:")
    uncontacted = [
        c for c in all_companies
        if not any(n.startswith("email_sent:") for n in c.notes)
    ]

    # 3. Handle resume if available
    resume_text = None
    resume_p = None
    try:
        resume_p = resolve_resume_path(resume)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error resolving resume version '{resume}': {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if resume_p:
        if resume_p.exists():
            try:
                resume_text = load_resume_text(resume_p)
                console.print(f"Loaded resume from [bold cyan]{resume_p}[/bold cyan] to evaluate keyword-fit.")
            except Exception as exc:  # noqa: BLE001
                console.print(f"[yellow]Warning: Could not load resume from '{resume_p}': {exc}. Proceeding without resume-fit.[/yellow]")
        else:
            console.print(f"[yellow]Warning: Resume file '{resume_p}' not found. Proceeding without resume-fit.[/yellow]")

    # 4. Helper for tiebreaker recency
    def get_recency(co: Company) -> datetime:
        dates = [
            datetime.combine(j.posted_date, datetime.min.time())
            for j in co.jobs if j.posted_date
        ]
        if dates:
            return max(dates)
        return co.discovered_at or datetime.min

    # Heuristic resume fit calculator
    def calculate_heuristic_fit(co: Company, r_text: str) -> int:
        r_words = set(re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", r_text.lower()))
        if not r_words:
            return 0
        co_text = (
            (co.description or "")
            + " "
            + " ".join(j.job_title + " " + (j.description or "") for j in co.jobs)
        )
        co_words = set(re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", co_text.lower()))
        return len(r_words.intersection(co_words))

    # 5. Rank companies
    # Sort key:
    # First: is_scored (bool) -> Scored companies above unscored.
    # Second: company_score_overall (float) -> Higher score first.
    # Third: job recency (datetime) -> Newer first.
    scored_list = []
    unscored_list = []

    for co in uncontacted:
        is_scored = co.company_score_overall is not None
        recency = get_recency(co)
        fit_score = 0
        if resume_text:
            fit_score = calculate_heuristic_fit(co, resume_text)

        item = {
            "company": co,
            "is_scored": is_scored,
            "overall": co.company_score_overall,
            "recency": recency,
            "fit_score": fit_score,
        }
        if is_scored:
            scored_list.append(item)
        else:
            unscored_list.append(item)

    # Sort scored: primarily overall score (descending), then recency (newest/descending)
    scored_list.sort(key=lambda x: (x["overall"], x["recency"]), reverse=True)
    # Sort unscored: primarily recency (newest/descending)
    unscored_list.sort(key=lambda x: x["recency"], reverse=True)

    ranked_items = scored_list + unscored_list
    top_items = ranked_items[:top]

    # 6. Render Output Table
    table = Table(title="Top Company Recommendations", show_header=True, header_style="bold magenta")
    table.add_column("Rank", justify="right", style="bold yellow")
    table.add_column("Company", style="bold cyan")
    table.add_column("Score", justify="right", style="bold white")
    if resume_text:
        table.add_column("Resume Fit (Overlap)", justify="right", style="bold green")
    table.add_column("Top Job Opening", style="bold white")
    table.add_column("Why / Rationale", style="italic dim white")

    for i, item in enumerate(top_items, 1):
        co = item["company"]
        score_val = f"{item['overall']:.2f}" if item["is_scored"] else "unscored"
        
        # Get top job title
        job_title = "—"
        if co.jobs:
            # Sort jobs by recency
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

        row = [
            str(i),
            co.name,
            score_val,
        ]
        if resume_text:
            row.append(str(item["fit_score"]))
        row.extend([job_title, rationale])

        table.add_row(*row)

    console.print()
    if not resume_text:
        console.print("[dim]Note: No resume configured. Ranking on overall company score alone.[/dim]\n")
    console.print(table)
    console.print()

    # 7. Print unscored warning/hint if any exist
    unscored_count = len([x for x in uncontacted if x.company_score_overall is None])
    if unscored_count > 0:
        console.print(
            f"[yellow]Hint: {unscored_count} companies unscored — run `jobs score-company` or a batch scorer to improve ranking quality.[/yellow]\n"
        )


# ---------------------------------------------------------------------------
# 10. send
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
    # 1. Load database
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' before attempting outreach."
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

    # 2. Filter companies
    # Score warning if score option is passed but no score field is on the Company model
    if score is not None:
        if "score" not in Company.model_fields:
            logger.warning("no score data available, --score ignored, sending to all matches")

    targets: list[Company] = []
    skipped_no_email = 0
    skipped_already_sent = 0

    for c in all_companies:
        # Company name filter
        if company and company.lower() not in c.name.lower():
            continue

        # Score filter (if Company has a score field)
        if score is not None and "score" in Company.model_fields:
            comp_score = getattr(c, "score", None)
            if comp_score is None or comp_score < score:
                continue

        # Usable recipient email filter
        recipient = c.recruiter_email or (c.generic_emails[0] if c.generic_emails else None)
        if not recipient:
            skipped_no_email += 1
            logger.info("outreach/send/{company}: skipped (no recipient email found)", company=c.name)
            continue

        # Already sent filter
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

    # 3. Process batch
    previewed_count = 0
    sent_count = 0
    declined_count = 0

    rate_limiter = RateLimiter()

    for idx, co in enumerate(targets, start=1):
        recipient = co.recruiter_email or co.generic_emails[0]

        console.print(f"Processing target [bold cyan]{co.name}[/bold cyan] ({idx}/{len(targets)})…")

        try:
            res = generate_email(co, template_name=template, model=model, dry_run=False)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]✗ Failed to generate email for {co.name}: {exc}[/red]")
            continue

        if not res["body"]:
            console.print(f"[red]✗ Failed to generate email body for {co.name}.[/red]")
            continue

        # Display preview
        _render_preview_panel(co.name, recipient, res["subject"], res["body"], res["template_used"])

        # Decide whether to send
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
                # Respect request_delay_seconds (using "smtp" pseudo-domain)
                rate_limiter.wait("smtp")

                console.print(f"  Sending email to {recipient}…")
                try:
                    success = send_email(recipient, res["subject"], res["body"])
                    if success:
                        sent_count += 1
                        co.notes.append(f"email_sent: {date.today().isoformat()} via {template}")
                        co.last_updated = datetime.now()
                        console.print("[green]  ✓ Sent successfully![/green]\n")
                    else:
                        console.print("[red]  ✗ SMTP delivery failed.[/red]\n")
                except Exception as exc:
                    console.print(f"[red]  ✗ SMTP connection failed: {exc}[/red]\n")

    # 4. Write back database changes
    try:
        input.write_bytes(
            orjson.dumps(
                [c.model_dump(mode="json") for c in all_companies],
                option=orjson.OPT_INDENT_2,
            )
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to update database {input}: {exc}[/red]")

    # 5. Print Summary
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
# 11. test-telegram
# ---------------------------------------------------------------------------

@app.command(name="test-telegram")
def test_telegram() -> None:
    """Send a test message to verify Telegram Bot API settings."""
    console.print("Sending Telegram test notification…")
    try:
        success = send_telegram_message("🔔 *Hiring Radar Test Notification*\n\nIf you see this, your Telegram Bot integration is working correctly! 🎉")
        if success:
            console.print("[bold green]✓ Test notification sent successfully![/bold green] Please check your Telegram chat.")
        else:
            console.print("[bold red]✗ Failed to send test notification.[/bold red] Ensure that TELEGRAM_BOT_TOKEN is set in .env, telegram.enabled is true and telegram.chat_id is set in config.yaml, and verify your bot credentials.")
            raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error sending Telegram notification:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# 12. watch
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
    import time
    from datetime import datetime

    companies_file = settings.output_dir / "companies.json"

    def get_current_state() -> dict[str, Company]:
        if not companies_file.exists():
            return {}
        try:
            raw = orjson.loads(companies_file.read_bytes())
            return {c.dedupe_key(): c for c in [Company.model_validate(x) for x in raw]}
        except Exception as exc:  # noqa: BLE001
            logger.warning("watch: failed to load existing database ({exc})", exc=exc)
            return {}

    console.print()
    if once:
        console.print("[bold cyan]Watch mode: running a single check...[/bold cyan]")
    else:
        console.print(f"[bold cyan]Watch mode: starting polling loop (interval: {interval}m, sources: {sources})...[/bold cyan]")
        console.print("[dim]Press Ctrl+C to terminate watch loop cleanly.[/dim]\n")

    # Load alert rules if alerts are enabled
    alert_rules = []
    if alerts:
        alert_rules = load_alert_rules()
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

    try:
        while True:
            cycle_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"[{cycle_time}] Checking for new hiring activities…")

            # a. Load previous state
            previous_state = get_current_state()

            # b. Run discovery
            try:
                _run_discovery(
                    sources=sources,
                    seed_file=None,
                    limit=100,
                    profile=profile,
                    remote=None,
                    country=None,
                    keyword=None,
                    exclude=None,
                    days=None,
                )
            except Exception as exc:  # noqa: BLE001
                console.print(f"[red]⚠ Discovery failed this cycle: {exc}[/red]")

            # c. Reload new state
            new_state = get_current_state()

            # d. Diff and Send Alerts
            new_companies_alerted = 0
            new_jobs_alerted = 0

            for key, new_co in new_state.items():
                if key not in previous_state:
                    # Brand new company
                    if should_alert_company(new_co):
                        alert_msg = format_new_company_alert(new_co)
                        console.print(f"  [green]+[/green] New company: [bold]{new_co.name}[/bold]. Sending Telegram alert…")
                        send_telegram_message(alert_msg)
                        new_companies_alerted += 1
                        time.sleep(1)  # brief sleep to avoid burst rate-limits
                else:
                    # Existing company, diff jobs list
                    prev_co = previous_state[key]
                    prev_urls = {j.job_url for j in prev_co.jobs}
                    new_jobs = [j for j in new_co.jobs if j.job_url not in prev_urls]
                    if new_jobs:
                        new_jobs_co = new_co.model_copy(update={"jobs": new_jobs})
                        if should_alert_company(new_jobs_co):
                            # Filter new_jobs to those that match at least one rule
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
                                
                                # Short alert message
                                msg = (
                                    f"🔔 *New Job Openings at {new_co.name}*\n\n"
                                    f"💼 Added {count_new} new role(s), including:\n"
                                    f"👉 [{first_new_job.job_title}]({first_new_job.job_url})\n\n"
                                    f"#hiring #{new_co.ats_platform or 'feed'}"
                                )
                                console.print(f"  [cyan]*[/cyan] {new_co.name}: {count_new} new job(s) matching alert rules found. Sending Telegram alert…")
                                send_telegram_message(msg)
                                new_jobs_alerted += 1
                                time.sleep(1)  # brief sleep to avoid burst rate-limits

            # e. Cycle logging
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
        
        # f. Clean termination summary
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
# 13. digest
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
    import re
    from datetime import datetime, timedelta

    # 1. Load database
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' to collect data first."
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

    # 2. Filter to last 24 hours
    window_start = datetime.now() - timedelta(hours=24)
    recent_companies: list[Company] = []
    for c in all_companies:
        c_time = c.discovered_at.replace(tzinfo=None) if c.discovered_at.tzinfo else c.discovered_at
        if c_time >= window_start:
            recent_companies.append(c)

    # 3. Compute metrics
    total_companies = len(recent_companies)
    total_jobs = sum(len(c.jobs) for c in recent_companies)

    # Note: this is a rough keyword-based heuristic, not authoritative categorization.
    ai_pattern = re.compile(r'\b(ai|ml|nlp|computer vision)\b|artificial intelligence|machine learning|deep learning', re.IGNORECASE)
    backend_pattern = re.compile(r'\b(backend|back-end|python|go|golang|rust|java|node|django|fastapi|c\+\+|c#|\.net|ruby|rails)\b', re.IGNORECASE)
    frontend_pattern = re.compile(r'\b(frontend|front-end|react|next\.js|nextjs|typescript|javascript|vue|angular|ui|ux|css|html)\b', re.IGNORECASE)

    ai_count = 0
    backend_count = 0
    frontend_count = 0
    other_count = 0

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

    # Sort recent companies by job count descending
    # Note: Top picks currently use job count as a simple proxy for active hiring.
    # This should be replaced with actual score-based ranking once Phase 10 (Scoring/Prioritization) lands.
    top_picks = sorted(recent_companies, key=lambda c: len(c.jobs), reverse=True)[:5]

    # 4. Format Markdown
    top_picks_lines = []
    for idx, c in enumerate(top_picks, start=1):
        top_picks_lines.append(f"{idx}. {c.name} — {len(c.jobs)} new jobs")
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

    # 5. Send or print
    if send:
        console.print("Posting daily hiring digest to Telegram…")
        success = send_telegram_message(digest_text)
        if success:
            console.print("[bold green]✓ Daily digest posted successfully to Telegram![/bold green]")
        else:
            console.print("[bold red]✗ Failed to post daily digest to Telegram.[/bold red]")

    # Either way, print to console
    from rich.panel import Panel
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
# 13.5 morning-brief
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
    """Generate a daily cold outreach hiring digest and send it to Telegram.

    Identical to `jobs digest --send`.
    """
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
# 13.6 report
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
    """Generate an end-of-day summary of user activity over a reporting window.

    Future polish (e.g. weekly/monthly rollups) can build on this same pattern later if wanted.
    """
    import re
    from rich.panel import Panel

    # Calculate date window boundaries
    window_start = datetime.now() - timedelta(days=days)
    window_start_date = window_start.date()

    # 1. Gather stats from companies.json
    new_companies_count = 0
    new_jobs_count = 0
    emails_sent_count = 0

    if input.exists():
        try:
            raw_companies = orjson.loads(input.read_bytes())
            for c_dict in raw_companies:
                # New companies discovered
                disc_at_str = c_dict.get("discovered_at")
                if disc_at_str:
                    try:
                        disc_dt = datetime.fromisoformat(disc_at_str)
                        c_time = disc_dt.replace(tzinfo=None) if disc_dt.tzinfo else disc_dt
                        if c_time >= window_start:
                            new_companies_count += 1
                            jobs_list = c_dict.get("jobs", [])
                            new_jobs_count += len(jobs_list)
                    except Exception:
                        pass

                # Emails drafted/sent
                notes = c_dict.get("notes", [])
                if isinstance(notes, list):
                    for note in notes:
                        if isinstance(note, str) and note.startswith("email_sent:"):
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
            raw_apps = orjson.loads(apps_path.read_bytes())
            if isinstance(raw_apps, dict):
                for app_key, app_dict in raw_apps.items():
                    history = app_dict.get("status_history", [])
                    if isinstance(history, list):
                        for hist_item in history:
                            if isinstance(hist_item, dict) and hist_item.get("status") == "applied":
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

        # 3. Follow-ups still pending (dependent on tracker module existence/imports)
        try:
            from app.tracker.status import load_applications
            apps_data = load_applications(apps_path)
            today = date.today()
            pending_followups_count = 0
            for key, app_obj in apps_data.items():
                if app_obj.status not in ("applied", "interviewing"):
                    continue
                if not app_obj.last_contact_date:
                    continue
                days_since = (today - app_obj.last_contact_date).days
                if days_since >= 7:  # default threshold
                    pending_followups_count += 1
        except Exception:
            # Handle gracefully if tracker/models/dependencies are missing or raise exceptions
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

    # 5. Optional Telegram send
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
            success = send_telegram_message(report_text)
            if success:
                console.print("[bold green]✓ Activity report posted successfully to Telegram![/bold green]")
            else:
                console.print("[bold red]✗ Failed to post activity report to Telegram.[/bold red]")

    # Either way, print to console in a nice Panel
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
# 14. dashboard
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
    import webbrowser

    console.print(f"Generating static dashboard from [bold cyan]{input}[/bold cyan]...")
    try:
        build_dashboard(input_path=input, output_path=output)
        console.print(f"[bold green][OK] Dashboard generated successfully![/bold green] Saved to: [dim]{output}[/dim]")

        if open_browser:
            console.print("Opening dashboard in your default browser...")
            webbrowser.open(output.absolute().as_uri())
    except Exception as exc:
        console.print(f"[bold red]Error generating dashboard:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc



# ---------------------------------------------------------------------------
# 22. mcp-serve
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
    import os
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
# 23. agent
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
    from rich.prompt import Prompt
    from rich.markdown import Markdown
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

                # Render tools called so far
                if res.get("tool_calls_made"):
                    tools_str = ", ".join(res["tool_calls_made"])
                    console.print(f"[dim]🔧 Tools invoked: {tools_str}[/dim]")

                console.print(f"\n[bold yellow]⚠️ Pending Approval:[/bold yellow] Agent wants to {desc}")
                approved = typer.confirm("Approve this action?")

                from app.agent.tools import execute_approved_tool
                from app.agent.memory import log_decision
                import json

                if approved:
                    log_decision(f"Approved and executed tool '{tool_name}' with arguments {args}")
                    with console.status(f"[bold yellow]Executing {tool_name}...[/bold yellow]"):
                        tool_result = execute_approved_tool(tool_name, args)
                else:
                    log_decision(f"Declined execution of tool '{tool_name}' with arguments {args}")
                    tool_result = {"error": "User declined to approve this action."}

                # Append tool result message
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": tool_name,
                    "content": json.dumps(tool_result),
                }
                conversation_history.append(tool_msg)

                # Resume the turn
                user_input_to_send = ""
                continue
            else:
                # Render tools called
                if res.get("tool_calls_made"):
                    tools_str = ", ".join(res["tool_calls_made"])
                    console.print(f"[dim]🔧 Tools invoked: {tools_str}[/dim]")

                # Render reply
                console.print(Markdown(res["reply"]))
                break


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Allows:  python -m app.cli <command>
    # The `hiring-radar` console script (pyproject.toml) calls app() directly.
    app()