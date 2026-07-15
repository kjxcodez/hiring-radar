"""AI Agent tools registry and thin wrapper functions for Hiring Radar."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional

import orjson
from pydantic import BaseModel

from app.config import settings
from app.models import Company


logger = logging.getLogger(__name__)


# 1. Define AgentTool structure
class AgentTool(BaseModel):
    """Container for an AI agent tool specification and callable function."""

    name: str
    description: str
    parameters_schema: dict[str, Any]
    fn: Callable[..., Any]

    class Config:
        arbitrary_types_allowed = True


TOOL_REGISTRY: dict[str, AgentTool] = {}


# Helper for fuzzy matching a company by name
def _find_company_by_name(name: str, companies_file: Path) -> tuple[Company, list[Company]]:
    if not companies_file.exists():
        raise FileNotFoundError(f"Companies database file '{companies_file}' not found.")

    all_companies = [
        Company.model_validate(c)
        for c in orjson.loads(companies_file.read_bytes())
    ]

    matches = [c for c in all_companies if name.lower() in c.name.lower()]
    if not matches:
        raise ValueError(f"Company matching '{name}' not found in the database.")

    return matches[0], all_companies


# 2. Register tools with try/except guards

# -- TOOL: search_jobs --
try:
    from mcp_server.server import search_jobs

    def _search_jobs_wrapper(sources: list[str], limit: int = 50) -> list[dict] | dict[str, str]:
        # search_jobs is already protected and returns serializable data
        jobs = search_jobs(sources, limit)
        if isinstance(jobs, dict) and "error" in jobs:
            return jobs

        from app.agent.memory import load_memory
        mem = load_memory()
        rejected = set(mem.get("rejected_companies", []))
        if not rejected:
            return jobs

        filtered = []
        for co_dict in jobs:
            try:
                co_obj = Company.model_validate(co_dict)
                if co_obj.dedupe_key() in rejected:
                    continue
            except Exception:  # noqa: BLE001
                pass
            filtered.append(co_dict)
        return filtered

    TOOL_REGISTRY["search_jobs"] = AgentTool(
        name="search_jobs",
        description=(
            "Search for open job openings from online platforms/ATS interfaces. "
            "Supported sources: greenhouse, lever, remoteok, wwr, ashby, workable, bamboohr."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of sources to search."
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of jobs to return. Default: 50.",
                    "default": 50
                }
            },
            "required": ["sources"]
        },
        fn=_search_jobs_wrapper
    )
except ImportError as err:
    logger.warning("Skipped registering tool 'search_jobs': %s", err)


# -- TOOL: get_company --
try:
    from mcp_server.server import get_company

    def _get_company_wrapper(name: str) -> dict | None | dict[str, str]:
        # get_company is already protected and returns serializable data
        return get_company(name)

    TOOL_REGISTRY["get_company"] = AgentTool(
        name="get_company",
        description="Retrieve detailed profile information for a company by name using a case-insensitive substring match.",
        parameters_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the company to find."
                }
            },
            "required": ["name"]
        },
        fn=_get_company_wrapper
    )
except ImportError as err:
    logger.warning("Skipped registering tool 'get_company': %s", err)


# -- TOOL: score_company_fit --
try:
    from app.resume.parser import load_resume_text
    from app.resume.score import score_company
    from app.cli import resolve_resume_path

    def _score_company_fit_wrapper(company_name: str, resume_path: Optional[str] = None) -> dict:
        try:
            companies_file = settings.output_dir / "companies.json"
            co, _ = _find_company_by_name(company_name, companies_file)

            # Resolve resume path
            try:
                resume_p = resolve_resume_path(resume_path)
            except Exception as e:
                return {"error": f"Failed to resolve resume path: {e}"}

            if not resume_p or not resume_p.exists():
                return {"error": f"Resume path '{resume_p}' does not exist."}

            resume_text = load_resume_text(resume_p)
            result = score_company(co, resume_text)
            return result
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to score company fit: {exc}"}

    TOOL_REGISTRY["score_company_fit"] = AgentTool(
        name="score_company_fit",
        description="Evaluate a candidate's resume compatibility against a target company's job postings and profile.",
        parameters_schema={
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Name of the company to evaluate."
                },
                "resume_path": {
                    "type": "string",
                    "description": "Optional custom path or label override for the resume file variant."
                }
            },
            "required": ["company_name"]
        },
        fn=_score_company_fit_wrapper
    )
except ImportError as err:
    logger.warning("Skipped registering tool 'score_company_fit': %s", err)


# -- TOOL: research_company --
try:
    import httpx
    from app.enrich.research import research_company
    from app.utils import RateLimiter

    def _research_company_wrapper(company_name: str) -> dict:
        try:
            companies_file = settings.output_dir / "companies.json"
            co, all_companies = _find_company_by_name(company_name, companies_file)

            rate_limiter = RateLimiter(requests_per_minute=settings.openrouter_rpm)
            with httpx.Client() as client:
                updated_co = research_company(co, client, rate_limiter)

            # Save updated company list
            for idx, item in enumerate(all_companies):
                if item.dedupe_key() == co.dedupe_key():
                    all_companies[idx] = updated_co
                    break

            companies_file.write_bytes(
                orjson.dumps(
                    [c.model_dump(mode="json") for c in all_companies],
                    option=orjson.OPT_INDENT_2
                )
            )

            return updated_co.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to research company: {exc}"}

    TOOL_REGISTRY["research_company"] = AgentTool(
        name="research_company",
        description="Perform deep company corporate research extracting product lists, customers, stack details, and growth signals.",
        parameters_schema={
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Name of the company to research."
                }
            },
            "required": ["company_name"]
        },
        fn=_research_company_wrapper
    )
except ImportError as err:
    logger.warning("Skipped registering tool 'research_company': %s", err)


# -- TOOL: score_company_attractiveness --
try:
    from app.enrich.company_score import score_company_attractiveness

    def _score_company_attractiveness_wrapper(company_name: str) -> dict:
        try:
            companies_file = settings.output_dir / "companies.json"
            co, all_companies = _find_company_by_name(company_name, companies_file)

            updated_co = score_company_attractiveness(co)

            # Save updated company list
            for idx, item in enumerate(all_companies):
                if item.dedupe_key() == co.dedupe_key():
                    all_companies[idx] = updated_co
                    break

            companies_file.write_bytes(
                orjson.dumps(
                    [c.model_dump(mode="json") for c in all_companies],
                    option=orjson.OPT_INDENT_2
                )
            )

            return updated_co.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to score company attractiveness: {exc}"}

    TOOL_REGISTRY["score_company_attractiveness"] = AgentTool(
        name="score_company_attractiveness",
        description="Evaluate and rate a company's general quality and attractiveness as an employer across multiple axes.",
        parameters_schema={
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Name of the company to score."
                }
            },
            "required": ["company_name"]
        },
        fn=_score_company_attractiveness_wrapper
    )
except ImportError as err:
    logger.warning("Skipped registering tool 'score_company_attractiveness': %s", err)


# -- TOOL: generate_email --
try:
    import httpx
    from app.outreach.email import generate_email
    from app.utils import RateLimiter

    def _generate_email_wrapper(company_name: str, template_name: str = "startup") -> dict:
        try:
            companies_file = settings.output_dir / "companies.json"
            co, all_companies = _find_company_by_name(company_name, companies_file)

            rate_limiter = RateLimiter(requests_per_minute=settings.openrouter_rpm)
            with httpx.Client() as client:
                res = generate_email(
                    company=co,
                    client=client,
                    rate_limiter=rate_limiter,
                    template_name=template_name,
                )

            # Save updated company list since generate_email writes to co.notes
            for idx, item in enumerate(all_companies):
                if item.dedupe_key() == co.dedupe_key():
                    all_companies[idx] = co
                    break

            companies_file.write_bytes(
                orjson.dumps(
                    [c.model_dump(mode="json") for c in all_companies],
                    option=orjson.OPT_INDENT_2
                )
            )

            return res
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to generate email: {exc}"}

    TOOL_REGISTRY["generate_email"] = AgentTool(
        name="generate_email",
        description="Generate highly personalized, professional cold outreach email variables tailored for a target company.",
        parameters_schema={
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Name of the company."
                },
                "template_name": {
                    "type": "string",
                    "description": "Markdown body template variant label to use. Default: startup.",
                    "default": "startup"
                }
            },
            "required": ["company_name"]
        },
        fn=_generate_email_wrapper
    )
except ImportError as err:
    logger.warning("Skipped registering tool 'generate_email': %s", err)


# -- TOOL: recommend --
try:
    from app.resume.parser import load_resume_text
    from app.cli import resolve_resume_path

    def _recommend_wrapper(top: int = 5, resume: Optional[str] = None) -> list[dict] | dict[str, str]:
        try:
            companies_file = settings.output_dir / "companies.json"
            if not companies_file.exists():
                return {"error": "Companies database does not exist. Run discovery first."}

            all_companies = [
                Company.model_validate(c)
                for c in orjson.loads(companies_file.read_bytes())
            ]

            # Filter out contacted
            from app.agent.memory import load_memory
            mem = load_memory()
            rejected = set(mem.get("rejected_companies", []))

            uncontacted = [
                c for c in all_companies
                if not any(n.startswith("email_sent:") for n in c.notes)
                and c.dedupe_key() not in rejected
            ]

            # Load resume fit if available
            resume_text = None
            resume_p = resolve_resume_path(resume)
            if resume_p and resume_p.exists():
                resume_text = load_resume_text(resume_p)

            def get_recency(co: Company) -> datetime:
                dates = [
                    datetime.combine(j.posted_date, datetime.min.time())
                    for j in co.jobs if j.posted_date
                ]
                if dates:
                    return max(dates)
                return co.discovered_at or datetime.min

            def calculate_heuristic_fit(co: Company, r_text: str) -> int:
                r_words = set(re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", r_text.lower()))
                if not r_words:
                    return 0
                co_text = (
                    (co.description or "")
                    + " "
                    + " ".join(j.job_title + " " + (j.description or "") for j in co.jobs)
                )
                co_words = set(re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", co_text.lower()))
                return len(r_words.intersection(co_words))

            scored_list = []
            unscored_list = []

            for co in uncontacted:
                is_scored = co.company_score_overall is not None
                recency = get_recency(co)
                fit_score = 0
                if resume_text:
                    fit_score = calculate_heuristic_fit(co, resume_text)

                item = {
                    "company": co,
                    "is_scored": is_scored,
                    "overall": co.company_score_overall,
                    "recency": recency,
                    "fit_score": fit_score,
                }
                if is_scored:
                    scored_list.append(item)
                else:
                    unscored_list.append(item)

            # Sort primarily by overall, then recency
            scored_list.sort(key=lambda x: (x["overall"], x["recency"]), reverse=True)
            unscored_list.sort(key=lambda x: x["recency"], reverse=True)

            ranked_items = scored_list + unscored_list
            top_items = ranked_items[:top]

            result_dicts = []
            for item in top_items:
                co_dict = item["company"].model_dump(mode="json")
                co_dict["_recommendation_meta"] = {
                    "overall_score": item["overall"],
                    "fit_score": item["fit_score"],
                    "recency": item["recency"].isoformat(),
                    "is_scored": item["is_scored"]
                }
                result_dicts.append(co_dict)

            return result_dicts
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to compute recommendations: {exc}"}

    TOOL_REGISTRY["recommend"] = AgentTool(
        name="recommend",
        description="Recommend the best companies to apply to, ranked by desirability and keyword resume compatibility.",
        parameters_schema={
            "type": "object",
            "properties": {
                "top": {
                    "type": "integer",
                    "description": "Number of top recommended companies to return. Default: 5.",
                    "default": 5
                },
                "resume": {
                    "type": "string",
                    "description": "Optional resume version label or path to evaluate keyword overlap."
                }
            }
        },
        fn=_recommend_wrapper
    )
except ImportError as err:
    logger.warning("Skipped registering tool 'recommend': %s", err)


# -- TOOL: apply_to_company --
try:
    from app.tracker.status import load_applications, save_applications, set_status
    from app.resume.versions import resolve_resume_version

    def _apply_to_company_wrapper(
        company_name: str,
        status: str = "applied",
        resume_version: Optional[str] = None
    ) -> dict:
        try:
            companies_file = settings.output_dir / "companies.json"
            co, _ = _find_company_by_name(company_name, companies_file)

            # Validate resume version if provided
            if resume_version:
                try:
                    resolve_resume_version(resume_version)
                except Exception as e:
                    return {"error": f"Invalid resume version: {e}"}

            apps_path = settings.output_dir / "applications.json"
            apps = load_applications(apps_path)

            key = co.dedupe_key()
            set_status(apps, key, status)

            # If moving to applied, set additional fields
            if status == "applied":
                apps[key].resume_version = resume_version
                if not apps[key].applied_date:
                    apps[key].applied_date = date.today()

            save_applications(apps, apps_path)

            return apps[key].model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to apply status: {exc}"}

    TOOL_REGISTRY["apply_to_company"] = AgentTool(
        name="apply_to_company",
        description="Track and update application workflow status (discovered, researched, applied, interviewing, rejected, offer) for a target company.",
        parameters_schema={
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Name of the target company."
                },
                "status": {
                    "type": "string",
                    "description": "Allowed values: discovered, researched, applied, interviewing, rejected, offer. Default: applied.",
                    "default": "applied"
                },
                "resume_version": {
                    "type": "string",
                    "description": "Optional resume version label used for this application (e.g. 'ai', 'backend')."
                }
            },
            "required": ["company_name"]
        },
        fn=_apply_to_company_wrapper
    )
except ImportError as err:
    logger.warning("Skipped registering tool 'apply_to_company': %s", err)


# -- TOOL: remember_preference --
try:
    from app.agent.memory import remember_preference

    def _remember_preference_wrapper(key: str, value: str) -> dict:
        try:
            remember_preference(key, value)
            return {"status": "success", "key": key, "value": value}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    TOOL_REGISTRY["remember_preference"] = AgentTool(
        name="remember_preference",
        description="Store or update a persistent user preference mapping (e.g. key='work_mode', value='Remote only').",
        parameters_schema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Category key for the preference."
                },
                "value": {
                    "type": "string",
                    "description": "Description/value of the preference."
                }
            },
            "required": ["key", "value"]
        },
        fn=_remember_preference_wrapper
    )
except ImportError as err:
    logger.warning("Skipped registering tool 'remember_preference': %s", err)


# -- TOOL: reject_company --
try:
    from app.agent.memory import reject_company

    def _reject_company_wrapper(company_key: str, reason: str) -> dict:
        try:
            companies_file = settings.output_dir / "companies.json"
            try:
                co, _ = _find_company_by_name(company_key, companies_file)
                resolved_key = co.dedupe_key()
            except Exception:  # noqa: BLE001
                resolved_key = company_key.strip().lower()

            reject_company(resolved_key, reason)
            return {"status": "success", "rejected_company_key": resolved_key}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    TOOL_REGISTRY["reject_company"] = AgentTool(
        name="reject_company",
        description="Reject a company to exclude it from all future job search and recommendation results.",
        parameters_schema={
            "type": "object",
            "properties": {
                "company_key": {
                    "type": "string",
                    "description": "Name or dedupe key of the company to reject."
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for rejecting the company."
                }
            },
            "required": ["company_key", "reason"]
        },
        fn=_reject_company_wrapper
    )
except ImportError as err:
    logger.warning("Skipped registering tool 'reject_company': %s", err)


# 3. Retrieve specs for OpenRouter/OpenAI tool-calling formatting
def get_tool_specs() -> list[dict[str, Any]]:
    """Return tool specifications in OpenAI/OpenRouter tools formatting."""
    specs = []
    for tool in TOOL_REGISTRY.values():
        specs.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters_schema,
            }
        })
    return specs
