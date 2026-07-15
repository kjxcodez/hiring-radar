"""Verification tests for the MCP server transport configurations."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.cli import mcp_serve


class TestMcpTransport(unittest.TestCase):
    @patch("app.cli.console")
    @patch("mcp_server.server.main")
    def test_mcp_serve_command_stdio(self, mock_main, mock_console):
        # Clear env variables
        os.environ.pop("MCP_TRANSPORT", None)
        os.environ.pop("MCP_HTTP_PORT", None)
        os.environ.pop("MCP_HTTP_HOST", None)

        mcp_serve(transport="stdio", port=8811, host="0.0.0.0")

        self.assertEqual(os.environ.get("MCP_TRANSPORT"), "stdio")
        self.assertEqual(os.environ.get("MCP_HTTP_PORT"), "8811")
        self.assertEqual(os.environ.get("MCP_HTTP_HOST"), "0.0.0.0")
        mock_main.assert_called_once()

    @patch("app.cli.console")
    @patch("mcp_server.server.main")
    def test_mcp_serve_command_sse(self, mock_main, mock_console):
        # Clear env variables
        os.environ.pop("MCP_TRANSPORT", None)
        os.environ.pop("MCP_HTTP_PORT", None)
        os.environ.pop("MCP_HTTP_HOST", None)

        mcp_serve(transport="sse", port=9090, host="127.0.0.1")

        self.assertEqual(os.environ.get("MCP_TRANSPORT"), "sse")
        self.assertEqual(os.environ.get("MCP_HTTP_PORT"), "9090")
        self.assertEqual(os.environ.get("MCP_HTTP_HOST"), "127.0.0.1")
        mock_main.assert_called_once()


if __name__ == "__main__":
    unittest.main()
