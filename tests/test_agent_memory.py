"""Verification tests for the standalone AI agent persistent memory."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from app.models import Company
from app.agent.memory import (
    load_memory,
    save_memory,
    remember_preference,
    reject_company,
    log_decision,
)
from app.agent.planner import build_agent_system_prompt
from app.agent.tools import TOOL_REGISTRY


class TestAgentMemory(unittest.TestCase):
    def setUp(self):
        # We will mock the output directory to be a temp dir or custom path in memory
        self.output_dir_patcher = patch("app.agent.memory.settings")
        self.mock_settings = self.output_dir_patcher.start()
        # Create a temp path or mock output dir
        self.temp_path = Path("output_test_memory")
        self.mock_settings.output_dir = self.temp_path

        # Also patch settings in planner/tools
        self.planner_settings_patcher = patch("app.agent.planner.settings")
        self.mock_planner_settings = self.planner_settings_patcher.start()
        self.mock_planner_settings.output_dir = self.temp_path

        self.tools_settings_patcher = patch("app.agent.tools.settings")
        self.mock_tools_settings = self.tools_settings_patcher.start()
        self.mock_tools_settings.output_dir = self.temp_path

        # Cleanup if files exist
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

    def test_load_save_memory(self):
        # Initial empty load
        mem = load_memory()
        self.assertEqual(mem["preferences"], {})
        self.assertEqual(mem["rejected_companies"], [])
        self.assertEqual(mem["past_decisions"], [])

        # Save preference
        remember_preference("role", "Engineer")
        mem2 = load_memory()
        self.assertEqual(mem2["preferences"]["role"], "Engineer")

        # Reject company
        reject_company("bad-corp", "poor reviews")
        mem3 = load_memory()
        self.assertIn("bad-corp", mem3["rejected_companies"])
        self.assertEqual(len(mem3["past_decisions"]), 1)
        self.assertIn("Rejected company 'bad-corp'", mem3["past_decisions"][0]["summary"])

        # Log decision
        log_decision("Custom log entry")
        mem4 = load_memory()
        self.assertEqual(len(mem4["past_decisions"]), 2)
        self.assertEqual(mem4["past_decisions"][1]["summary"], "Custom log entry")

    def test_system_prompt_embedding(self):
        remember_preference("location", "Remote")
        reject_company("outcast-llc", "boring work")

        prompt = build_agent_system_prompt()
        self.assertIn("location: Remote", prompt)
        self.assertIn("outcast-llc", prompt)

    @patch("app.agent.tools.search_jobs")
    def test_search_jobs_and_recommend_tool_filters_rejected(self, mock_search):
        # Configure search_jobs mock to return a company we rejected
        from datetime import datetime
        now_str = datetime.utcnow().isoformat()
        mock_search.return_value = [
            {"name": "Good Corp", "domain": "good.com", "discovered_at": now_str, "last_updated": now_str},
            {"name": "Bad LLC", "domain": "bad.com", "discovered_at": now_str, "last_updated": now_str}
        ]

        # Reject Bad LLC
        reject_company("bad.com", "not interested")

        # Invoke search_jobs wrapper
        search_fn = TOOL_REGISTRY["search_jobs"].fn
        results = search_fn(sources=["greenhouse"])

        # Should only contain Good Corp
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Good Corp")


if __name__ == "__main__":
    unittest.main()
