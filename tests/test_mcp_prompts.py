"""Verification tests for the MCP prompts module."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from mcp_server.server import app


class TestMcpPrompts(unittest.TestCase):
    def test_prompts_exposure(self):
        # Retrieve list of prompts exposed on the FastMCP server instance
        prompts = asyncio.run(app.list_prompts())
        prompt_names = [p.name for p in prompts]

        self.assertIn("cold_email", prompt_names)
        self.assertIn("company_research", prompt_names)
        self.assertIn("resume_match", prompt_names)

    @patch("mcp_server.server.settings")
    @patch("mcp_server.server.orjson.loads")
    @patch("mcp_server.server.Path.exists")
    @patch("mcp_server.server.Path.read_bytes")
    @patch("app.outreach.email.build_email_prompt")
    @patch("app.outreach.email.build_email_system_prompt")
    def test_cold_email_prompt(
        self, mock_sys, mock_user, mock_read, mock_exists, mock_loads, mock_settings
    ):
        mock_exists.return_value = True
        mock_loads.return_value = [{
            "name": "Startup Corp",
            "discovered_at": "2026-07-15T00:00:00",
            "last_updated": "2026-07-15T00:00:00",
            "notes": [],
            "jobs": []
        }]
        mock_sys.return_value = "System Instructions"
        mock_user.return_value = "User Details"

        from mcp_server.server import cold_email
        res = cold_email("startup", template="startup")
        self.assertIn("System Instructions", res)
        self.assertIn("User Details", res)

    @patch("mcp_server.server.settings")
    @patch("mcp_server.server.orjson.loads")
    @patch("mcp_server.server.Path.exists")
    @patch("mcp_server.server.Path.read_bytes")
    @patch("app.enrich.research.build_research_prompt")
    @patch("app.enrich.research.build_system_prompt")
    def test_company_research_prompt(
        self, mock_sys, mock_user, mock_read, mock_exists, mock_loads, mock_settings
    ):
        mock_exists.return_value = True
        mock_loads.return_value = [{
            "name": "Research Corp",
            "discovered_at": "2026-07-15T00:00:00",
            "last_updated": "2026-07-15T00:00:00",
            "notes": [],
            "jobs": []
        }]
        mock_sys.return_value = "Research System"
        mock_user.return_value = "Research User"

        from mcp_server.server import company_research
        res = company_research("research")
        self.assertIn("Research System", res)
        self.assertIn("Research User", res)

    @patch("mcp_server.server.settings")
    @patch("mcp_server.server.orjson.loads")
    @patch("mcp_server.server.Path.exists")
    @patch("mcp_server.server.Path.read_bytes")
    @patch("app.resume.parser.load_resume_text")
    @patch("app.resume.score.build_scoring_prompt")
    @patch("app.resume.score.build_system_prompt")
    def test_resume_match_prompt(
        self, mock_sys, mock_user, mock_resume, mock_read, mock_exists, mock_loads, mock_settings
    ):
        mock_exists.return_value = True
        mock_loads.return_value = [{
            "name": "Resume Corp",
            "discovered_at": "2026-07-15T00:00:00",
            "last_updated": "2026-07-15T00:00:00",
            "notes": [],
            "jobs": []
        }]
        mock_resume.return_value = "Resume content"
        mock_sys.return_value = "Score System"
        mock_user.return_value = "Score User"

        from mcp_server.server import resume_match
        res = resume_match("resume")
        self.assertIn("Score System", res)
        self.assertIn("Score User", res)


if __name__ == "__main__":
    unittest.main()
