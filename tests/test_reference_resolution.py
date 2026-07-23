"""Tests for Contextual Reference Resolver."""

from __future__ import annotations

from app.agent.session import AgentSession
from app.agent.reference_resolver import resolve_references


def test_reference_resolution_indices() -> None:
    """Verify indices and pronoun phrases map to previous session entities."""
    session = AgentSession()
    session.last_recommendations = [
        {"name": "Stripe", "job_title": "Backend engineer"},
        {"name": "Wealthfront", "job_title": "Frontend developer"},
    ]
    
    q_resolved, entities = resolve_references("Show more like the second one", session)
    assert entities.get("company_name") == "Wealthfront"
    assert "Wealthfront" in q_resolved


def test_reference_resolution_pronouns() -> None:
    """Verify general pronoun references fall back to discussed companies."""
    session = AgentSession()
    session.discussed_companies = ["Stripe", "Google"]
    
    q_resolved, entities = resolve_references("tell me about that one", session)
    assert entities.get("company_name") == "Google"
    assert "Google" in q_resolved
