"""CLI sub-package entrypoint.

This module re-exports all public APIs and symbols that are imported or
patched by the test suite, preserving backwards-compatibility and avoiding
breaking any test mock boundaries.
"""

from __future__ import annotations

import orjson
from pathlib import Path


# Re-export Typer apps
from app.cli.main import app, search_app

# Re-export console & container helpers
from app.cli.common import (
    console,
    get_container,
    resolve_resume_path,
    _container,
    reset_container,
    track_progress,
)

# Re-export settings & configuration
from app.config import settings, yaml_config

# Re-export discovery registry and seed loading
from app.discover import SOURCE_REGISTRY
from app.discover.seed import load_seed_slugs

# Re-export application loaders/persistence
from app.tracker.status import load_applications, save_applications, set_status

# Re-export internal helper
from app.cli.commands.discovery import _run_discovery

# Re-export command entrypoint functions for test imports
from app.cli.commands.discovery import discover, watch_loop
from app.cli.commands.data import scrape, enrich, export, status, examples
from app.cli.commands.outreach import (
    preview,
    outreach_send,
    test_smtp,
    test_telegram,
    outreach_digest,
    morning_brief,
    activity_report,
)
from app.cli.commands.tracker import note_cli, followups
from app.cli.commands.outreach_crm import apply_callback as apply_cli
from app.cli.commands.recommendation import recommend_cli
from app.cli.commands.monitoring import monitor_callback as monitor_cli
from app.cli.commands.enrichment import research_cli, score_company_cli, tailor_cli

from app.cli.commands.system import view_dashboard, mcp_serve, agent

# Export all symbols so 'from app.cli import *' works identically
__all__ = [
    "app",
    "search_app",
    "console",
    "get_container",
    "_container",
    "reset_container",
    "track_progress",
    "settings",
    "yaml_config",
    "orjson",
    "Path",
    "SOURCE_REGISTRY",
    "load_seed_slugs",
    "load_applications",
    "save_applications",
    "set_status",
    "_run_discovery",
    "discover",
    "watch_loop",
    "scrape",
    "enrich",
    "export",
    "status",
    "examples",
    "preview",
    "outreach_send",
    "test_smtp",
    "test_telegram",
    "outreach_digest",
    "morning_brief",
    "activity_report",
    "apply_cli",
    "note_cli",
    "followups",
    "recommend_cli",
    "monitor_cli",
    "research_cli",
    "score_company_cli",
    "tailor_cli",
    "view_dashboard",
    "mcp_serve",
    "agent",
]

