"""AI Recommendation CLI command group definitions for Typer."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.table import Table

from app.cli.common import console, get_container
from app.config import settings
from app.resume.versions import resolve_resume_version
from app.resume.parser import load_resume_text
from app.cli.commands.tracker import resolve_resume_path

# Create Typer sub-app
recommend_app = typer.Typer(
    name="recommend",
    help="AI-powered candidate matching and job recommendations.",
    no_args_is_help=False,
)


@recommend_app.callback(invoke_without_command=True)
def recommend_cli(
    ctx: Optional[typer.Context] = None,
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
    if ctx and ctx.invoked_subcommand is not None:
        return


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
            job_title = jobs_sorted[0].job_title

        rationale = "—"
        if co.notes:
            for note in co.notes:
                if note.startswith("score_rationale:"):
                    rationale = note[len("score_rationale:"):].strip()
                    break

        row = [str(i), co.name, score_val]
        if has_resume:
            row.append(str(item["fit_score"]))
        row.append(job_title)
        row.append(rationale)
        table.add_row(*row)

    console.print(table)

    # Print reminder for unscored
    unscored_count = sum(1 for item in recs if not item["is_scored"])
    if unscored_count > 0:
        console.print(f"\n[dim]* Note: {unscored_count} companies unscored. Run 'hiring-radar enrich' first.[/dim]")


@recommend_app.command(name="resume")
def recommend_resume(
    path: str = typer.Argument(..., help="Path to resume file (.txt, .md, .pdf, .docx)."),
    force: Annotated[
        bool,
        typer.Option("--force", help="Wipe caches and force full re-enrichment of recommendations."),
    ] = False,
) -> None:
    """Parse resume, extract candidate features, and run recommendation scoring."""
    container = get_container()
    resume_path = Path(path)
    if not resume_path.exists():
        console.print(f"[red]Error: Resume path '{path}' does not exist.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold green]Parsing candidate resume {resume_path.name}...[/bold green]")
    from app.recommendation.resume import ResumeParser
    cand = ResumeParser.parse(resume_path, container.ai_gateway)

    # Keep a cached version of candidate profile in output dir
    profile_cache = container.settings.output_dir / "candidate_profile.json"
    container.storage.write(profile_cache, cand.model_dump(mode="json"))

    console.print("[bold green]Executing Recommendation Engine...[/bold green]")
    recs = container.recommendation_engine.recommend(cand, force=force)

    # Show top 5
    show_top_table(recs, limit=5)


@recommend_app.command(name="top")
def recommend_top(
    limit: Annotated[
        int,
        typer.Option("--limit", help="Number of top matches to list."),
    ] = 10,
) -> None:
    """List current top-ranked recommendations."""
    container = get_container()
    recs = container.recommendation_repo.load_recommendations()
    if not recs:
        console.print("[yellow]No recommendation records found.[/yellow]")
        console.print("  Run [bold]hiring-radar recommend resume <path>[/bold] first.")
        return

    show_top_table(recs, limit=limit)


@recommend_app.command(name="company")
def recommend_company(
    name: str = typer.Argument(..., help="Name of the company to view."),
) -> None:
    """Show detailed match score and AI fit reasons for a single company."""
    container = get_container()
    recs = container.recommendation_repo.load_recommendations()
    matches = [r for r in recs if name.lower() in r.get("company_name", "").lower()]

    if not matches:
        console.print(f"[yellow]No recommendations found matching company '{name}'.[/yellow]")
        return

    for rec in matches[:3]:
        print_detailed_rec(rec)


@recommend_app.command(name="explain")
def recommend_explain(
    index: int = typer.Argument(..., help="Rank index of the recommendation to explain."),
) -> None:
    """Explain matching details for a specific ranked index."""
    container = get_container()
    recs = container.recommendation_repo.load_recommendations()
    if not recs:
        console.print("[yellow]No recommendation records found.[/yellow]")
        return

    if index < 1 or index > len(recs):
        console.print(f"[red]Error: Index must be between 1 and {len(recs)}.[/red]")
        raise typer.Exit(code=1)

    rec = recs[index - 1]
    print_detailed_rec(rec)


@recommend_app.command(name="refresh")
def recommend_refresh() -> None:
    """Wipe caches and recalculate all recommendations."""
    container = get_container()
    profile_cache = container.settings.output_dir / "candidate_profile.json"
    if not profile_cache.exists():
        console.print("[yellow]No cached candidate profile found.[/yellow]")
        console.print("  Run [bold]hiring-radar recommend resume <path>[/bold] first.")
        return

    from app.recommendation.profile import CandidateProfile
    data = container.storage.read(profile_cache)
    cand = CandidateProfile.model_validate(data)

    console.print("[bold green]Refreshing recommendations cache...[/bold green]")
    recs = container.recommendation_engine.recommend(cand, force=True)
    show_top_table(recs, limit=5)


# Helpers
def show_top_table(recs: list[dict], limit: int = 10) -> None:
    """Render top matches list to console."""
    table = Table(title="AI Recommendation Matching", show_header=True, header_style="bold magenta")
    table.add_column("Rank", justify="right", style="bold yellow")
    table.add_column("Company", style="bold cyan")
    table.add_column("Job Title", style="bold white")
    table.add_column("Match Score", justify="right", style="bold green")
    table.add_column("Why it fits", style="italic dim white")

    for rec in recs[:limit]:
        why = rec.get("explanation", {}).get("why_fit", "—")
        table.add_row(
            str(rec.get("rank", "—")),
            rec.get("company_name", "—"),
            rec.get("job_title", "—"),
            f"{rec.get('score', 0.0):.1f}%",
            why,
        )

    console.print()
    console.print(table)
    console.print()


def print_detailed_rec(rec: dict) -> None:
    """Print detailed recommendation report."""
    console.print()
    console.print(f"[bold cyan]Recommendation Report: {rec.get('job_title')} at {rec.get('company_name')}[/bold cyan]")
    console.print(f"  [dim]Rank:[/dim] #{rec.get('rank')} | [dim]Match Score:[/dim] [bold green]{rec.get('score')}%[/bold green]")
    console.print()

    exp = rec.get("explanation", {})
    console.print(f"[bold white]Why it fits:[/bold white]")
    console.print(f"  {exp.get('why_fit', '—')}")
    console.print()

    table_sw = Table(show_header=False)
    table_sw.add_column("Type", style="bold white")
    table_sw.add_column("Items", style="bold yellow")
    table_sw.add_row("Strengths", ", ".join(rec.get("strengths", [])) or "—")
    table_sw.add_row("Missing Skills", ", ".join(rec.get("missing_skills", [])) or "—")
    console.print(table_sw)
    console.print()

    console.print("[bold white]Resume Improvement Suggestions:[/bold white]")
    for tip in exp.get("resume_improvements", []):
        console.print(f"  • {tip}")
    console.print()

    console.print("[bold white]Suggested Learning Roadmap:[/bold white]")
    for step in exp.get("study_roadmap", []):
        console.print(f"  • {step}")
    console.print()

    console.print("[bold white]Personalized Outreach Talking Points:[/bold white]")
    for pt in exp.get("outreach_talking_points", []):
        console.print(f"  • {pt}")
    console.print()
