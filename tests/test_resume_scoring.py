"""Verification tests for resume parsing and scoring modules."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.models import Company, JobPosting
from app.resume.parser import load_resume_text
from app.resume.score import score_company


class TestResumeScoring(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path("output/test_scratch")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        # Clean up temporary test files
        for f in self.tmp_dir.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            self.tmp_dir.rmdir()
        except OSError:
            pass

    def test_load_resume_text_txt(self):
        txt_path = self.tmp_dir / "resume.txt"
        test_content = "This is a mock resume text."
        txt_path.write_text(test_content, encoding="utf-8")

        extracted = load_resume_text(txt_path)
        self.assertEqual(extracted, test_content)

    @patch("app.resume.parser.PdfReader")
    def test_load_resume_text_pdf(self, mock_pdf_reader):
        pdf_path = self.tmp_dir / "resume.pdf"
        pdf_path.write_bytes(b"dummy pdf bytes")

        # Mock pdf extractor pages
        mock_page_1 = MagicMock()
        mock_page_1.extract_text.return_value = "Page 1 Content"
        mock_page_2 = MagicMock()
        mock_page_2.extract_text.return_value = "Page 2 Content"

        mock_instance = MagicMock()
        mock_instance.pages = [mock_page_1, mock_page_2]
        mock_pdf_reader.return_value = mock_instance

        extracted = load_resume_text(pdf_path)
        self.assertEqual(extracted, "Page 1 Content\nPage 2 Content")

    def test_load_resume_text_unsupported(self):
        invalid_path = self.tmp_dir / "resume.docx"
        invalid_path.write_text("dummy", encoding="utf-8")

        with self.assertRaises(ValueError):
            load_resume_text(invalid_path)

    @patch("app.resume.score.settings")
    def test_score_company_dry_run(self, mock_settings):
        mock_settings.openrouter_api_key = "mock-key"
        mock_settings.openrouter_model = "mock-model"

        from datetime import datetime
        company = Company(
            name="AI Labs",
            website="https://ailabs.com",
            discovered_at=datetime.now(),
            last_updated=datetime.now(),
            jobs=[
                JobPosting(
                    job_title="ML Engineer",
                    job_url="https://jobs.com/1",
                    location="Remote",
                    remote_type="remote",
                    source="remoteok",
                    description="Looking for Python, PyTorch, LLMs expert.",
                )
            ],
        )

        res = score_company(company, "My Python and ML Resume", dry_run=True)
        self.assertEqual(res["overall_match_percent"], 0)
        self.assertEqual(res["skill_breakdown"], {})
        self.assertEqual(res["missing_skills"], [])

    @patch("app.resume.score.get_http_client")
    @patch("app.resume.score.settings")
    def test_score_company_success(self, mock_settings, mock_http_client):
        mock_settings.openrouter_api_key = "mock-key"
        mock_settings.openrouter_model = "mock-model"

        # Mock API JSON response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{\n"
                            '  "overall_match_percent": 85,\n'
                            '  "skill_breakdown": {"Python": 5, "PyTorch": 4},\n'
                            '  "missing_skills": ["LLMs"]\n'
                            "}"
                        )
                    }
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_http_client.return_value.__enter__.return_value = mock_client

        from datetime import datetime
        company = Company(
            name="AI Labs",
            website="https://ailabs.com",
            discovered_at=datetime.now(),
            last_updated=datetime.now(),
            jobs=[
                JobPosting(
                    job_title="ML Engineer",
                    job_url="https://jobs.com/1",
                    location="Remote",
                    remote_type="remote",
                    source="remoteok",
                    description="Looking for Python, PyTorch, LLMs expert.",
                )
            ],
        )

        res = score_company(company, "My Python and ML Resume", dry_run=False)
        self.assertEqual(res["overall_match_percent"], 85)
        self.assertEqual(res["skill_breakdown"], {"Python": 5, "PyTorch": 4})
        self.assertEqual(res["missing_skills"], ["LLMs"])


if __name__ == "__main__":
    unittest.main()
