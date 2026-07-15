"""Verification tests for the standalone AI agent mechanical approval gates."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.agent.planner import run_agent_turn
from app.agent.tools import TOOL_REGISTRY, execute_approved_tool


class TestAgentApproval(unittest.TestCase):
    def setUp(self):
        # We will mock the output directory to be a temp dir
        self.output_dir_patcher = patch("app.agent.memory.settings")
        self.mock_settings = self.output_dir_patcher.start()
        self.temp_path = Path("output_test_approval")
        self.mock_settings.output_dir = self.temp_path

        # Patch settings in planner/tools
        self.planner_settings_patcher = patch("app.agent.planner.settings")
        self.mock_planner_settings = self.planner_settings_patcher.start()
        self.mock_planner_settings.output_dir = self.temp_path

        self.tools_settings_patcher = patch("app.agent.tools.settings")
        self.mock_tools_settings = self.tools_settings_patcher.start()
        self.mock_tools_settings.output_dir = self.temp_path

        self.mem_file = self.temp_path / "agent_memory.json"
        if self.mem_file.exists():
            self.mem_file.unlink()
        if self.temp_path.exists():
            self.temp_path.rmdir()

    def tearDown(self):
        if self.mem_file.exists():
            self.mem_file.unlink()
        if self.temp_path.exists():
            self.temp_path.rmdir()
        self.output_dir_patcher.stop()
        self.planner_settings_patcher.stop()
        self.tools_settings_patcher.stop()

    @patch("app.agent.planner.settings")
    @patch("app.agent.planner._post_with_retry")
    def test_run_agent_turn_approval_blocks_execution(self, mock_post, mock_settings):
        # Configure settings mock
        mock_settings.openrouter_api_key = "fake_key"
        mock_settings.openrouter_model = "fake_model"

        # Model requests apply_to_company (which is side_effecting=True)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_apply",
                                "type": "function",
                                "function": {
                                    "name": "apply_to_company",
                                    "arguments": "{\"company_name\": \"Stark Industries\", \"status\": \"applied\"}"
                                }
                            }
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        # Spy on tool implementation
        mock_tool = MagicMock()
        with patch.dict(TOOL_REGISTRY, {"apply_to_company": TOOL_REGISTRY["apply_to_company"]}):
            # Patch the inner function to ensure it is not executed
            with patch.object(TOOL_REGISTRY["apply_to_company"], "fn", mock_tool):
                conversation_history = []
                result = run_agent_turn(
                    user_message="Apply to Stark Industries",
                    conversation_history=conversation_history,
                    model="fake_model"
                )

                # Assert execution was blocked and returns pending_approval
                self.assertIn("pending_approval", result)
                pending = result["pending_approval"]
                self.assertEqual(pending["tool"], "apply_to_company")
                self.assertEqual(pending["arguments"]["company_name"], "Stark Industries")
                self.assertIn("update application status for 'Stark Industries'", pending["description"])

                # Verify tool was NOT called
                mock_tool.assert_not_called()

    @patch("app.agent.tools.settings")
    def test_execute_approved_tool_executes(self, mock_tools_settings):
        mock_tool_fn = MagicMock()
        mock_tool_fn.return_value = {"status": "success"}

        with patch.dict(TOOL_REGISTRY, {"apply_to_company": TOOL_REGISTRY["apply_to_company"]}):
            # Set a mock function as the tool implementation
            TOOL_REGISTRY["apply_to_company"].fn = mock_tool_fn

            res = execute_approved_tool("apply_to_company", {"company_name": "Wayne Enterprises"})
            self.assertEqual(res, {"status": "success"})
            mock_tool_fn.assert_called_once_with(company_name="Wayne Enterprises")


if __name__ == "__main__":
    unittest.main()
