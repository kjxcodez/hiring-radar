"""Listeners for tool and workflow timelines."""

from __future__ import annotations

import time
from typing import Dict
from app.cli.common import console


class ToolTimelineTracker:
    """Tracks start/stop timings of tool executions to show a checklist timeline."""

    def __init__(self) -> None:
        self._start_times: Dict[str, float] = {}

    def start_tool(self, tool_name: str) -> None:
        """Record start time of a tool."""
        self._start_times[tool_name] = time.time()

    def end_tool(self, tool_name: str, success: bool = True) -> None:
        """Record end time and print duration timeline update."""
        t_start = self._start_times.get(tool_name)
        if not t_start:
            return
            
        duration = time.time() - t_start
        status_char = "✓" if success else "✗"
        color = "green" if success else "red"
        
        console.print(f"[{color}]{status_char}[/{color}] [bold]{tool_name}[/bold] ({duration:.2f}s)")
