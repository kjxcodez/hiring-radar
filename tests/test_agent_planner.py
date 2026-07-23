"""Verification tests for the standalone AI agent planner loop."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from app.agent.planner import run_agent_turn


class TestAgentPlanner(unittest.TestCase):
    @patch("app.agent.planner.settings")
    @patch("app.llm.router.LLMRouter.complete")
    def test_run_agent_turn_direct_reply(self, mock_complete, mock_settings):
        # Configure mocks
        mock_settings.openrouter_api_key = "fake_key"
        mock_settings.openrouter_model = "fake_model"

        # Mock direct text completion response
        from app.llm.models import LLMResponse
        mock_complete.return_value = LLMResponse(
            content="Hello! I can help you with that.",
            provider="openai",
            model="fake_model"
        )

        conversation_history = []
        result = run_agent_turn(
            user_message="Hello agent",
            conversation_history=conversation_history,
            model="fake_model"
        )

        self.assertEqual(result["reply"], "Hello! I can help you with that.")
        self.assertEqual(len(result["updated_history"]), 2)
        self.assertEqual(result["updated_history"][0]["role"], "user")
        self.assertEqual(result["updated_history"][1]["role"], "assistant")
        self.assertEqual(result["tool_calls_made"], [])

    @patch("app.agent.planner.TOOL_REGISTRY")
    @patch("app.agent.planner.settings")
    @patch("app.llm.router.LLMRouter.complete")
    def test_run_agent_turn_with_tool_call(self, mock_complete, mock_settings, mock_registry):
        # Configure mocks
        mock_settings.openrouter_api_key = "fake_key"
        mock_settings.openrouter_model = "fake_model"

        # Round 1: Model requests a tool call
        from app.llm.models import LLMResponse
        res_1 = LLMResponse(
            content=None,
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_company",
                        "arguments": "{\"name\": \"Test Co\"}"
                    }
                }
            ],
            provider="openai",
            model="fake_model"
        )

        # Round 2: Model gives final reply incorporating tool result
        res_2 = LLMResponse(
            content="I found details for Test Co.",
            provider="openai",
            model="fake_model"
        )

        mock_complete.side_effect = [res_1, res_2]

        # Mock tool registry implementation
        mock_tool = MagicMock()
        mock_tool.side_effecting = False
        mock_tool.fn.return_value = {"name": "Test Co", "description": "A great mock company"}
        mock_registry.__contains__.return_value = True
        mock_registry.__getitem__.return_value = mock_tool

        conversation_history = []
        result = run_agent_turn(
            user_message="Search for Test Co",
            conversation_history=conversation_history,
            model="fake_model"
        )

        self.assertEqual(result["reply"], "I found details for Test Co.")
        # History flow:
        # 1. user: Search for Test Co
        # 2. assistant: requests tool call
        # 3. tool result: JSON response
        # 4. assistant: final text answer
        self.assertEqual(len(result["updated_history"]), 4)
        self.assertEqual(result["updated_history"][0]["role"], "user")
        self.assertEqual(result["updated_history"][1]["role"], "assistant")
        self.assertEqual(result["updated_history"][2]["role"], "tool")
        self.assertEqual(result["updated_history"][3]["role"], "assistant")

        self.assertIn("get_company", result["tool_calls_made"])
        mock_tool.fn.assert_called_once_with(name="Test Co")


if __name__ == "__main__":
    unittest.main()
