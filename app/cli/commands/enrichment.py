"""Enrichment domain commands: research, score-company, tailor."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.console import Group

from app.cli.common import console, get_container
from app.config import settings
from app.enrich.company_score import score_company_attractiveness

# ---------------------------------------------------------------------------
# 9. research
# ---------------------------------------------------------------------------

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

    console.print(f"Performing deeper corporate research on [bold cyan]{company_name}[/bold cyan]...")
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
