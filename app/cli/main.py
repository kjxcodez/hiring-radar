"""CLI Entrypoint Main module.

Responsible for bootstrap and sub-command routing registration.
"""

from __future__ import annotations

import typer

from app.utils import setup_logging


# ---------------------------------------------------------------------------
# Typer App Bootstrap
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="hiring-radar",
    help="Discover hiring companies and structure data for cold outreach.",
    add_completion=False,
    no_args_is_help=True,
)

search_app = typer.Typer(
    name="search",
    help="Manage and execute saved search configurations.",
    no_args_is_help=True,
)
app.add_typer(search_app, name="search")


@app.callback()
def _bootstrap() -> None:
    """Initialise logging before every command."""
    setup_logging()


# ---------------------------------------------------------------------------
# Command Registrations
# ---------------------------------------------------------------------------

# 1. Discover
from app.cli.commands.discovery import discover
app.command()(discover)

# 2. Scrape, 3. Enrich, 4. Export, 5. Status, 6. Examples
from app.cli.commands.data import scrape, enrich, export, status, examples
app.command()(scrape)
app.command()(enrich)
app.command()(export)
app.command()(status)
app.command()(examples)

# 7. Search (sub-commands)
from app.cli.commands.discovery import search_save, search_run, search_list
search_app.command(name="save")(search_save)
search_app.command(name="run")(search_run)
search_app.command(name="list")(search_list)

# 8. Preview, 16. Send, 17. Test SMTP, 18. Test Telegram, 20. Digest, 21. Morning Brief, 22. Report
from app.cli.commands.outreach import (
    preview,
    outreach_send,
    test_smtp,
    test_telegram,
    outreach_digest,
    morning_brief,
    activity_report,
)
app.command()(preview)
app.command(name="send")(outreach_send)
app.command(name="test-smtp")(test_smtp)
app.command(name="test-telegram")(test_telegram)
app.command(name="digest")(outreach_digest)
app.command(name="morning-brief")(morning_brief)
app.command(name="report")(activity_report)

from app.cli.commands.tracker import apply_cli, note_cli, followups
app.command(name="apply")(apply_cli)
app.command(name="note")(note_cli)
app.command(name="followups")(followups)

from app.cli.commands.recommendation import recommend_app, recommend_cli
app.add_typer(recommend_app, name="recommend")


# 9. Research, 10. Score-company, 11. Tailor
from app.cli.commands.enrichment import research_cli, score_company_cli, tailor_cli
app.command(name="research")(research_cli)
app.command(name="score-company")(score_company_cli)
app.command(name="tailor")(tailor_cli)

# 23. Dashboard, 24. Mcp-serve, 25. Agent
from app.cli.commands.system import view_dashboard, mcp_serve, agent
app.command(name="dashboard")(view_dashboard)
app.command(name="mcp-serve")(mcp_serve)
app.command(name="agent")(agent)

# 26. Background Jobs
jobs_app = typer.Typer(
    name="jobs",
    help="Monitor and manage background tasks and execution history.",
    no_args_is_help=True,
)
app.add_typer(jobs_app, name="jobs")

from app.cli.commands.jobs import jobs_list, jobs_history, jobs_cancel, jobs_retry
jobs_app.command(name="list")(jobs_list)
jobs_app.command(name="history")(jobs_history)
jobs_app.command(name="cancel")(jobs_cancel)
jobs_app.command(name="retry")(jobs_retry)

# 27. Sync Engine Command Group
from app.cli.commands.sync import sync_app
app.add_typer(sync_app, name="sync")

# 28. Company Intelligence Command Group
from app.cli.commands.intelligence import intelligence_app
app.add_typer(intelligence_app, name="intelligence")


