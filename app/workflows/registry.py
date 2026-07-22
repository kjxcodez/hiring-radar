"""Registry for resolving workflow classes by alias name."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.workflows.workflow import (
    DiscoverWorkflow,
    EnrichmentWorkflow,
    OutreachWorkflow,
    RecommendationWorkflow,
    ResearchWorkflow,
    ResumeTailorWorkflow,
    ResumeWorkflow,
    IntelligenceWorkflow,
    AIRecommendationWorkflow,
    ApplicationPrepareWorkflow,
    MonitoringWorkflow,
)

if TYPE_CHECKING:
    from app.workflows.workflow import Workflow


_WORKFLOW_MAP: dict[str, type[Workflow]] = {
    "discover": DiscoverWorkflow,
    "enrich": EnrichmentWorkflow,
    "research": ResearchWorkflow,
    "resume": ResumeWorkflow,
    "resume_tailor": ResumeTailorWorkflow,
    "recommend": RecommendationWorkflow,
    "outreach": OutreachWorkflow,
    "intelligence": IntelligenceWorkflow,
    "recommend_job": AIRecommendationWorkflow,
    "recommend_outreach": ApplicationPrepareWorkflow,
    "monitoring": MonitoringWorkflow,
}


def get_workflow_class(name: str) -> type[Workflow]:
    """Retrieve the Workflow class registered for the given alias name."""
    if name not in _WORKFLOW_MAP:
        raise KeyError(f"Workflow '{name}' is not registered in the workflow registry.")
    return _WORKFLOW_MAP[name]


def list_registered_workflows() -> list[str]:
    """Return a list of all registered workflow aliases."""
    return list(_WORKFLOW_MAP.keys())
