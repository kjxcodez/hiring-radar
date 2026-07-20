"""Tracker domain commands: apply, note, followups, recommend."""

from __future__ import annotations

import orjson as _orjson_orig
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from app.cli.common import (
    console,
    get_container,
    resolve_resume_path,
    ModuleProxy,
    FuncProxy,
)
from app.config import settings, yaml_config
from app.models import Application, ApplicationStatus, Company
from app.tracker.status import (
    load_applications as _load_applications_orig,
    save_applications as _save_applications_orig,
    set_status,
)
from app.resume.parser import load_resume_text

orjson = ModuleProxy("orjson", _orjson_orig)
load_applications = FuncProxy("load_applications", _load_applications_orig)
save_applications = FuncProxy("save_applications", _save_applications_orig)


# ---------------------------------------------------------------------------
# 12. apply
# ---------------------------------------------------------------------------

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
            resolve_resume_path(resume)
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
