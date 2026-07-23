"""Verification tests for recommend CLI command and sorting/logic logic."""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.models import Company, JobPosting
from app.cli import recommend_cli


class TestRecommend(unittest.TestCase):
    @patch("app.cli.console")
    @patch("app.cli.orjson.loads")
    @patch("app.cli.Path.exists")
    @patch("app.cli.Path.read_bytes")
    def test_recommend_ranking_logic_no_resume(self, mock_read, mock_exists, mock_loads, mock_console):
        mock_exists.return_value = True
        
        # Two scored companies, one unscored company, one contacted company
        mock_loads.return_value = [
            {
                "name": "Scored Good",
                "company_score_overall": 8.5,
                "discovered_at": "2026-07-14T00:00:00",
                "last_updated": "2026-07-14T00:00:00",
                "notes": [],
                "jobs": [
                    {"job_title": "Senior React Developer", "job_url": "http://example.com", "source": "greenhouse", "posted_date": "2026-07-14"}
                ]
            },
            {
                "name": "Scored Awesome",
                "company_score_overall": 9.2,
                "discovered_at": "2026-07-14T00:00:00",
                "last_updated": "2026-07-14T00:00:00",
                "notes": ["score_rationale: Superb tech stack"],
                "jobs": [
                    {"job_title": "Principal Architect", "job_url": "http://example.com", "source": "greenhouse", "posted_date": "2026-07-14"}
                ]
            },
            {
                "name": "Unscored New",
                "company_score_overall": None,
                "discovered_at": "2026-07-14T00:00:00",
                "last_updated": "2026-07-14T00:00:00",
                "notes": [],
                "jobs": []
            },
            {
                "name": "Contacted Company",
                "company_score_overall": 9.9,
                "discovered_at": "2026-07-14T00:00:00",
                "last_updated": "2026-07-14T00:00:00",
                "notes": ["email_sent: 2026-07-14 via startup"],
                "jobs": []
            }
        ]

        # Call with no resume path
        recommend_cli(None, top=3, resume=None)

        # Retrieve the rendered Table from console.print
        calls = mock_console.print.call_args_list
        # Verify a table was printed
        table_printed = False
        hint_printed = False
        for c in calls:
            if not c[0]:
                continue
            arg = c[0][0]
            if hasattr(arg, "title") and arg.title == "Top Company Recommendations":
                table_printed = True
                # Check rows length
                self.assertEqual(len(arg.columns[0]._cells), 3)
                # First row should be Rank 1: Scored Awesome (Score: 9.20)
                self.assertEqual(arg.columns[1]._cells[0], "Scored Awesome")
                self.assertEqual(arg.columns[2]._cells[0], "9.20")
                self.assertEqual(arg.columns[3]._cells[0], "Principal Architect")
                self.assertEqual(arg.columns[4]._cells[0], "Superb tech stack")

                # Second row should be Rank 2: Scored Good (Score: 8.50)
                self.assertEqual(arg.columns[1]._cells[1], "Scored Good")
                self.assertEqual(arg.columns[2]._cells[1], "8.50")
                
                # Third row should be Rank 3: Unscored New (Score: unscored)
                self.assertEqual(arg.columns[1]._cells[2], "Unscored New")
                self.assertEqual(arg.columns[2]._cells[2], "unscored")

            if isinstance(arg, str) and "companies unscored" in arg:
                hint_printed = True
        
        self.assertTrue(table_printed)
        self.assertTrue(hint_printed)


if __name__ == "__main__":
    unittest.main()
