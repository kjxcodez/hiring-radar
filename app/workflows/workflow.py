"""Workflow base class and implementations of all pipelines."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.workflows.executor import WorkflowExecutor
from app.workflows.step import (
    DeduplicateStep,
    DiscoverStep,
    EnrichStep,
    LoadCompaniesStep,
    LoadResumeStep,
    OutreachEmailStep,
    OutreachSubjectStep,
    PersistCompaniesStep,
    RecommendStep,
    ResearchStep,
    ScrapeStep,
    ScoreResumeStep,
    TailorResumeStep,
    EnrichIntelligenceStep,
    UpdateGraphStep,
    LoadCandidateStep,
    RunRecommendationEngineStep,
    OutreachPrepareStep,
)

if TYPE_CHECKING:
    from app.workflows.context import WorkflowContext
    from app.workflows.step import WorkflowStep


class Workflow:
    """Orchestrates sequential steps to complete a multi-step operation."""
    name: str = "BaseWorkflow"
    description: str = "Base workflow description"
    steps: list[WorkflowStep] = []

    def run(self, context: WorkflowContext) -> Any:
        """Execute the workflow steps using the sequential executor."""
        executor = WorkflowExecutor()
        return executor.execute(self, context)


# ===========================================================================
# 1. Discover Workflow
# ===========================================================================

class DiscoverWorkflow(Workflow):
    """Workflow to query job boards, scrape pages, deduplicate, and persist."""
    name = "discover"
    description = "Discover new jobs from feeds, scrape career details, and persist."
    steps = [
        DiscoverStep(),
        ScrapeStep(),
        DeduplicateStep(),
        PersistCompaniesStep(),
    ]

    def run(self, context: WorkflowContext) -> Any:
        super().run(context)
        return context.metadata.get("companies", [])


# ===========================================================================
# 2. Enrichment Workflow
# ===========================================================================

class EnrichmentWorkflow(Workflow):
    """Workflow to load, enrich with AI summarizations, and persist."""
    name = "enrich"
    description = "Enrich target company profiles with LLM metadata."
    steps = [
        LoadCompaniesStep(),
        EnrichStep(),
        PersistCompaniesStep(),
    ]

    def run(self, context: WorkflowContext) -> Any:
        super().run(context)
        return context.metadata.get("companies", [])


# ===========================================================================
# 3. Research Workflow
# ===========================================================================

class ResearchWorkflow(Workflow):
    """Workflow to load, perform deeper Github/profile research, and persist."""
    name = "research"
    description = "Research target company domain signals and Github profiles."
    steps = [
        LoadCompaniesStep(),
        ResearchStep(),
        PersistCompaniesStep(),
    ]

    def run(self, context: WorkflowContext) -> Any:
        super().run(context)
        return context.metadata.get("researched_company")


# ===========================================================================
# 4. Resume Scoring & Tailoring Workflows
# ===========================================================================

class ResumeWorkflow(Workflow):
    """Workflow to load candidate resume, calculate matching scores, and persist notes."""
    name = "resume"
    description = "Evaluate company suitability and fit score against resume."
    steps = [
        LoadResumeStep(),
        ScoreResumeStep(),
        PersistCompaniesStep(),
    ]

    def run(self, context: WorkflowContext) -> Any:
        super().run(context)
        return context.metadata.get("score_results", {})


class ResumeTailorWorkflow(Workflow):
    """Workflow to load candidate resume, generate tailoring advice, and persist notes."""
    name = "resume_tailor"
    description = "Generate optimization advice to tailor resume for company."
    steps = [
        LoadResumeStep(),
        TailorResumeStep(),
        PersistCompaniesStep(),
    ]

    def run(self, context: WorkflowContext) -> Any:
        super().run(context)
        return context.metadata.get("tailor_results", {})


# ===========================================================================
# 5. Recommendation Workflow
# ===========================================================================

class RecommendationWorkflow(Workflow):
    """Workflow to load companies and rank recommendations."""
    name = "recommend"
    description = "Rank and retrieve top job application recommendations."
    steps = [
        LoadCompaniesStep(),
        RecommendStep(),
    ]

    def run(self, context: WorkflowContext) -> Any:
        super().run(context)
        return context.metadata.get("recommendations", [])


# ===========================================================================
# 6. Outreach Workflow
# ===========================================================================

class OutreachWorkflow(Workflow):
    """Workflow to load companies, generate subjects and emails, and persist."""
    name = "outreach"
    description = "Draft cold outreach subjects and personalized email variables."
    steps = [
        LoadCompaniesStep(),
        OutreachSubjectStep(),
        OutreachEmailStep(),
        PersistCompaniesStep(),
    ]

    def run(self, context: WorkflowContext) -> Any:
        super().run(context)
        return context.metadata.get("outreach_results", {})


# ===========================================================================
# 7. Intelligence Workflow
# ===========================================================================

class IntelligenceWorkflow(Workflow):
    """Workflow to enrich company profile properties and build the Knowledge Graph."""
    name = "intelligence"
    description = "Enrich companies with business and tech signals, and update Knowledge Graph."
    steps = [
        EnrichIntelligenceStep(),
        UpdateGraphStep(),
    ]

    def run(self, context: WorkflowContext) -> Any:
        super().run(context)
        return True


# ===========================================================================
# 8. AI Recommendation Workflow
# ===========================================================================

class AIRecommendationWorkflow(Workflow):
    """Workflow to load candidate profiles and run AI recommendation engine matching."""
    name = "recommend_job"
    description = "Load candidate, execute match engine, and save job recommendations."
    steps = [
        LoadCandidateStep(),
        RunRecommendationEngineStep(),
    ]

    def run(self, context: WorkflowContext) -> Any:
        super().run(context)
        return context.metadata.get("recommendations", [])


# ===========================================================================
# 9. Application Preparation Workflow
# ===========================================================================

class ApplicationPrepareWorkflow(Workflow):
    """Workflow to generate outreach copy and initialize application schedules."""
    name = "recommend_outreach"
    description = "Generate cold outreach materials and schedule CRM events."
    steps = [
        OutreachPrepareStep(),
    ]

    def run(self, context: WorkflowContext) -> Any:
        super().run(context)
        return True



