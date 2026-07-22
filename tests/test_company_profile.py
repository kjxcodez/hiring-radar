"""Unit tests for the Company Intelligence Profile models."""

from __future__ import annotations

from app.intelligence.profile import (
    BusinessProfile,
    CompanyIntelligence,
    EngineeringProfile,
    GitHubProfile,
    HiringProfile,
    SignalsProfile,
)


def test_intelligence_profile_instantiation():
    intel = CompanyIntelligence(
        business=BusinessProfile(
            industry="Software",
            category="Fintech",
            company_size="100-500",
            headquarters="San Francisco, CA",
            remote_policy="remote",
            founded_year=2015,
        ),
        engineering=EngineeringProfile(
            languages=["Python", "TypeScript"],
            frameworks=["React", "FastAPI"],
            cloud=["AWS"],
            databases=["PostgreSQL"],
        ),
        hiring=HiringProfile(
            hiring_velocity="growing",
            open_roles=15,
            departments=["Engineering", "Product"],
            seniority_distribution={"Senior": 0.4, "Mid-level": 0.6},
            geographic_distribution=["US", "EU"],
        ),
        github=GitHubProfile(
            organization="stripe",
            popular_repositories=["stripe-python"],
            stars=1200,
        ),
        signals=SignalsProfile(
            funding_stage="Series C",
            startup_maturity="late",
        ),
        cache_key="hash123",
    )

    assert intel.business.industry == "Software"
    assert "Python" in intel.engineering.languages
    assert intel.hiring.hiring_velocity == "growing"
    assert intel.github.organization == "stripe"
    assert intel.signals.funding_stage == "Series C"
    assert intel.cache_key == "hash123"
