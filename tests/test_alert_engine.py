"""Unit tests for mapping change events to prioritized user alerts."""

from __future__ import annotations

from app.monitoring.events import SalaryChanged, RemotePolicyChanged
from app.monitoring.alerts import AlertEngine


def test_alert_engine_routing():
    ev1 = SalaryChanged(company_name="Stripe", previous_value="120k", current_value="140k")
    ev2 = RemotePolicyChanged(company_name="Google", previous_value="hybrid", current_value="remote")

    alerts = AlertEngine.generate_alerts([ev1, ev2])
    assert len(alerts) == 2
    assert alerts[0].company_name == "Stripe"
    assert alerts[0].severity == "High"
    assert "Salary increased" in alerts[0].title

    assert alerts[1].company_name == "Google"
    assert alerts[1].severity == "High"
    assert "Remote policy updated" in alerts[1].title
