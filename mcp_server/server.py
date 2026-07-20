"""Model Context Protocol (MCP) server implementation for Hiring Radar.

Exposes key jobs search, company research, and application tracking capabilities
as JSON-RPC tools for LLM consumption.
"""

from __future__ import annotations

from typing import Optional, Any
import os
from pathlib import Path
import orjson
from mcp.server.fastmcp import FastMCP
from app.config import settings

# Initialize FastMCP server
app = FastMCP("Hiring Radar")

# Lazy-loaded container initialization
_container = None

def get_container():
    global _container
    if _container is None:
        from app.services.config import ServiceContainer
        _container = ServiceContainer()

    from unittest.mock import Mock
    if isinstance(settings, Mock):
        _container.settings = settings
        from app.repositories import CompanyRepository, ApplicationRepository, MemoryRepository
        _container.company_repo = CompanyRepository(settings.output_dir / "companies.json")
        _container.application_repo = ApplicationRepository(settings.output_dir / "applications.json")
        _container.memory_repo = MemoryRepository(settings.output_dir / "agent_memory.json")
        _container._discovery_service = None
        _container._scraping_service = None
        _container._research_service = None
        _container._resume_service = None
        _container._outreach_service = None
        _container._tracker_service = None
        _container._recommendation_service = None
        _container._dashboard_service = None
        _container._health_service = None

    return _container


# Expose search_jobs tool
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


# Expose get_company tool
@app.tool()
def get_company(name: str) -> dict | None:
    """Retrieve detailed information for a company by name using a case-insensitive substring search.

    Parameters:
    - name: The name of the company to find.

    Returns:
    - The company details dictionary, None if not found, or an error dictionary.
    """
    try:
        container = get_container()
        companies = container.company_repo.load_all()
        matches = [c for c in companies if name.lower() in c.name.lower()]
        if matches:
            return matches[0].model_dump(mode="json")
        return None
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Failed to retrieve company: {exc}"}


# Expose list_applications tool
@app.tool()
def list_applications() -> list[dict] | dict[str, str]:
    """List all tracked job applications and their current status.

    Returns:
    - A list of application status dictionaries, or an error dictionary.
    """
    try:
        container = get_container()
        apps = container.tracker_service.get_applications()
        return [app.model_dump(mode="json") for app in apps.values()]
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Failed to list applications: {exc}"}


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------

@app.resource("hiring-radar://companies", mime_type="application/json", description="The full list of companies and their scraped job postings.")
def get_companies_resource() -> list[dict]:
    """Read the full companies database file from disk."""
    companies_file = settings.output_dir / "companies.json"
    if not companies_file.exists():
        return []
    try:
        return orjson.loads(companies_file.read_bytes())
    except Exception:
        return []


@app.resource("hiring-radar://jobs", mime_type="application/json", description="A flattened list of all active job postings across all tracked companies.")
def get_jobs_resource() -> list[dict]:
    """Compile and flatten all job openings across all companies in the database."""
    companies_file = settings.output_dir / "companies.json"
    if not companies_file.exists():
        return []
    try:
        companies = orjson.loads(companies_file.read_bytes())
        flattened = []
        for c in companies:
            for j in c.get("jobs", []):
                j["company_name"] = c.get("name")
                flattened.append(j)
        return flattened
    except Exception:
        return []


@app.resource("hiring-radar://profiles", mime_type="application/json", description="List of search profile labels configured in the system.")
def get_profiles_resource() -> list[str]:
    """Get the stems of all available SearchProfile configurations."""
    try:
        from app.profiles import list_profiles
        return list_profiles()
    except Exception:
        return []


@app.resource("hiring-radar://templates", mime_type="application/json", description="List of outreach message templates available in the system.")
def get_templates_resource() -> list[str]:
    """Get the stems of all available cold email templates."""
    try:
        from app.outreach.templates import list_templates
        return list_templates()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# MCP Prompts
# ---------------------------------------------------------------------------

@app.prompt(description="Generate the cold outreach email prompt for a company.")
def cold_email(company_name: str, template: str = "startup") -> str:
    """Construct prompt text for generating a cold outreach email to a target company."""
    try:
        container = get_container()
        companies = container.company_repo.load_all()
        matches = [c for c in companies if company_name.lower() in c.name.lower()]
        if not matches:
            return f"Error: Company '{company_name}' not found in the database."
        co = matches[0]

        from app.outreach.email import build_email_system_prompt, build_email_prompt
        system = build_email_system_prompt()
        user = build_email_prompt(co)
        return f"--- SYSTEM PROMPT ---\n{system}\n\n--- USER PROMPT ---\n{user}\n\nTemplate requested: {template}"
    except Exception as exc:  # noqa: BLE001
        return f"Error building cold email prompt: {exc}"


@app.prompt(description="Generate the company research prompt to extract products, stack, and growth signals.")
def company_research(company_name: str) -> str:
    """Construct prompt text for performing deeper research on a target company."""
    try:
        container = get_container()
        companies = container.company_repo.load_all()
        matches = [c for c in companies if company_name.lower() in c.name.lower()]
        if not matches:
            return f"Error: Company '{company_name}' not found in the database."
        co = matches[0]

        from app.enrich.research import build_system_prompt, build_research_prompt
        system = build_system_prompt()
        user = build_research_prompt(co, [])
        return f"--- SYSTEM PROMPT ---\n{system}\n\n--- USER PROMPT ---\n{user}"
    except Exception as exc:  # noqa: BLE001
        return f"Error building company research prompt: {exc}"


@app.prompt(description="Generate the resume matching compatibility prompt for a company.")
def resume_match(company_name: str) -> str:
    """Construct prompt text for evaluating how well a candidate's resume fits a target company."""
    try:
        companies_file = settings.output_dir / "companies.json"
        if not companies_file.exists():
            return f"Error: Company database file not found at {companies_file}."
        
        raw = companies_file.read_bytes()
        companies_list = orjson.loads(raw)
        
        from app.models import Company
        companies = [Company.model_validate(c) for c in companies_list]
        matches = [c for c in companies if company_name.lower() in c.name.lower()]
        if not matches:
            return f"Error: Company '{company_name}' not found in the database."
        co = matches[0]

        resume_path = settings.resume_path
        if not resume_path:
            return "Error: No resume path configured. Please configure RESUME_PATH in settings or environment."
        
        from app.resume.parser import load_resume_text
        try:
            resume_text = load_resume_text(resume_path)
        except Exception as exc:  # noqa: BLE001
            return f"Error: Failed to load resume from {resume_path}: {exc}"

        from app.resume.score import build_system_prompt, build_scoring_prompt
        system = build_system_prompt()
        user = build_scoring_prompt(co, resume_text)
        return f"--- SYSTEM PROMPT ---\n{system}\n\n--- USER PROMPT ---\n{user}"
    except Exception as exc:  # noqa: BLE001
        return f"Error building resume match prompt: {exc}"


# Server entrypoint
def main() -> None:
    """Run the MCP server over stdio or HTTP/SSE transport based on environment variables."""
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    port_str = os.getenv("MCP_HTTP_PORT", "8811")
    host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")

    try:
        port = int(port_str)
    except ValueError:
        port = 8811

    if transport in ("http", "sse"):
        app.settings.host = host
        app.settings.port = port
        app.run(transport="sse")
    else:
        app.run(transport="stdio")


if __name__ == "__main__":
    main()
