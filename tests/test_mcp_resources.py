"""Verification tests for the MCP resources module."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from mcp_server.server import app


class TestMcpResources(unittest.TestCase):
    def test_resources_exposure(self):
        # Retrieve list of resources exposed on the FastMCP server instance
        resources = asyncio.run(app.list_resources())
        uris = [str(r.uri) for r in resources]

        self.assertIn("hiring-radar://companies", uris)
        self.assertIn("hiring-radar://jobs", uris)
        self.assertIn("hiring-radar://profiles", uris)
        self.assertIn("hiring-radar://templates", uris)

    @patch("mcp_server.server.settings")
    @patch("mcp_server.server.orjson.loads")
    @patch("mcp_server.server.Path.exists")
    @patch("mcp_server.server.Path.read_bytes")
    def test_companies_resource(self, mock_read, mock_exists, mock_loads, mock_settings):
        mock_exists.return_value = True
        mock_loads.return_value = [{"name": "Mock Company"}]

        from mcp_server.server import get_companies_resource
        res = get_companies_resource()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["name"], "Mock Company")

    @patch("mcp_server.server.settings")
    @patch("mcp_server.server.orjson.loads")
    @patch("mcp_server.server.Path.exists")
    @patch("mcp_server.server.Path.read_bytes")
    def test_jobs_resource(self, mock_read, mock_exists, mock_loads, mock_settings):
        mock_exists.return_value = True
        mock_loads.return_value = [
            {
                "name": "Mock Company",
                "jobs": [{"job_title": "Software Engineer"}]
            }
        ]

        from mcp_server.server import get_jobs_resource
        res = get_jobs_resource()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["job_title"], "Software Engineer")
        self.assertEqual(res[0]["company_name"], "Mock Company")

    @patch("app.profiles.list_profiles")
    def test_profiles_resource(self, mock_list):
        mock_list.return_value = ["ai", "remote"]

        from mcp_server.server import get_profiles_resource
        res = get_profiles_resource()
        self.assertEqual(res, ["ai", "remote"])

    @patch("app.outreach.templates.list_templates")
    def test_templates_resource(self, mock_list):
        mock_list.return_value = ["intro", "followup"]

        from mcp_server.server import get_templates_resource
        res = get_templates_resource()
        self.assertEqual(res, ["intro", "followup"])


if __name__ == "__main__":
    unittest.main()
