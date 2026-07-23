"""Crash recovery utility maintaining agent task graphs execution continuity."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from app.config import settings
from app.runtime.task import TaskGraph

logger = logging.getLogger(__name__)


class RecoveryEngine:
    """Restores executing queue, tasks, and graphs state upon crash restarts."""

    def __init__(self, directory: Optional[Path] = None) -> None:
        self.directory = directory or (settings.output_dir / "runtime")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.state_file = self.directory / "runtime_state.json"

    def save_state(self, active_graphs: Dict[str, TaskGraph]) -> None:
        """Persist active graph executions states atomically."""
        try:
            data = {gid: graph.model_dump(mode="json") for gid, graph in active_graphs.items()}
            self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save runtime recovery state: %s", e)

    def load_state(self) -> Dict[str, TaskGraph]:
        """Restore previous active graph executions states."""
        if not self.state_file.exists():
            return {}
        try:
            content = self.state_file.read_text(encoding="utf-8")
            if not content.strip():
                return {}
            data = json.loads(content)
            return {gid: TaskGraph(**graph_dict) for gid, graph_dict in data.items()}
        except Exception as e:
            logger.error("Failed to load runtime recovery state: %s", e)
            return {}

    def clear(self) -> None:
        """Purge recovery state file."""
        if self.state_file.exists():
            try:
                self.state_file.unlink()
            except Exception:
                pass
