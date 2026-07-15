"""Verification tests for the MCP server module."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from mcp_server.server import app


class TestMcpServer(unittest.TestCase):
    def test_tools_exposure(self):
        # Retrieve list of tools exposed on the FastMCP server instance
        tools = asyncio.run(app.list_tools())
        tool_names = [t.name for t in tools]

        self.assertIn("search_jobs", tool_names)
        self.assertIn("get_company", tool_names)
        self.assertIn("list_applications", tool_names)

    @patch("mcp_server.server.settings")
    @patch("app.tracker.status.load_applications")
    def test_list_applications_tool(self, mock_load, mock_settings):
        # Mock load_applications output
        mock_app = MagicMock()
        mock_app.model_dump.return_value = {"company_key": "test.com", "status": "applied"}
        mock_load.return_value = {"test.com": mock_app}

        # Invoke tool function
        from mcp_server.server import list_applications
        result = list_applications()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["company_key"], "test.com")
        self.assertEqual(result[0]["status"], "applied")

    @patch("mcp_server.server.settings")
    @patch("mcp_server.server.orjson.loads")
    @patch("mcp_server.server.Path.exists")
    @patch("mcp_server.server.Path.read_bytes")
    def test_get_company_tool(self, mock_read, mock_exists, mock_loads, mock_settings):
        mock_exists.return_value = True
        mock_loads.return_value = [
            {
                "name": "Target Company",
                "discovered_at": "2026-07-15T00:00:00",
                "last_updated": "2026-07-15T00:00:00",
                "notes": [],
                "jobs": []
            }
        ]

        from mcp_server.server import get_company
        res = get_company("target")
        self.assertIsNotNone(res)
        self.assertEqual(res["name"], "Target Company")

        res_none = get_company("nonexistent")
        self.assertIsNone(res_none)


if __name__ == "__main__":
    unittest.main()
