"""Verification tests for the free-text note command on applications."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from app.models import Company
from app.cli import note_cli


class TestTrackerNotes(unittest.TestCase):
    @patch("app.cli.console")
    @patch("app.cli.save_applications")
    @patch("app.cli.load_applications")
    @patch("app.cli.orjson.loads")
    @patch("app.cli.Path.exists")
    @patch("app.cli.Path.read_bytes")
    def test_note_command_add_and_list(self, mock_read, mock_exists, mock_loads, mock_load_apps, mock_save_apps, mock_console):
        mock_exists.return_value = True
        
        # Mock company list database
        mock_loads.return_value = [
            {
                "name": "Note Company",
                "discovered_at": "2026-07-15T00:00:00",
                "last_updated": "2026-07-15T00:00:00",
                "notes": [],
                "jobs": []
            }
        ]

        # Mock initial loaded apps mapping
        mock_load_apps.return_value = {}

        # Run command with --add and --list together
        note_cli(
            company_name="note",
            add="Applied via LinkedIn",
            list_notes=True
        )

        # 1. Verify load_applications was called
        mock_load_apps.assert_called_once()

        # 2. Verify save_applications was called with the new timestamped note
        mock_save_apps.assert_called_once()
        saved_dict = mock_save_apps.call_args[0][0]
        app_record = saved_dict["note company"]
        self.assertEqual(len(app_record.notes), 1)
        self.assertIn("Applied via LinkedIn", app_record.notes[0])
        self.assertIn(date.today().isoformat(), app_record.notes[0])

        # 3. Verify Rich output console was printed
        calls = mock_console.print.call_args_list
        printed_notes = False
        for c in calls:
            if not c[0]:
                continue
            arg = c[0][0]
            if isinstance(arg, str) and "Applied via LinkedIn" in arg:
                printed_notes = True

        self.assertTrue(printed_notes)


if __name__ == "__main__":
    unittest.main()
