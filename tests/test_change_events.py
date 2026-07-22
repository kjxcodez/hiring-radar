"""Unit tests for ChangeEvent Pydantic models."""

from __future__ import annotations

from app.monitoring.events import JobCreated, SalaryChanged, ApplicationStatusChanged


def test_change_events_fields():
    ev1 = JobCreated(company_name="Stripe", job_url="http://stripe.com/1", current_value="Staff Engineer")
    assert ev1.event_type == "JobCreated"
    assert ev1.company_name == "Stripe"
    assert ev1.job_url == "http://stripe.com/1"
    assert ev1.current_value == "Staff Engineer"
    assert ev1.severity == "Medium"
    assert ev1.event_id is not None
    assert ev1.timestamp is not None

    ev2 = SalaryChanged(company_name="Stripe", previous_value="120k", current_value="140k")
    assert ev2.event_type == "SalaryChanged"
    assert ev2.severity == "High"
    assert ev2.previous_value == "120k"
    assert ev2.current_value == "140k"
