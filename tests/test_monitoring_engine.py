"""Unit tests for the complete MonitoringEngine change detection flow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models import Company, JobPosting
from app.repositories import CompanyRepository
from app.services.config import ServiceContainer
from app.storage import JsonStorage
from app.monitoring.engine import MonitoringEngine


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


def test_monitoring_engine_full_flow(temp_dir):
    # Setup mock gateway for AI digest summarization
    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = (
        "{"
        '  "executive_summary": "Daily updates.",'
        '  "top_opportunities": [],'
        '  "biggest_hiring_trends": [],'
        '  "new_remote_roles": [],'
        '  "recommendation_improvements": [],'
        '  "companies_to_prioritize": [],'
        '  "suggested_actions": ["Review alerts"]'
        "}"
    )

    container = ServiceContainer()
    container.ai_gateway = mock_gateway
    container.settings.output_dir = temp_dir
    container.company_repo = CompanyRepository(temp_dir / "companies.json", storage=JsonStorage())

    # Build engine
    engine = MonitoringEngine(container)

    # 1. First run - saves initial baseline snapshot (no events)
    co = Company(
        name="Stripe",
        domain="stripe.com",
        description="Payments",
        jobs=[
            JobPosting(
                job_title="Developer",
                job_url="https://stripe.com/1",
                source="greenhouse",
            )
        ],
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    container.company_repo.save_all([co])

    events_first = engine.run_monitoring()
    assert len(events_first) == 0  # Initial baseline registers state and returns empty
    assert engine.companies_snap_path.exists()

    co_changed = Company(
        name="Stripe",
        domain="stripe.com",
        description="Payments",
        jobs=[
            JobPosting(
                job_title="Developer",
                job_url="https://stripe.com/1",
                remote_type="remote",
                source="greenhouse",
            )
        ],
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    container.company_repo.save_all([co_changed])

    events_second = engine.run_monitoring()
    assert len(events_second) == 1
    assert events_second[0].event_type == "RemotePolicyChanged"
    assert events_second[0].company_name == "Stripe"

    # Verify repository files created
    assert container.monitoring_repo.events_path.exists()
    assert container.monitoring_repo.alerts_path.exists()
    assert container.monitoring_repo.digest_path.exists()

    # Alert should exist
    alerts = container.monitoring_repo.load_alerts()
    assert len(alerts) == 1
    assert "Remote policy updated at Stripe" in alerts[0]["title"]
