"""Tests for Query Analysis Layer."""

from __future__ import annotations

from app.agent.query_analysis import analyze_query_rule_based


def test_query_analysis_rule_based() -> None:
    """Verify local heuristic extraction of filter parameters from query text."""
    res = analyze_query_rule_based("Find remote backend jobs in Europe with Python")
    assert res is not None
    assert "backend" in res.job_titles
    assert "Europe" in res.locations
    assert res.remote_preferred is True
    assert "python" in res.technologies
