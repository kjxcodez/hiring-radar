"""Verification tests for the diagnostics health check script."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from scripts.health_check import run_checks


class TestHealthCheck(unittest.TestCase):
    @patch("scripts.health_check.Console")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_bytes")
    @patch("app.config.settings")
    @patch("app.config.yaml_config")
    def test_run_checks_all_ok(self, mock_yaml, mock_settings, mock_read_bytes, mock_exists, mock_console):
        # Configure settings/env mock
        mock_settings.openrouter_api_key = "fake_api_key"
        mock_settings.telegram_bot_token = None  # Not testing Telegram messaging
        mock_settings.output_dir = Path("output")

        # Mock Path methods
        mock_exists.return_value = True
        mock_read_bytes.side_effect = [b"[]", b"{}"]  # companies.json, applications.json

        success = run_checks()
        self.assertTrue(success)

    @patch("scripts.health_check.Console")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_bytes")
    @patch("app.config.settings")
    def test_run_checks_missing_key_fails(self, mock_settings, mock_read_bytes, mock_exists, mock_console):
        # Configure settings to have missing key
        mock_settings.openrouter_api_key = None
        mock_settings.output_dir = Path("output")

        # Mock Path methods
        mock_exists.return_value = True
        mock_read_bytes.side_effect = [b"[]", b"{}"]

        success = run_checks()
        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
