"""Discovery domain commands: discover, search save/run/list, watch, _run_discovery."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from loguru import logger
from rich.table import Table

from app.cli.common import build_discovery_event_callback, console, get_container
from app.config import settings
from app.discover import SOURCE_REGISTRY
from app.discover.seed import load_seed_slugs, resolve_seed_companies
from app.filters import apply_filters
from app.models import Company
from app.notify import format_new_company_alert, send_telegram_message

# ---------------------------------------------------------------------------
# Internal helper — used by discover command and tests directly
# ---------------------------------------------------------------------------


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
            console.print(f"  [dim]Resolving names in seed file:[/dim] {seed_file}...")
            seed_companies = resolve_seed_companies(seed_file)
            console.print(f"  [green]✓[/green]  Resolved {len(seed_companies)} company/companies from seed file")
        else:
            console.print(f"  [red]✗[/red]  Seed file not found: {seed_file}")

    # --- Event Callback for real-time printing ---
    event_callback = build_discovery_event_callback()

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
# 7. search sub-commands (save / run / list)
# ---------------------------------------------------------------------------


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

    event_callback = build_discovery_event_callback()

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
# 19. watch
# ---------------------------------------------------------------------------


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
                logger.debug(
                    "watch alert match: company '{company}' matched alert rule '{rule}'",
                    company=co_to_check.name,
                    rule=rule.name,
                )
                return True
        return False

    # Resolve SearchProfile if present
    loaded_prof = None
    if profile:
        loaded_prof = container.profile_repo.load_profile(profile)

    def _silent_event_callback(event_type: str, data: dict[str, Any]) -> None:
        pass  # Keep watch output uncluttered by sub-discover prints

    try:
        while True:
            cycle_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"[{cycle_time}] Checking for new hiring activities...")

            previous_state = get_current_state()

            try:
                container.discovery_service.discover(
                    sources=sources,
                    limit=100,
                    profile=loaded_prof,
                    event_callback=_silent_event_callback,
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
                        console.print(f"  [green]+[/green] New company: [bold]{new_co.name}[/bold]. Sending Telegram alert...")
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
                                matched_urls: set[str] = set()
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
                                console.print(f"  [cyan]*[/cyan] {new_co.name}: {count_new} new job(s) matching alert rules found. Sending Telegram alert...")
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

            console.print(f"Sleeping for {interval} minutes (next check around {datetime.now() + timedelta(minutes=interval)})...\n")
            time.sleep(interval * 60)

    except KeyboardInterrupt:
        console.print()
        console.print("[bold yellow]Watch loop interrupted by user. Exiting cleanly...[/bold yellow]")

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
