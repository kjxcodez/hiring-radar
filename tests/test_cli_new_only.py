"""Verification tests for the discover --new-only reporting flag."""

from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.models import Company, JobPosting
from app.cli import _run_discovery


class TestCliNewOnly(unittest.TestCase):
    def setUp(self):
        # We will mock the output directory to be a temp dir
        self.output_dir_patcher = patch("app.cli.settings")
        self.mock_settings = self.output_dir_patcher.start()
        self.temp_path = Path("output_test_new_only")
        self.mock_settings.output_dir = self.temp_path

        self.companies_file = self.temp_path / "companies.json"
        if self.companies_file.exists():
            self.companies_file.unlink()
        if self.temp_path.exists():
            self.temp_path.rmdir()

        self.temp_path.mkdir(exist_ok=True)

    def tearDown(self):
        if self.companies_file.exists():
            self.companies_file.unlink()
        if self.temp_path.exists():
            self.temp_path.rmdir()
        self.output_dir_patcher.stop()

    @patch("app.cli.console")
    @patch("app.cli.load_seed_slugs")
    @patch("app.cli.SOURCE_REGISTRY")
    def test_run_discovery_new_only(self, mock_registry, mock_load_seeds, mock_console):
        mock_load_seeds.return_value = {"greenhouse": ["some-slug"]}
        
        now_str = datetime.utcnow().isoformat()
        # Create an existing company on disk
        existing_co = Company(
            name="Existing Corp",
            domain="existing.com",
            discovered_at=now_str,
            last_updated=now_str,
            jobs=[
                JobPosting(
                    job_title="Software Engineer",
                    job_url="https://existing.com/job1",
                    location="Remote",
                    remote_type="remote",
                    source="greenhouse",
                )
            ]
        )
        self.companies_file.write_bytes(
            json.dumps([existing_co.model_dump(mode="json")]).encode("utf-8")
        )

        # Mock discovery returning one existing and one brand new company
        new_co = Company(
            name="Brand New Corp",
            domain="new.com",
            discovered_at=now_str,
            last_updated=now_str,
            jobs=[
                JobPosting(
                    job_title="ML Engineer",
                    job_url="https://new.com/job1",
                    location="USA",
                    remote_type="onsite",
                    source="greenhouse",
                )
            ]
        )

        # Re-emit existing_co as well (but maybe with an extra job or same)
        mock_registry.__contains__.return_value = True
        mock_registry.__getitem__.return_value = MagicMock(return_value=[existing_co, new_co])

        # Run with new_only = True
        summary = _run_discovery(
            sources="greenhouse",
            seed_file=None,
            limit=10,
            profile=None,
            remote=None,
            country=None,
            keyword=None,
            exclude=None,
            days=None,
            new_only=True
        )

        # Verify stats dictionary counts
        self.assertEqual(summary["new_companies_written"], 1)  # Only Brand New Corp
        self.assertEqual(summary["unchanged_companies_not_shown"], 1)  # Existing Corp
        self.assertEqual(summary["new_jobs"], 1)  # 1 job on Brand New Corp
        self.assertEqual(summary["total_companies_written"], 2)  # Both merged/persisted

        # Verify companies.json actually contains both
        data = json.loads(self.companies_file.read_bytes())
        self.assertEqual(len(data), 2)
        names = {c["name"] for c in data}
        self.assertIn("Existing Corp", names)
        self.assertIn("Brand New Corp", names)

    @patch("app.cli.console")
    @patch("app.cli.load_seed_slugs")
    @patch("app.cli.SOURCE_REGISTRY")
    def test_run_discovery_full_reporting(self, mock_registry, mock_load_seeds, mock_console):
        mock_load_seeds.return_value = {"greenhouse": ["some-slug"]}
        mock_registry.__contains__.return_value = True
        mock_registry.__getitem__.return_value = MagicMock(return_value=[])

        # Run with new_only = False
        summary = _run_discovery(
            sources="greenhouse",
            seed_file=None,
            limit=10,
            profile=None,
            remote=None,
            country=None,
            keyword=None,
            exclude=None,
            days=None,
            new_only=False
        )

        # Under full reporting, it reports standard stats
        self.assertEqual(summary["total_companies_written"], 0)
        self.assertEqual(summary["new_companies_written"], 0)
        self.assertEqual(summary["unchanged_companies_not_shown"], 0)


if __name__ == "__main__":
    unittest.main()
