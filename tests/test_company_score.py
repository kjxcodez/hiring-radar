"""Verification tests for company attractiveness scoring module."""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.models import Company
from app.enrich.company_score import score_company_attractiveness


class TestCompanyAttractivenessScore(unittest.TestCase):
    @patch("app.enrich.company_score.settings")
    def test_score_company_attractiveness_dry_run(self, mock_settings):
        mock_settings.openrouter_api_key = "mock-key"
        mock_settings.openrouter_model = "mock-model"

        company = Company(
            name="Test Target",
            discovered_at=datetime.now(),
            last_updated=datetime.now(),
        )

        res = score_company_attractiveness(company, dry_run=True)
        self.assertEqual(res.company_scores, {})
        self.assertIsNone(res.company_score_overall)

    @patch("app.enrich.company_score._post_with_retry")
    @patch("app.enrich.company_score.settings")
    def test_score_company_attractiveness_success(self, mock_settings, mock_post):
        mock_settings.openrouter_api_key = "mock-key"
        mock_settings.openrouter_model = "mock-model"

        # Mock API response payload
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{\n"
                            '  "growth": 8,\n'
                            '  "engineering_culture": 9,\n'
                            '  "remote_friendliness": 10,\n'
                            '  "open_source_presence": 5,\n'
                            '  "hiring_urgency": 7,\n'
                            '  "overall": 8.5,\n'
                            '  "rationale": "High quality engineering culture with great remote support."\n'
                            "}"
                        )
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        company = Company(
            name="Test Target",
            discovered_at=datetime.now(),
            last_updated=datetime.now(),
        )

        res = score_company_attractiveness(company, dry_run=False)
        self.assertEqual(res.company_scores["growth"], 8)
        self.assertEqual(res.company_scores["engineering_culture"], 9)
        self.assertEqual(res.company_scores["remote_friendliness"], 10)
        self.assertEqual(res.company_scores["open_source_presence"], 5)
        self.assertEqual(res.company_scores["hiring_urgency"], 7)
        self.assertEqual(res.company_score_overall, 8.5)
        self.assertIn("score_rationale: High quality engineering culture with great remote support.", res.notes)


if __name__ == "__main__":
    unittest.main()
