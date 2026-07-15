"""Verification tests for the standalone AI agent tools registry."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from datetime import date

from app.models import Company, Application
from app.agent.tools import TOOL_REGISTRY, get_tool_specs


class TestAgentTools(unittest.TestCase):
    def test_tool_registry_specs(self):
        specs = get_tool_specs()
        names = [s["function"]["name"] for s in specs]

        self.assertIn("search_jobs", names)
        self.assertIn("get_company", names)
        self.assertIn("score_company_fit", names)
        self.assertIn("research_company", names)
        self.assertIn("score_company_attractiveness", names)
        self.assertIn("generate_email", names)
        self.assertIn("recommend", names)
        self.assertIn("apply_to_company", names)

    @patch("app.agent.tools.settings")
    @patch("app.agent.tools.load_applications")
    @patch("app.agent.tools.save_applications")
    @patch("app.agent.tools._find_company_by_name")
    def test_apply_to_company_tool(self, mock_find, mock_save, mock_load, mock_settings):
        # Mock company lookup
        mock_co = MagicMock(spec=Company)
        mock_co.dedupe_key.return_value = "target corp"
        mock_find.return_value = (mock_co, [])

        # Mock application load/save
        app_record = Application(company_key="target corp", status="discovered")
        mock_load.return_value = {"target corp": app_record}

        # Invoke
        apply_fn = TOOL_REGISTRY["apply_to_company"].fn
        res = apply_fn("Target", status="applied")

        self.assertEqual(res["status"], "applied")
        mock_save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
