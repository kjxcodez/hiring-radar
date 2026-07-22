from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models import Company, JobPosting
from app.repositories.company import CompanyRepository
from app.storage import JsonStorage
from app.workflows.engine import WorkflowEngine


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


@patch("app.outreach.email.yaml_config")
@patch("app.outreach.email.settings")
@patch("app.cli.common.get_container")
def test_outreach_workflow_generation(mock_get_container, mock_settings, mock_yaml, temp_dir):
    mock_settings.openrouter_api_key = "mock-key"
    mock_settings.openrouter_model = "mock-model"
    mock_yaml.email.from_name = "Kapil Kumar Jangid"

    # Write dummy template
    template_dir = temp_dir / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    template_file = template_dir / "startup.md"
    template_file.write_text("Hello {{recipient_name}}, {{hook}} {{sender_pitch}} {{cta}} Regards {{sender_name}}")

    companies_path = temp_dir / "companies.json"
    storage = JsonStorage()
    company_repo = CompanyRepository(companies_path, storage=storage)

    company = Company(
        name="Outreach Target",
        website="https://outreach.com",
        recruiter_email="hiring@outreach.com",
        recruiter_name="Alice Recruiter",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
        jobs=[
            JobPosting(
                job_title="Software Developer",
                job_url="https://outreach.com/job1",
                source="lever",
            )
        ]
    )
    company_repo.save_all([company])

    # Mock the AI Gateway
    mock_ai_gateway = MagicMock()
    # Mock complete_json for generate_subject_lines
    mock_ai_gateway.complete_json.return_value = ["Subject 1", "Subject 2"]
    # Mock complete for creative variables _post_with_retry call
    mock_ai_gateway.complete.return_value = (
        '{\n  "hook": "Tailored hook",\n  "sender_pitch": "Experienced engineer",\n  "cta": "Quick call"\n}'
    )

    mock_container = MagicMock()
    mock_container.company_repo = company_repo
    mock_container.ai_gateway = mock_ai_gateway
    mock_get_container.return_value = mock_container

    engine = WorkflowEngine(container=mock_container, settings=mock_settings, ai_gateway=mock_ai_gateway)

    # Patch template loading directory to temp template dir
    with patch("app.outreach.templates.Path", return_value=template_dir):
        res = engine.run(
            "outreach",
            company_name="Outreach Target",
            template="startup",
            dry_run=False,
        )

    assert isinstance(res, dict)
    assert res["recipient"] == "hiring@outreach.com"
    assert res["subject"] == "Subject 1"
    assert "Tailored hook" in res["body"]
    assert "Alice Recruiter" in res["body"]
