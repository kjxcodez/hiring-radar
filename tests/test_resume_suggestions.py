"""Verification tests for resume tailoring suggestions module."""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.models import Company
from app.resume.suggestions import suggest_resume_tailoring


class TestResumeSuggestions(unittest.TestCase):
    @patch("app.resume.suggestions.settings")
    def test_suggest_resume_tailoring_dry_run(self, mock_settings):
        mock_settings.openrouter_api_key = "mock-key"
        mock_settings.openrouter_model = "mock-model"

        company = Company(
            name="Tailor Inc",
            discovered_at=datetime.now(),
            last_updated=datetime.now(),
        )

        res = suggest_resume_tailoring(company, "My Resume Text", dry_run=True)
        self.assertEqual(res["missing_keywords"], [])
        self.assertEqual(res["projects_to_emphasize"], [])
        self.assertEqual(res["summary_suggestion"], "—")

    @patch("app.resume.suggestions._post_with_retry")
    @patch("app.resume.suggestions.settings")
    def test_suggest_resume_tailoring_success(self, mock_settings, mock_post):
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
                            '  "missing_keywords": ["FastAPI", "Docker"],\n'
                            '  "projects_to_emphasize": ["Highlight the chat application project"],\n'
                            '  "summary_suggestion": "Experienced developer focused on FastAPI integrations.",\n'
                            '  "reorder_suggestion": "Move Docker to the top of skills list."\n'
                            "}"
                        )
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        company = Company(
            name="Tailor Inc",
            discovered_at=datetime.now(),
            last_updated=datetime.now(),
        )

        res = suggest_resume_tailoring(company, "My Resume Text", dry_run=False)
        self.assertEqual(res["missing_keywords"], ["FastAPI", "Docker"])
        self.assertEqual(res["projects_to_emphasize"], ["Highlight the chat application project"])
        self.assertEqual(res["summary_suggestion"], "Experienced developer focused on FastAPI integrations.")
        self.assertEqual(res["reorder_suggestion"], "Move Docker to the top of skills list.")


if __name__ == "__main__":
    unittest.main()
