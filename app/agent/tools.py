"""AI Agent tools registry and thin wrapper functions for Hiring Radar."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable, Optional
from pydantic import BaseModel

from app.models import Company
from app.config import settings
from app.tracker.status import load_applications, save_applications

logger = logging.getLogger(__name__)

# Lazy-loaded container
_container = None

def get_container():
    global _container
    if _container is None:
        from app.services.config import ServiceContainer
        _container = ServiceContainer()
    return _container


def _find_company_by_name(name: str, input_path: Optional[Path] = None) -> tuple[Optional[Company], list[str]]:
    container = get_container()
    repo = container.company_repo
    if input_path:
        from app.repositories.company import CompanyRepository
        repo = CompanyRepository(input_path)
    companies = repo.load_all()
    matches = [c for c in companies if name.lower() in c.name.lower()]
    if len(matches) == 1:
        return matches[0], []
    suggestions = [
        c.name for c in companies
        if name.lower() in c.name.lower() or c.name.lower() in name.lower()
    ]
    if len(matches) > 1:
        return None, [m.name for m in matches]
    return None, suggestions


# Define AgentTool structure
class AgentTool(BaseModel):
    """Container for an AI agent tool specification and callable function."""

    name: str
    description: str
    parameters_schema: dict[str, Any]
    fn: Callable[..., Any]
    side_effecting: bool = False

    class Config:
        arbitrary_types_allowed = True


TOOL_REGISTRY: dict[str, AgentTool] = {}


# -- TOOL: search_jobs --
try:
    from mcp_server.server import search_jobs

    def _search_jobs_wrapper(sources: list[str], limit: int = 50) -> list[dict] | dict[str, str]:
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
    def _score_company_fit_wrapper(company_name: str, resume_path: Optional[str] = None) -> dict:
        try:
            container = get_container()
            res = container.resume_service.score_compatibility(
                company_name=company_name,
                resume_label=resume_path,
            )
            return {
                "overall_match_percent": res["overall_match_percent"],
                "skill_breakdown": res["skill_breakdown"],
                "missing_skills": res["missing_skills"],
            }
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
except Exception as err:
    logger.warning("Skipped registering tool 'score_company_fit': %s", err)


# -- TOOL: research_company --
try:
    def _research_company_wrapper(company_name: str) -> dict:
        try:
            container = get_container()
            co = container.research_service.research(company_name=company_name)
            return co.model_dump(mode="json")
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
except Exception as err:
    logger.warning("Skipped registering tool 'research_company': %s", err)


# -- TOOL: score_company_attractiveness --
try:
    def _score_company_attractiveness_wrapper(company_name: str) -> dict:
        try:
            container = get_container()
            from app.enrich.company_score import score_company_attractiveness
            companies = container.company_repo.load_all()
            matches = [c for c in companies if company_name.lower() in c.name.lower()]
            if not matches:
                return {"error": f"Company '{company_name}' not found."}
            if len(matches) > 1:
                return {"error": f"Multiple companies match '{company_name}': " + ", ".join(c.name for c in matches)}

            co = matches[0]
            updated_co = score_company_attractiveness(co)

            for idx, item in enumerate(companies):
                if item.dedupe_key() == co.dedupe_key():
                    companies[idx] = updated_co
                    break

            container.company_repo.save_all(companies)
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
except Exception as err:
    logger.warning("Skipped registering tool 'score_company_attractiveness': %s", err)


# -- TOOL: generate_email --
try:
    def _generate_email_wrapper(company_name: str, template_name: str = "startup") -> dict:
        try:
            container = get_container()
            res = container.outreach_service.generate_outreach_draft(
                company_name=company_name,
                template=template_name,
            )
            return {
                "subject": res["subject"],
                "body": res["body"],
                "template_used": res["template_used"],
            }
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
except Exception as err:
    logger.warning("Skipped registering tool 'generate_email': %s", err)


# -- TOOL: recommend --
try:
    def _recommend_wrapper(top: int = 5, resume: Optional[str] = None) -> list[dict] | dict[str, str]:
        try:
            container = get_container()
            recs = container.recommendation_service.get_recommendations(top=top, resume_label=resume)
            result_dicts = []
            for item in recs:
                co = item["company"]
                co_dict = co.model_dump(mode="json")
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
except Exception as err:
    logger.warning("Skipped registering tool 'recommend': %s", err)


# -- TOOL: apply_to_company --
try:
    def _apply_to_company_wrapper(
        company_name: str,
        status: str = "applied",
        resume_version: Optional[str] = None
    ) -> dict:
        try:
            co, suggestions = _find_company_by_name(company_name)
            if not co:
                if suggestions:
                    return {"error": f"Company '{company_name}' not found. Did you mean: {', '.join(suggestions)}?"}
                return {"error": f"Company '{company_name}' not found."}

            key = co.dedupe_key()
            container = get_container()
            apps_path = container.application_repo.filepath

            apps = load_applications(apps_path)
            if key not in apps:
                from app.models import Application
                app_record = Application(
                    company_key=key,
                    status="discovered",
                    status_history=[{"status": "discovered", "date": date.today().isoformat()}],
                )
                apps[key] = app_record
            else:
                app_record = apps[key]

            from app.tracker.status import set_status
            set_status(apps, key, status)

            if resume_version:
                app_record.resume_version = resume_version

            save_applications(apps, apps_path)
            return app_record.model_dump(mode="json")
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
        fn=_apply_to_company_wrapper,
        side_effecting=True
    )
except Exception as err:
    logger.warning("Skipped registering tool 'apply_to_company': %s", err)


# -- TOOL: remember_preference --
try:
    def _remember_preference_wrapper(key: str, value: str) -> dict:
        try:
            from app.agent.memory import load_memory, save_memory
            mem = load_memory()
            mem["preferences"][key] = value
            save_memory(mem)
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
except Exception as err:
    logger.warning("Skipped registering tool 'remember_preference': %s", err)


# -- TOOL: reject_company --
try:
    def _reject_company_wrapper(company_key: str, reason: str) -> dict:
        try:
            container = get_container()
            companies = container.company_repo.load_all()
            matches = [c for c in companies if company_key.lower() in c.name.lower()]
            if matches:
                resolved_key = matches[0].dedupe_key()
            else:
                resolved_key = company_key.strip().lower()

            from app.agent.memory import load_memory, save_memory
            mem = load_memory()
            if resolved_key not in mem["rejected_companies"]:
                mem["rejected_companies"].append(resolved_key)
            mem["past_decisions"].append({
                "date": date.today().isoformat(),
                "action": "reject",
                "company_key": resolved_key,
                "reason": reason
            })
            save_memory(mem)
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
except Exception as err:
    logger.warning("Skipped registering tool 'reject_company': %s", err)


# -- TOOL: list_applications --
try:
    def _list_applications_wrapper() -> list[dict]:
        try:
            container = get_container()
            apps_data = container.application_repo.load_all()
            apps = apps_data.values() if isinstance(apps_data, dict) else apps_data
            result = []
            for app in apps:
                # Handle dict or Pydantic record
                is_dict = isinstance(app, dict)
                
                co_name = "Unknown"
                co = app.get("company") if is_dict else getattr(app, "company", None)
                if co:
                    co_name = co.get("name", "Unknown") if isinstance(co, dict) else getattr(co, "name", "Unknown")
                else:
                    # Fallback to key or direct properties
                    co_name = app.get("company_key", "Unknown") if is_dict else getattr(app, "company_key", "Unknown")

                job_title = "Role"
                job = app.get("job") if is_dict else getattr(app, "job", None)
                if job:
                    job_title = job.get("job_title", "Role") if isinstance(job, dict) else getattr(job, "job_title", "Role")

                status = app.get("status") if is_dict else getattr(app, "status", "Unknown")
                next_followup = app.get("next_followup") if is_dict else getattr(app, "next_followup", None)
                
                result.append({
                    "company_name": co_name,
                    "job_title": job_title,
                    "status": status,
                    "next_followup": next_followup,
                })
            return result
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to load applications: {exc}"}

    TOOL_REGISTRY["list_applications"] = AgentTool(
        name="list_applications",
        description="Retrieve all tracked applications in the CRM tracking database along with status and next follow-up dates.",
        parameters_schema={"type": "object", "properties": {}},
        fn=_list_applications_wrapper
    )
except Exception as err:
    logger.warning("Skipped registering tool 'list_applications': %s", err)


# -- TOOL: list_alerts --
try:
    def _list_alerts_wrapper(limit: int = 20) -> list[dict]:
        try:
            container = get_container()
            alerts = container.monitoring_repo.load_alerts()
            result = []
            for alert in alerts[:limit]:
                if isinstance(alert, dict):
                    result.append(alert)
                else:
                    result.append(alert.model_dump(mode="json"))
            return result
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to load alerts: {exc}"}

    TOOL_REGISTRY["list_alerts"] = AgentTool(
        name="list_alerts",
        description="Retrieve active monitoring alerts and detected hiring update events.",
        parameters_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max alerts to fetch. Default: 20.",
                    "default": 20
                }
            }
        },
        fn=_list_alerts_wrapper
    )
except Exception as err:
    logger.warning("Skipped registering tool 'list_alerts': %s", err)


# -- TOOL: list_companies --
try:
    def _list_companies_wrapper(limit: int = 50) -> list[dict]:
        try:
            container = get_container()
            companies = container.company_repo.load_all()
            result = []
            for co in companies[:limit]:
                co_dict = co.model_dump(mode="json")
                co_dict.pop("ai_talking_points", None)
                co_dict.pop("research_notes", None)
                result.append(co_dict)
            return result
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to load companies: {exc}"}

    TOOL_REGISTRY["list_companies"] = AgentTool(
        name="list_companies",
        description="Retrieve recently discovered or researched companies and their open roles.",
        parameters_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max companies to fetch. Default: 50.",
                    "default": 50
                }
            }
        },
        fn=_list_companies_wrapper
    )
except Exception as err:
    logger.warning("Skipped registering tool 'list_companies': %s", err)




def execute_approved_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a side-effecting tool after explicit human approval."""
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool '{tool_name}' is not registered."}
    try:
        tool_impl = TOOL_REGISTRY[tool_name]
        return tool_impl.fn(**arguments)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Tool execution failed: {exc}"}


# Retrieve specs for OpenRouter/OpenAI tool-calling formatting
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
