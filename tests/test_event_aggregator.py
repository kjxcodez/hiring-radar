"""Unit tests for EventAggregator filtering and grouping."""

from __future__ import annotations

from app.monitoring.events import JobCreated
from app.monitoring.aggregator import EventAggregator


def test_event_aggregator_collapse():
    ev1 = JobCreated(company_name="Stripe", job_url="http://1", current_value="Staff", timestamp="2026-07-23T00:00:00")
    ev2 = JobCreated(company_name="Stripe", job_url="http://1", current_value="Principal", timestamp="2026-07-23T01:00:00")

    collapsed = EventAggregator.collapse_and_deduplicate([ev1, ev2])
    assert len(collapsed) == 1
    assert collapsed[0].current_value == "Principal"


def test_event_aggregator_grouping():
    ev1 = JobCreated(company_name="Stripe", job_url="http://1")
    ev2 = JobCreated(company_name="Google", job_url="http://2")

    grouped = EventAggregator.group_by_company([ev1, ev2])
    assert "Stripe" in grouped
    assert "Google" in grouped
    assert len(grouped["Stripe"]) == 1
