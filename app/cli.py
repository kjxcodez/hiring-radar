"""hiring-radar CLI entrypoint.

Run as:
    python -m app.cli <command>      # always works, no install needed
    hiring-radar <command>           # after `pip install -e .` (see pyproject.toml)
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import orjson
import typer
from rich.console import Console
from rich.table import Table

from app.config import settings
from app.utils import setup_logging

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

    console.print()
    console.print("[bold yellow]⚠  discover — not implemented yet[/bold yellow]")
    console.print()
    console.print(f"  [dim]Sources requested:[/dim] {', '.join(source_list)}")
    console.print(f"  [dim]Limit:[/dim]            {limit}")
    if seed_file:
        console.print(f"  [dim]Seed file:[/dim]        {seed_file}")
    console.print()
    console.print(
        "  This command will query each source, deduplicate results, and write"
        " [bold]output/companies.json[/bold]."
    )
    console.print()
    raise typer.Exit(code=0)


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
            help="Single company name/slug for targeted debugging.",
        ),
    ] = None,
) -> None:
    """Fetch full job listings and career-page data for discovered companies."""
    console.print()
    console.print("[bold yellow]⚠  scrape — not implemented yet[/bold yellow]")
    console.print()
    console.print(f"  [dim]Input:[/dim]   {input}")
    if company:
        console.print(f"  [dim]Company:[/dim] {company}")
    console.print()
    console.print(
        "  This command will iterate each company, pull its ATS job listings,"
        " and enrich the companies.json in place."
    )
    console.print()
    raise typer.Exit(code=0)


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
    """Show a summary of locally collected data."""
    companies_file = settings.output_dir / "companies.json"

    if not companies_file.exists():
        console.print()
        console.print("[bold red]No data found.[/bold red]")
        console.print(
            f"  [dim]{companies_file}[/dim] does not exist yet.\n"
            "  Run [bold]hiring-radar discover[/bold] first to collect companies."
        )
        console.print()
        raise typer.Exit(code=0)

    raw = companies_file.read_bytes()
    try:
        data: list[dict] = orjson.loads(raw)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to parse {companies_file}:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not isinstance(data, list):
        console.print(f"[red]Expected a JSON array in {companies_file}.[/red]")
        raise typer.Exit(code=1)

    total = len(data)
    with_jobs = sum(1 for c in data if c.get("jobs"))
    with_email = sum(
        1 for c in data
        if c.get("generic_emails") or c.get("recruiter_email")
    )
    with_ai = sum(1 for c in data if c.get("ai_summary"))

    table = Table(title="hiring-radar · local data status", show_header=True)
    table.add_column("Metric", style="bold cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="bold white")

    table.add_row("Total companies", str(total))
    table.add_row("Companies with ≥1 job listing", str(with_jobs))
    table.add_row("Companies with email found", str(with_email))
    table.add_row("Companies with AI summary", str(with_ai))

    console.print()
    console.print(table)
    console.print(f"\n  [dim]Source:[/dim] {companies_file}")
    console.print()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Allows:  python -m app.cli <command>
    # The `hiring-radar` console script (pyproject.toml) calls app() directly.
    app()