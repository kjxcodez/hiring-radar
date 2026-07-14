"""Verification tests for deeper company research module."""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx

from app.models import Company, JobPosting
from app.utils import RateLimiter
from app.enrich.research import _extract_github_repos, research_company


class TestCompanyResearch(unittest.TestCase):
    def test_extract_github_repos_with_itemprop(self):
        # Mock HTML containing itemprop="name codeRepository"
        html = """
        <html>
          <body>
            <div>
              <a href="/org/repo1" itemprop="name codeRepository">repo1</a>
              <span itemprop="description">This is description 1</span>
            </div>
            <div>
              <a href="/org/repo2" itemprop="name codeRepository">repo2</a>
            </div>
          </body>
        </html>
        """
        repos = _extract_github_repos(html)
        self.assertEqual(len(repos), 2)
        self.assertEqual(repos[0], "- repo1: This is description 1")
        self.assertEqual(repos[1], "- repo2")

    def test_extract_github_repos_with_wb_break_all(self):
        # Mock HTML containing class="wb-break-all"
        html = """
        <html>
          <body>
            <div>
              <a href="/org/repo1" class="wb-break-all">repo1</a>
              <p class="color-fg-muted">This is org description 1</p>
            </div>
            <div>
              <a href="/org/repo2" class="wb-break-all">repo2</a>
            </div>
          </body>
        </html>
        """
        repos = _extract_github_repos(html)
        self.assertEqual(len(repos), 2)
        self.assertEqual(repos[0], "- repo1: This is org description 1")
        self.assertEqual(repos[1], "- repo2")

    @patch("app.enrich.research.settings")
    def test_research_company_dry_run(self, mock_settings):
        mock_settings.openrouter_api_key = "mock-key"
        mock_settings.openrouter_model = "mock-model"

        company = Company(
            name="Research Inc",
            discovered_at=datetime.now(),
            last_updated=datetime.now(),
            github_url="https://github.com/research-inc",
        )

        client = httpx.Client()
        rate_limiter = RateLimiter()

        # Mock the network page fetch to not do actual calls
        with patch("app.enrich.research._fetch_github_text") as mock_fetch:
            mock_fetch.return_value = "<html></html>"
            res = research_company(company, client, rate_limiter, dry_run=True)
            
            self.assertEqual(res.research_notes["products"], "—")
            self.assertEqual(res.research_notes["likely_customers"], "—")

    @patch("app.enrich.research._post_with_retry")
    @patch("app.enrich.research.settings")
    def test_research_company_success(self, mock_settings, mock_post):
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
                            '  "products": "Analytics Dashboard",\n'
                            '  "likely_customers": "Recruiters",\n'
                            '  "engineering_notes": "Python, React",\n'
                            '  "recent_signals": "Active growth"\n'
                            "}"
                        )
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        company = Company(
            name="Research Inc",
            discovered_at=datetime.now(),
            last_updated=datetime.now(),
            github_url="https://github.com/research-inc",
        )

        client = httpx.Client()
        rate_limiter = RateLimiter()

        with patch("app.enrich.research._fetch_github_text") as mock_fetch:
            mock_fetch.return_value = '<html><a href="/repo1" itemprop="name codeRepository">repo1</a></html>'
            res = research_company(company, client, rate_limiter, dry_run=False)

            self.assertEqual(res.research_notes["products"], "Analytics Dashboard")
            self.assertEqual(res.research_notes["likely_customers"], "Recruiters")
            self.assertEqual(res.research_notes["engineering_notes"], "Python, React")
            self.assertEqual(res.research_notes["recent_signals"], "Active growth")


if __name__ == "__main__":
    unittest.main()
