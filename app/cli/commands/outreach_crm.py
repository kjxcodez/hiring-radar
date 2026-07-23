"""Outreach and Candidate CRM CLI commands."""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.table import Table
from rich.panel import Panel

from app.cli.common import console, get_container
from app.config import settings
from app.outreach.profile import OutreachMessage
from app.outreach.timeline import TimelineTracker

# Create Typer sub-app
apply_app = typer.Typer(
    name="apply",
    help="Outreach drafts, application tracking, and candidate CRM.",
    no_args_is_help=False,
)


@apply_app.callback(invoke_without_command=True)
def apply_callback(
    ctx: typer.Context,
) -> None:
    """Outreach and Candidate CRM command group."""
    if ctx.invoked_subcommand is not None:
        return
    # If no subcommand, list all applications
    list_applications()


@apply_app.command(name="list")
def list_applications() -> None:
    """List all current applications in the CRM database."""
    container = get_container()
    apps = container.application_repo.load_all()
    if not apps:
        console.print("[yellow]No applications found in the CRM.[/yellow]")
        console.print("  Run [bold]hiring-radar apply prepare <company>[/bold] to start.")
        return

    table = Table(title="Candidate CRM Applications", show_header=True, header_style="bold magenta")
    table.add_column("Company", style="bold cyan")
    table.add_column("Job Title", style="bold white")
    table.add_column("Status", style="bold green")
    table.add_column("Next Follow-up", style="bold yellow")
    table.add_column("Last Updated", style="dim white")

    # Sort applications by status transition activity or last updated
    for co_key, app in sorted(apps.items(), key=lambda item: item[1].last_updated or datetime.min, reverse=True):
        co_name = app.company.name if app.company else co_key
        job_title = app.job.job_title if app.job else "—"
        last_updated = app.last_updated.strftime("%Y-%m-%d %H:%M") if app.last_updated else "—"
        table.add_row(
            co_name,
            job_title,
            app.status,
            app.next_followup or "—",
            last_updated,
        )

    console.print()
    console.print(table)
    console.print()


@apply_app.command(name="prepare")
def prepare_company(
    company_name: str = typer.Argument(..., help="Name of the company to prepare outreach for."),
    force: Annotated[
        bool,
        typer.Option("--force", help="Force rebuild outreach drafts and schedules."),
    ] = False,
) -> None:
    """Prepare tailored resume tips, cover letter, email, LinkedIn, and referral drafts."""
    container = get_container()
    try:
        console.print(f"[bold green]Executing outreach drafting engine for {company_name}...[/bold green]")
        app = container.outreach_engine.prepare_application(company_name, force=force)

        console.print(f"\n[green]✓ Successfully prepared outreach for [bold]{company_name}[/bold]![/green]")
        console.print(f"  [bold]CRM Status:[/bold] {app.status}")
        console.print(f"  [bold]Cover Letter Drafted:[/bold] Yes ({len(app.cover_letter_version)} chars)")
        console.print(f"  [bold]Outreach Channels Ready:[/bold] Email, LinkedIn, Referral")
        console.print(f"  [bold]Follow-up Schedule Initialized:[/bold] {len(app.followup_schedule)} milestones")
        console.print()
    except Exception as exc:
        console.print(f"[red]Error during outreach preparation: {exc}[/red]")
        raise typer.Exit(code=1)


@apply_app.command(name="email")
def view_email(
    company_name: str = typer.Argument(..., help="Name of the company."),
) -> None:
    """Show the generated cold outreach email draft for a company."""
    container = get_container()
    apps = container.application_repo.load_all()
    # Find matching company key
    matched_key = None
    for key in apps:
        if company_name.lower() in key:
            matched_key = key
            break

    if not matched_key:
        console.print(f"[yellow]No application in CRM matches '{company_name}'.[/yellow]")
        return

    app = apps[matched_key]
    email_msg = next((m for m in app.messages if m.channel == "email"), None)

    if not email_msg:
        console.print("[yellow]No email draft found for this application.[/yellow]")
        return

    console.print()
    console.print(Panel(
        f"[bold yellow]Subject:[/bold yellow] {email_msg.subject}\n\n{email_msg.content}",
        title=f"Email Draft: {app.company.name if app.company else matched_key}",
        border_style="cyan"
    ))
    console.print("\n[dim]Note: This email is a draft. Copy/paste or refine it before sending.[/dim]\n")


