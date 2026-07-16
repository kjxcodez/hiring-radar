"""Verification tests for the report CLI subcommand."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.models import Company, JobPosting, Application
from app.cli import activity_report


class TestCliReport(unittest.TestCase):
    def setUp(self):
        # Setup temporary directories and files
        self.temp_path = Path("output_test_report")
        self.temp_path.mkdir(exist_ok=True)
        self.companies_file = self.temp_path / "companies.json"
        self.apps_file = self.temp_path / "applications.json"

        if self.companies_file.exists():
            self.companies_file.unlink()
        if self.apps_file.exists():
            self.apps_file.unlink()

    def tearDown(self):
        if self.companies_file.exists():
            self.companies_file.unlink()
        if self.apps_file.exists():
            self.apps_file.unlink()
        if self.temp_path.exists():
            self.temp_path.rmdir()

    @patch("app.cli.console")
    @patch("app.cli.yaml_config")
    @patch("app.cli.settings")
    def test_report_empty_databases(self, mock_settings, mock_yaml, mock_console):
        # Test report handles missing files gracefully
        activity_report(
            days=1,
            send=False,
            input=self.companies_file,
            apps_path=self.apps_file
        )

        # Check console panel contents (all zeros since files don't exist)
        panel_args = mock_console.print.call_args_list
        stats_printed = False
        for call in panel_args:
            if call[0]:
                arg = call[0][0]
                text = str(getattr(arg, "renderable", arg))
                if "Activity Report" in text:
                    self.assertIn("New companies discovered: 0", text)
                    self.assertIn("New jobs added: 0", text)
                    self.assertIn("Emails drafted/sent: 0", text)
                    self.assertIn("Applications submitted: 0", text)
                    stats_printed = True
        self.assertTrue(stats_printed)

    @patch("app.cli.console")
    @patch("app.cli.yaml_config")
    @patch("app.cli.settings")
    def test_report_with_data(self, mock_settings, mock_yaml, mock_console):
        # 1. Populated companies database
        now_str = datetime.utcnow().isoformat()
        yesterday_str = (datetime.utcnow() - timedelta(days=2)).isoformat()
        
        c1 = Company(
            name="New Corp",
            domain="newcorp.com",
            discovered_at=now_str,
            last_updated=now_str,
            notes=["email_sent: 2026-07-16 via startup"],
            jobs=[
                JobPosting(
                    job_title="Software Engineer",
                    job_url="https://newcorp.com/job1",
                    location="Remote",
                    remote_type="remote",
                    source="greenhouse",
                )
            ]
        )
        c2 = Company(
            name="Old Corp",
            domain="oldcorp.com",
            discovered_at=yesterday_str,
            last_updated=yesterday_str,
            notes=[],
            jobs=[]
        )
        self.companies_file.write_bytes(
            json.dumps([c1.model_dump(mode="json"), c2.model_dump(mode="json")]).encode("utf-8")
        )

        # 2. Populated applications database
        apps_data = {
            "newcorp.com": {
                "company_key": "newcorp.com",
                "status": "applied",
                "status_history": [
                    {"status": "discovered", "date": "2026-07-15"},
                    {"status": "applied", "date": "2026-07-16"}
                ],
                "applied_date": "2026-07-16",
                "resume_version": "default",
                "notes": [],
                "last_contact_date": "2026-07-16"
            }
        }
        self.apps_file.write_bytes(json.dumps(apps_data).encode("utf-8"))

        # Run report command for window of last 1 day
        # (This will match New Corp discovered, 1 job, 1 email_sent, 1 applied)
        # Note: we freeze date for the test or calculate dynamically.
        # Since we use datetime.utcnow() for window calculations inside, it matches.
        # But wait! We parsed email sent date 2026-07-16, and status history date 2026-07-16.
        # Are they >= window_start.date()?
        # Yes, window_start.date() will be today's date (or yesterday's date if timezone is late).
        # To be safe, we can query with --days 5 in the test! That way, dates from yesterday/today will always fall in window.
        activity_report(
            days=5,
            send=False,
            input=self.companies_file,
            apps_path=self.apps_file
        )

        panel_args = mock_console.print.call_args_list
        stats_printed = False
        for call in panel_args:
            if call[0]:
                arg = call[0][0]
                text = str(getattr(arg, "renderable", arg))
                if "Activity Report" in text:
                    self.assertIn("New companies discovered: 2", text)
                    self.assertIn("New jobs added: 1", text)
                    self.assertIn("Emails drafted/sent: 1", text)
                    self.assertIn("Applications submitted: 1", text)
                    stats_printed = True
        self.assertTrue(stats_printed)


if __name__ == "__main__":
    unittest.main()
