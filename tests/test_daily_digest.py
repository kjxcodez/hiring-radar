"""Unit tests for daily AI digest generation."""

from __future__ import annotations

from unittest.mock import MagicMock
from app.monitoring.events import JobCreated
from app.monitoring.digest import DigestGenerator


def test_digest_generator_mock_ai():
    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = (
        "{"
        '  "executive_summary": "Summary text.",'
        '  "top_opportunities": ["Stripe Dev"],'
        '  "biggest_hiring_trends": ["React expansion"],'
        '  "new_remote_roles": ["Remote engineer"],'
        '  "recommendation_improvements": [],'
        '  "companies_to_prioritize": ["Stripe"],'
        '  "suggested_actions": ["Apply soon"]'
        "}"
    )

    ev = JobCreated(company_name="Stripe", job_url="http://1", current_value="Dev")
    digest = DigestGenerator.generate([ev], mock_gateway)

    assert digest["executive_summary"] == "Summary text."
    assert "Stripe Dev" in digest["top_opportunities"]
    assert "React expansion" in digest["biggest_hiring_trends"]
