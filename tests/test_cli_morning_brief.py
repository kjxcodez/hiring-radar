"""Verification tests for the morning-brief CLI subcommand."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
import typer

from app.cli import morning_brief


class TestCliMorningBrief(unittest.TestCase):
    def setUp(self):
        import app.cli
        app.cli.reset_container()

    def tearDown(self):
        import app.cli
        app.cli.reset_container()

    @patch("app.cli.console")
    @patch("app.cli.yaml_config")
    @patch("app.cli.settings")
    def test_morning_brief_unconfigured_exits_cleanly(self, mock_settings, mock_yaml, mock_console):

        # Configure Telegram to be disabled
        mock_settings.telegram_bot_token = None
        mock_yaml.telegram.chat_id = ""
        mock_yaml.telegram.enabled = False

        # Should raise Exit(0) cleanly
        with self.assertRaises(typer.Exit) as ctx:
            morning_brief(input=MagicMock())

        self.assertEqual(ctx.exception.exit_code, 0)
        mock_console.print.assert_any_call(
            "Telegram notifications are not fully configured or are disabled. "
            "Skipping morning brief execution."
        )

    @patch("app.cli.outreach_digest")
    @patch("app.cli.yaml_config")
    @patch("app.cli.settings")
    def test_morning_brief_configured_triggers_digest(self, mock_settings, mock_yaml, mock_outreach_digest):
        # Configure Telegram to be enabled
        mock_settings.telegram_bot_token = "fake_token"
        mock_yaml.telegram.chat_id = "fake_chat_id"
        mock_yaml.telegram.enabled = True

        fake_input = MagicMock()
        morning_brief(input=fake_input)

        # Should trigger outreach_digest with send=True
        mock_outreach_digest.assert_called_once_with(input=fake_input, send=True)


if __name__ == "__main__":
    unittest.main()
