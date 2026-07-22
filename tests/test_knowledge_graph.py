"""Unit tests for the Knowledge Graph index manager."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models import Company, JobPosting
from app.storage import JsonStorage
from app.intelligence.profile import (
    BusinessProfile,
    CompanyIntelligence,
    EngineeringProfile,
    GitHubProfile,
    HiringProfile,
    SignalsProfile,
)
from app.intelligence.graph import KnowledgeGraph


def _make_company_with_intel() -> Company:
    co = Company(
        name="Stripe",
        domain="stripe.com",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    intel = CompanyIntelligence(
        business=BusinessProfile(industry="Payments"),
        engineering=EngineeringProfile(languages=["Python", "Go"]),
        hiring=HiringProfile(geographic_distribution=["US", "EU"], departments=["Engineering"]),
        github=GitHubProfile(organization="stripe"),
    )
    co.intelligence = intel
    return co


def test_knowledge_graph_rebuild_and_lifecycle(tmp_path: Path):
    co = _make_company_with_intel()
    graph = KnowledgeGraph()
    graph.rebuild_graph([co])

    assert "company_stripe.com" in graph.nodes
    assert "tech_python" in graph.nodes
    assert "tech_go" in graph.nodes
    assert "loc_us" in graph.nodes

    # Check edges
    assert len(graph.edges) == 6

    edges_sources = {e.source for e in graph.edges}
    assert "company_stripe.com" in edges_sources

    # Test Save & Load
    graph_file = tmp_path / "knowledge_graph.json"
    storage = JsonStorage()
    graph.save(graph_file, storage)

    loaded_graph = KnowledgeGraph()
    loaded_graph.load(graph_file, storage)

    assert "company_stripe.com" in loaded_graph.nodes
    assert len(loaded_graph.edges) == len(graph.edges)
