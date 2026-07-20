"""Outreach domain commands: preview, send, digest, morning-brief, report, test-smtp, test-telegram."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Optional

import typer
from loguru import logger
from rich.panel import Panel
from rich.table import Table

from app.cli.common import _render_preview_panel, console, get_container, resolve_symbol
from app.config import settings, yaml_config
from app.utils import RateLimiter


# ---------------------------------------------------------------------------
# 8. preview
# ---------------------------------------------------------------------------


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
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' before attempting preview."
        )
        raise typer.Exit(code=1)

    container = get_container()
    outreach_service = container.outreach_service

    # Custom repository if path overridden
    if input != container.company_repo.filepath:
        from app.repositories.company import CompanyRepository
        from app.services.outreach import OutreachService
        outreach_service = OutreachService(CompanyRepository(input), container.settings, container.yaml_config)

    console.print(f"Generating email for [bold cyan]{company_name}[/bold cyan] using template '{template}'...")
    try:
        res = outreach_service.generate_outreach_draft(
            company_name=company_name,
            template=template,
            model=model,
            dry_run=False,
        )
    except Exception as exc:
        console.print(f"[red]Error: Failed to generate email: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not res["body"]:
        console.print("[red]Error: Generated email body was empty. Check OpenRouter API key and settings.[/red]")
        raise typer.Exit(code=1)

    _render_preview_panel(res["company"].name, res["recipient"], res["subject"], res["body"], res["template_used"])


# ---------------------------------------------------------------------------
# 16. send
# ---------------------------------------------------------------------------


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
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' before attempting outreach."
        )
        raise typer.Exit(code=1)

    container = get_container()
    outreach_service = container.outreach_service

    # Custom repository if path overridden
    if input != container.company_repo.filepath:
        from app.repositories.company import CompanyRepository
        from app.services.outreach import OutreachService
        outreach_service = OutreachService(CompanyRepository(input), container.settings, container.yaml_config)

    all_companies = outreach_service.company_repo.load_all()

    # Filter targets
    targets = []
    skipped_no_email = 0
    skipped_already_sent = 0

    for c in all_companies:
        if company and company.lower() not in c.name.lower():
            continue

        recipient = c.recruiter_email or (c.generic_emails[0] if c.generic_emails else None)
        if not recipient:
            skipped_no_email += 1
            logger.info("outreach/send/{company}: skipped (no recipient email found)", company=c.name)
            continue

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

    # Process batch
    previewed_count = 0
    sent_count = 0
    declined_count = 0

    rate_limiter = RateLimiter()

    for idx, co in enumerate(targets, start=1):
        recipient = co.recruiter_email or co.generic_emails[0]
        console.print(f"Processing target [bold cyan]{co.name}[/bold cyan] ({idx}/{len(targets)})...")

        try:
            res = outreach_service.generate_outreach_draft(
                company_name=co.name,
                template=template,
                model=model,
                dry_run=False,
            )
        except Exception as exc:
            console.print(f"[red]✗ Failed to generate email for {co.name}: {exc}[/red]")
            continue

        if not res["body"]:
            console.print(f"[red]✗ Failed to generate email body for {co.name}.[/red]")
            continue

        _render_preview_panel(co.name, recipient, res["subject"], res["body"], res["template_used"])

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
                rate_limiter.wait("smtp")
                console.print(f"  Sending email to {recipient}...")
                try:
                    success = outreach_service.send_outreach_email(recipient, res["subject"], res["body"])
                    if success:
                        sent_count += 1
                        outreach_service.mark_email_sent(co.name, template)
                        console.print("[green]  ✓ Sent successfully![/green]\n")
                    else:
                        console.print("[red]  ✗ SMTP delivery failed.[/red]\n")
                except Exception as exc:
                    console.print(f"[red]  ✗ SMTP connection failed: {exc}[/red]\n")

    # Print Summary
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
# 17. test-smtp
# ---------------------------------------------------------------------------


def test_smtp(
    email: str = typer.Argument(..., help="Recipient email address to send the test message to."),
) -> None:
    """Send a test email to verify SMTP and App Password settings."""
    container = get_container()
    console.print(f"Sending SMTP connection test email to [bold cyan]{email}[/bold cyan]...")
    try:
        success = container.outreach_service.send_test_email(email)
        if success:
            console.print("[bold green]✓ Test email sent successfully![/bold green] Please check your inbox.")
        else:
            console.print("[bold red]✗ Failed to send test email.[/bold red] Review the error details in the logs.")
            raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error configuring SMTP connection:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# 18. test-telegram
# ---------------------------------------------------------------------------


def test_telegram() -> None:
    """Send a test message to verify Telegram Bot API settings."""
    container = get_container()
    console.print("Sending Telegram test notification...")
    try:
        success = container.health_service.test_telegram()
        if success:
            console.print("[bold green]✓ Test notification sent successfully![/bold green] Please check your Telegram chat.")
        else:
            console.print("[bold red]✗ Failed to send test notification.[/bold red] Ensure that TELEGRAM_BOT_TOKEN is set in .env, telegram.enabled is true and telegram.chat_id is set in config.yaml, and verify your bot credentials.")
            raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error sending Telegram notification:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# 20. digest
# ---------------------------------------------------------------------------


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
    if not input.exists():
        console.print(
            f"[red]Error: Input file '{input}' not found.[/red]\n"
            "What to do next: Run 'hiring-radar discover' and 'hiring-radar scrape' to collect data first."
        )
        raise typer.Exit(code=1)

    container = get_container()
    companies = container.company_repo.load_all()

    # Filter to last 24 hours
    window_start = datetime.now() - timedelta(hours=24)
    recent_companies = []
    for c in companies:
        c_time = c.discovered_at.replace(tzinfo=None) if c.discovered_at.tzinfo else c.discovered_at
        if c_time >= window_start:
            recent_companies.append(c)

    total_companies = len(recent_companies)
    total_jobs = sum(len(c.jobs) for c in recent_companies)

    ai_pattern = re.compile(r'\b(ai|ml|nlp|computer vision)\b|artificial intelligence|machine learning|deep learning', re.IGNORECASE)
    backend_pattern = re.compile(r'\b(backend|back-end|python|go|golang|rust|java|node|django|fastapi|c\+\+|c#|\.net|ruby|rails)\b', re.IGNORECASE)
    frontend_pattern = re.compile(r'\b(frontend|front-end|react|next\.js|nextjs|typescript|javascript|vue|angular|ui|ux|css|html)\b', re.IGNORECASE)

    ai_count = backend_count = frontend_count = other_count = 0
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

    top_picks = sorted(recent_companies, key=lambda c: len(c.jobs), reverse=True)[:5]
    top_picks_lines = [f"{idx}. {c.name} — {len(c.jobs)} new jobs" for idx, c in enumerate(top_picks, start=1)]
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

    if send:
        console.print("Posting daily hiring digest to Telegram...")
        from app.notify.telegram import send_telegram_message
        success = send_telegram_message(digest_text)
        if success:
            console.print("[bold green]✓ Daily digest posted successfully to Telegram![/bold green]")
        else:
            console.print("[bold red]✗ Failed to post daily digest to Telegram.[/bold red]")

    panel = Panel(
        digest_text,
        title="[bold magenta]Daily Hiring Digest[/bold magenta]",
        expand=False,
        border_style="cyan",
    )
    console.print()
    console.print(panel)
    console.print()


# ---------------------------------------------------------------------------
# 21. morning-brief
# ---------------------------------------------------------------------------


def morning_brief(
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = settings.output_dir / "companies.json",
) -> None:
    """Generate a daily cold outreach hiring digest and send it to Telegram."""
    curr_settings = resolve_symbol("settings", settings)
    curr_yaml_config = resolve_symbol("yaml_config", yaml_config)
    bot_token = curr_settings.telegram_bot_token
    chat_id = curr_yaml_config.telegram.chat_id
    enabled = curr_yaml_config.telegram.enabled

    if not bot_token or not chat_id or not enabled:
        console.print(
            "Telegram notifications are not fully configured or are disabled. "
            "Skipping morning brief execution."
        )
        raise typer.Exit(code=0)

    curr_outreach_digest = resolve_symbol("outreach_digest", outreach_digest)
    curr_outreach_digest(input=input, send=True)



# ---------------------------------------------------------------------------
# 22. report
# ---------------------------------------------------------------------------


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
    """Generate an end-of-day summary of user activity over a reporting window."""
    window_start = datetime.now() - timedelta(days=days)
    window_start_date = window_start.date()

    container = get_container()

    # 1. Gather stats from companies.json
    new_companies_count = 0
    new_jobs_count = 0
    emails_sent_count = 0

    if input.exists():
        try:
            # Custom company repo if path overridden
            company_repo = container.company_repo
            if input != company_repo.filepath:
                from app.repositories.company import CompanyRepository
                company_repo = CompanyRepository(input)

            companies = company_repo.load_all()
            for c in companies:
                if c.discovered_at:
                    c_time = c.discovered_at.replace(tzinfo=None) if c.discovered_at.tzinfo else c.discovered_at
                    if c_time >= window_start:
                        new_companies_count += 1
                        new_jobs_count += len(c.jobs)

                for note in c.notes:
                    if note.startswith("email_sent:"):
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
            # Custom application repo if path overridden
            app_repo = container.application_repo
            if apps_path != app_repo.filepath:
                from app.repositories.application import ApplicationRepository
                app_repo = ApplicationRepository(apps_path)

            apps = app_repo.load_all()
            for app_key, app_dict in apps.items():
                for hist_item in app_dict.status_history:
                    if hist_item.get("status") == "applied":
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

        # 3. Follow-ups still pending
        try:
            tracker_service = container.tracker_service
            if apps_path != container.application_repo.filepath:
                from app.repositories.application import ApplicationRepository
                from app.services.tracker import TrackerService
                tracker_service = TrackerService(ApplicationRepository(apps_path), container.company_repo)

            followups_list = tracker_service.get_followups(threshold_days=7)
            pending_followups_count = len(followups_list)
        except Exception:
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
            console.print("Posting activity report to Telegram...")
            from app.notify.telegram import send_telegram_message
            success = send_telegram_message(report_text)
            if success:
                console.print("[bold green]✓ Activity report posted successfully to Telegram![/bold green]")
            else:
                console.print("[bold red]✗ Failed to post activity report to Telegram.[/bold red]")

    panel = Panel(
        report_text,
        title="[bold magenta]Activity Report[/bold magenta]",
        expand=False,
        border_style="cyan",
    )
    console.print()
    console.print(panel)
    console.print()
