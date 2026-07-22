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


@patch("app.resume.score.settings")
@patch("app.resume.score.get_http_client")
def test_resume_workflow_scoring(mock_get_client, mock_settings, temp_dir):
    mock_settings.openrouter_api_key = "mock-key"

    # Mock LLM score response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "{\n"
                        '  "overall_match_percent": 90,\n'
                        '  "skill_breakdown": {"Python": 5},\n'
                        '  "missing_skills": []\n'
                        "}"
                    )
                }
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_get_client.return_value.__enter__.return_value = mock_client

    # Write dummy resume
    resume_file = temp_dir / "my_resume.txt"
    resume_file.write_text("Experienced Python full stack developer.")

    companies_path = temp_dir / "companies.json"
    storage = JsonStorage()
    company_repo = CompanyRepository(companies_path, storage=storage)

    company = Company(
        name="Target Corp",
        website="https://target.com",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
        jobs=[
            JobPosting(
                job_title="Python Engineer",
                job_url="https://target.com/job1",
                source="wwr",
            )
        ]
    )
    company_repo.save_all([company])

    mock_resume_service = MagicMock()
    mock_resume_service.resolve_version_path.return_value = resume_file
    mock_resume_service.parse_resume.return_value = "Experienced Python full stack developer."

    mock_container = MagicMock()
    mock_container.company_repo = company_repo
    mock_container.resume_service = mock_resume_service

    engine = WorkflowEngine(container=mock_container, settings=mock_settings)

    # Run resume scoring workflow
    res = engine.run(
        "resume",
        company_name="Target Corp",
        resume_label="my_resume.txt",
        dry_run=False,
    )

    assert isinstance(res, dict)
    assert res["overall_match_percent"] == 90
    assert res["skill_breakdown"] == {"Python": 5}
