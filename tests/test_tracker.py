"""Verification tests for application tracker and state machine."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.models import Application
from app.tracker.status import load_applications, save_applications, set_status


class TestApplicationTracker(unittest.TestCase):
    def test_load_save_applications(self):
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "apps.json"

            # 1. Loading non-existent file returns empty dict
            apps = load_applications(tmp_path)
            self.assertEqual(apps, {})

            # 2. Add an application and save it
            app = Application(
                company_key="example.com",
                status="applied",
                status_history=[{"status": "applied", "date": "2026-07-15"}],
                applied_date=date(2026, 7, 15),
            )
            apps["example.com"] = app
            save_applications(apps, tmp_path)

            # 3. Reload it and verify fields
            loaded = load_applications(tmp_path)
            self.assertIn("example.com", loaded)
            self.assertEqual(loaded["example.com"].status, "applied")
            self.assertEqual(loaded["example.com"].applied_date, date(2026, 7, 15))

    def test_set_status_new_application(self):
        apps = {}
        # Transition from non-existent to "applied"
        app = set_status(apps, "newcompany.com", "applied")

        self.assertEqual(app.company_key, "newcompany.com")
        self.assertEqual(app.status, "applied")
        # History should contain "discovered" initialization and "applied" transition
        self.assertEqual(len(app.status_history), 2)
        self.assertEqual(app.status_history[0]["status"], "discovered")
        self.assertEqual(app.status_history[1]["status"], "applied")
        self.assertEqual(app.applied_date, date.today())
        self.assertEqual(app.last_contact_date, date.today())

    @patch("app.tracker.status.logger")
    def test_set_status_backwards_transition_warning(self, mock_logger):
        apps = {}
        # First transition to offer
        set_status(apps, "target.com", "offer")

        # Backwards transition to researched
        set_status(apps, "target.com", "researched")

        # Verify warning log was called
        mock_logger.warning.assert_called_once()
        self.assertIn("Backwards-nonsensical transition", mock_logger.warning.call_args[0][0])


