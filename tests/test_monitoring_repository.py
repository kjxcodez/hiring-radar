"""Unit tests for the MonitoringRepository json files storage."""

from __future__ import annotations

from pathlib import Path
from app.storage import JsonStorage
from app.monitoring.events import JobCreated
from app.monitoring.alerts import Alert
from app.monitoring.repository import MonitoringRepository


def test_monitoring_repository_save_load_clear(tmp_path: Path):
    events_path = tmp_path / "events.json"
    alerts_path = tmp_path / "alerts.json"
    digest_path = tmp_path / "digest.json"

    repo = MonitoringRepository(events_path, alerts_path, digest_path, JsonStorage())

    # Starts empty
    assert repo.load_events() == []
    assert repo.load_alerts() == []
    assert repo.load_digest() == {}

    # Save
    ev = JobCreated(company_name="Stripe", job_url="http://1")
    al = Alert(title="Title", description="Desc", severity="Low", company_name="Stripe")
    dig = {"executive_summary": "Summary"}

    repo.save_events([ev])
    repo.save_alerts([al])
    repo.save_digest(dig)

    # Loads successfully
    assert len(repo.load_events()) == 1
    assert len(repo.load_alerts()) == 1
    assert repo.load_digest()["executive_summary"] == "Summary"

    # Clear
    repo.clear()
    assert repo.load_events() == []
    assert repo.load_alerts() == []
    assert repo.load_digest() == {}
