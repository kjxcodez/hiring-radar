from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models import Company, JobPosting
from app.repositories.company import CompanyRepository
from app.storage import JsonStorage
from app.workflows.context import WorkflowContext
from app.workflows.engine import WorkflowEngine


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


@patch("app.workflows.step.SOURCE_REGISTRY", new={})
@patch("app.workflows.step.load_seed_slugs")
@patch("app.cli.load_seed_slugs", create=True)
def test_discover_workflow_execution(mock_cli_load, mock_load_seeds, temp_dir):
    # Setup mock seeds and source return
    mock_load_seeds.return_value = {"mock_source": ["slug1"]}
    mock_cli_load.return_value = {"mock_source": ["slug1"]}

    # Mock custom source discover function
    mock_company = Company(
        name="Test Workflow Co",
        website="https://testworkflow.com",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
        jobs=[
            JobPosting(
                job_title="Backend Developer",
                job_url="https://testworkflow.com/job1",
                location="Remote",
                remote_type="remote",
                source="mock_source",
            )
        ]
    )

    from app.workflows.step import SOURCE_REGISTRY
    SOURCE_REGISTRY["mock_source"] = lambda slugs: [mock_company]

    companies_path = temp_dir / "companies.json"
    storage = JsonStorage()
    company_repo = CompanyRepository(companies_path, storage=storage)

    mock_container = MagicMock()
    mock_container.company_repo = company_repo

    engine = WorkflowEngine(container=mock_container, settings=MagicMock())

    # Run discover workflow
    res = engine.run(
        "discover",
        sources="mock_source",
        limit=10,
        skip_scrape=True,
    )

    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0].name == "Test Workflow Co"

    # Verify persistent database write
    assert companies_path.exists()
    all_saved = company_repo.load_all()
    assert len(all_saved) == 1
    assert all_saved[0].name == "Test Workflow Co"
