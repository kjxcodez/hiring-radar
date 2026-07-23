"""Event Translation Layer mapping workflow execution details into user-friendly updates."""

from __future__ import annotations

from typing import Any
from app.workflows.events import WorkflowStarted, StepStarted

# Workflow name mappings
WORKFLOW_TRANSLATIONS = {
    "discover": "Discovering current opportunities",
    "sync": "Synchronizing career database",
    "intelligence": "Researching company intelligence",
    "recommend_job": "Scoring candidate matches",
    "recommend_outreach": "Drafting personalized outreach",
    "monitoring": "Checking for new hiring updates",
}

# Step name mappings
STEP_TRANSLATIONS = {
    # Discovery / Sync
    "GreenhouseDiscover": "Fetching Greenhouse listings",
    "LeverDiscover": "Fetching Lever listings",
    "RemoteOKDiscover": "Fetching RemoteOK listings",
    "WWRDiscover": "Fetching WeWorkRemotely listings",
    "WorkableDiscover": "Fetching Workable listings",
    "BambooHRDiscover": "Fetching BambooHR listings",
    "AshbyDiscover": "Fetching Ashby listings",
    "DeduplicateSync": "Deduplicating duplicate jobs",
    "PersistCompanies": "Updating corporate registries",
    
    # Intelligence
    "EnrichIntelligence": "Analyzing firmographics and signals",
    "UpdateGraph": "Constructing Knowledge Graph nodes",
    
    # Recommendations
    "LoadCandidate": "Loading candidate resume",
    "ScoreResume": "Matching skills against role metrics",
    "RunRecommendationEngine": "Ranking matches and explaining scores",
    
    # CRM / Outreach
    "OutreachPrepare": "Drafting email and LinkedIn outreach",
    
    # Monitoring
    "RunMonitoring": "Running difference detection checklists",
}


def translate_event(event: Any) -> str | None:
    """Translate internal step/workflow lifecycle events to human-readable strings.

    Returns None if the event type does not map to a user-facing transition.
    """
    if isinstance(event, WorkflowStarted):
        wf_name = event.workflow_name
        translated = WORKFLOW_TRANSLATIONS.get(wf_name)
        if translated:
            return f"{translated}..."
        return f"Executing workflow '{wf_name}'..."
        
    elif isinstance(event, StepStarted):
        step_name = event.step_name
        translated = STEP_TRANSLATIONS.get(step_name)
        if translated:
            return f"{translated}..."
        return f"Running step {step_name}..."
        
    return None
