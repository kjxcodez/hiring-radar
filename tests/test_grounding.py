"""Tests for Grounding Layer."""

from __future__ import annotations

from app.agent.grounding import format_grounding_context


def test_grounding_format() -> None:
    """Verify grounding formatting compiles into descriptive text."""
    app_data = [
        {"company_name": "Stripe", "job_title": "Backend", "status": "Applied", "next_followup": "2026-08-01"}
    ]
    
    ctx = format_grounding_context("list_applications", app_data)
    assert "Company: Stripe" in ctx
    assert "Status: Applied" in ctx
