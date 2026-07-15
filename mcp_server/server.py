"""Model Context Protocol (MCP) server implementation for Hiring Radar.

Exposes key jobs search, company research, and application tracking capabilities
as JSON-RPC tools for LLM consumption.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import orjson
from mcp.server.fastmcp import FastMCP

from app.config import settings


# 1. Initialize FastMCP server
app = FastMCP("Hiring Radar")


# 2. Expose search_jobs tool
@app.tool()
def search_jobs(sources: list[str], limit: int = 50) -> list[dict] | dict[str, str]:
    """Search for open jobs from various sources.

    Parameters:
    - sources: A list of job board sources to search. Valid values: greenhouse, lever, remoteok, wwr, ashby, workable, bamboohr.
    - limit: The maximum number of jobs to return. Default: 50.

    Returns:
    - A list of matching company/job posting dictionaries, or an error dictionary.
    """
    try:
        from app.discover import SOURCE_REGISTRY
        from app.discover import remoteok as _remoteok_mod
        from app.discover import wwr as _wwr_mod
        from app.discover.seed import load_seed_slugs

        # Validate sources
        unknown = [s for s in sources if s not in SOURCE_REGISTRY and s not in ("remoteok", "wwr")]
        if unknown:
            return {"error": f"Unknown source(s): {', '.join(unknown)}"}

        all_new = []
        for src in sources:
            if src == "remoteok":
                discovered = _remoteok_mod.discover(limit=limit)
            elif src == "wwr":
                discovered = _wwr_mod.discover(limit=limit)
            else:
                seed_map = load_seed_slugs([src])
                slugs = seed_map.get(src, [])
                if not slugs:
                    continue
                discovered = SOURCE_REGISTRY[src](slugs)
            all_new.extend(discovered)

        # Truncate to limit and return JSON dicts
        return [c.model_dump(mode="json") for c in all_new[:limit]]
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Search failed: {exc}"}


# 3. Expose get_company tool
@app.tool()
def get_company(name: str) -> dict | None:
    """Retrieve detailed information for a company by name using a case-insensitive substring search.

    Parameters:
    - name: The name of the company to find.

    Returns:
    - The company details dictionary, None if not found, or an error dictionary.
    """
    try:
        from app.models import Company
        companies_file = settings.output_dir / "companies.json"
        if not companies_file.exists():
            return None

        all_companies = [
            Company.model_validate(c)
            for c in orjson.loads(companies_file.read_bytes())
        ]

        matches = [c for c in all_companies if name.lower() in c.name.lower()]
        if matches:
            return matches[0].model_dump(mode="json")
        return None
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Failed to retrieve company: {exc}"}


# 4. Expose list_applications tool
@app.tool()
def list_applications() -> list[dict] | dict[str, str]:
    """List all tracked job applications and their current status.

    Returns:
    - A list of application status dictionaries, or an error dictionary.
    """
    try:
        from app.tracker.status import load_applications
        apps_path = settings.output_dir / "applications.json"
        apps = load_applications(apps_path)
        return [app.model_dump(mode="json") for app in apps.values()]
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Failed to list applications: {exc}"}


# 5. Server entrypoint
def main() -> None:
    """Run the MCP server over stdio transport."""
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