@apply_app.command(name="linkedin")
def view_linkedin(
    company_name: str = typer.Argument(..., help="Name of the company."),
) -> None:
    """Show the recruiter LinkedIn message draft (<300 chars)."""
    container = get_container()
    apps = container.application_repo.load_all()
    matched_key = None
    for key in apps:
        if company_name.lower() in key:
            matched_key = key
            break

    if not matched_key:
        console.print(f"[yellow]No application in CRM matches '{company_name}'.[/yellow]")
        return

    app = apps[matched_key]
    li_msg = next((m for m in app.messages if m.channel == "linkedin"), None)

    if not li_msg:
        console.print("[yellow]No LinkedIn message draft found for this application.[/yellow]")
        return

    console.print()
    console.print(Panel(
        li_msg.content,
        title=f"LinkedIn Recruiter Note: {app.company.name if app.company else matched_key}",
        subtitle=f"Length: {len(li_msg.content)}/300 chars",
        border_style="cyan"
    ))
    console.print()


@apply_app.command(name="cover-letter")
def view_cover_letter(
    company_name: str = typer.Argument(..., help="Name of the company."),
) -> None:
    """Show the generated cover letter draft."""
    container = get_container()
    apps = container.application_repo.load_all()
    matched_key = None
    for key in apps:
        if company_name.lower() in key:
            matched_key = key
            break

    if not matched_key:
        console.print(f"[yellow]No application in CRM matches '{company_name}'.[/yellow]")
        return

    app = apps[matched_key]
    if not app.cover_letter_version:
        console.print("[yellow]No cover letter found for this application.[/yellow]")
        return

    console.print()
    console.print(Panel(
        app.cover_letter_version,
        title=f"Cover Letter: {app.company.name if app.company else matched_key}",
        border_style="cyan"
    ))
    console.print()


@apply_app.command(name="referral")
def view_referral(
    company_name: str = typer.Argument(..., help="Name of the company."),
) -> None:
    """Show the generated employee referral request draft."""
    container = get_container()
    apps = container.application_repo.load_all()
    matched_key = None
    for key in apps:
        if company_name.lower() in key:
            matched_key = key
            break

    if not matched_key:
        console.print(f"[yellow]No application in CRM matches '{company_name}'.[/yellow]")
        return

    app = apps[matched_key]
    ref_msg = next((m for m in app.messages if m.channel == "referral"), None)

    if not ref_msg:
        console.print("[yellow]No referral message draft found for this application.[/yellow]")
        return

    console.print()
    console.print(Panel(
        ref_msg.content,
        title=f"Referral Request Note: {app.company.name if app.company else matched_key}",
        border_style="cyan"
    ))
    console.print()


@apply_app.command(name="timeline")
def view_timeline(
    company_name: str = typer.Argument(..., help="Name of the company."),
) -> None:
    """Show the event timeline for this company application."""
    container = get_container()
    apps = container.application_repo.load_all()
    matched_key = None
    for key in apps:
        if company_name.lower() in key:
            matched_key = key
            break

    if not matched_key:
        console.print(f"[yellow]No application in CRM matches '{company_name}'.[/yellow]")
        return

    app = apps[matched_key]
    if not app.timeline:
        console.print("[yellow]Timeline is empty.[/yellow]")
        return

    console.print(f"\n[bold cyan]Timeline: {app.company.name if app.company else matched_key}[/bold cyan]\n")
    for entry in app.timeline:
        ts = entry.timestamp[:16].replace("T", " ")
        console.print(f"  [bold yellow]{ts}[/bold yellow] - [bold]{entry.event}[/bold]")
        console.print(f"    [dim]{entry.description}[/dim]")
    console.print()


@apply_app.command(name="refresh")
def refresh_applications() -> None:
    """Regenerate drafts and follow-up schedules for all CRM records."""
    container = get_container()
    apps = container.application_repo.load_all()
    if not apps:
        console.print("[yellow]No application records in the CRM to refresh.[/yellow]")
        return

    console.print(f"[bold green]Refreshing {len(apps)} applications...[/bold green]")
    for co_key, app in apps.items():
        co_name = app.company.name if app.company else co_key
        console.print(f"  Refreshing [bold cyan]{co_name}[/bold cyan]...")
        try:
            container.outreach_engine.prepare_application(
                company_name=co_name,
                candidate=app.candidate,
                force=True,
            )
        except Exception as exc:  # noqa: BLE001
            console.print(f"    [red]Failed to refresh {co_name}: {exc}[/red]")

    console.print("[green]✓ CRM applications refreshed successfully.[/green]")
