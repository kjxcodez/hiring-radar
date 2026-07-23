"""Live CLI progress rendering for the Hiring Radar AI Agent."""

from __future__ import annotations

import time
from typing import Any
from rich.console import Group
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from app.agent.translator import translate_event
from app.workflows.events import (
    StepFailed,
    StepFinished,
    StepStarted,
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowStarted,
)


class AgentProgressRenderer:
    """Manages Rich Live console display for active workflow executions."""

    def __init__(self, show_progress: bool = True, animations: bool = True) -> None:
        self.show_progress = show_progress
        self.animations = animations
        self.live: Live | None = None
        self.active_wf: str | None = None
        self.steps: list[dict[str, Any]] = []
        self.current_step: str | None = None
        self.start_time: float = 0.0

    def __enter__(self) -> AgentProgressRenderer:
        if self.show_progress:
            self.start_time = time.perf_counter()
            self.live = Live(self.render(), refresh_per_second=10, transient=True)
            self.live.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.live:
            self.live.__exit__(exc_type, exc_val, exc_tb)
            self.live = None

    def render(self) -> Group:
        """Render the current workflow execution progress structure."""
        renderables = []
        
        # 1. Header (Active workflow)
        if self.active_wf:
            spin_style = "purple"
            header_text = Text(f" {self.active_wf}...", style="bold purple")
            if self.animations:
                renderables.append(Group(Spinner("dots", text=header_text, style=spin_style)))
            else:
                renderables.append(header_text)
                
        # 2. Step list
        for step in self.steps:
            name = step["name"]
            status = step["status"]
            if status == "success":
                renderables.append(Text(f"  ✓ {name}", style="green"))
            elif status == "failed":
                renderables.append(Text(f"  ✗ {name}", style="bold red"))
            elif status == "running":
                text = Text(f"  {name}", style="yellow")
                if self.animations:
                    renderables.append(Spinner("simpleDots", text=text, style="yellow"))
                else:
                    renderables.append(text)
                    
        return Group(*renderables)

    def update(self) -> None:
        if self.live:
            self.live.update(self.render())

    def handle_event(self, event: Any) -> None:
        """Process a workflow event and update display state."""
        if not self.show_progress:
            return

        if isinstance(event, WorkflowStarted):
            translated = translate_event(event)
            if translated:
                self.active_wf = translated.rstrip(".")
            else:
                self.active_wf = f"Running {event.workflow_name}"
            self.steps = []
            self.current_step = None
            self.update()
            
        elif isinstance(event, StepStarted):
            translated = translate_event(event)
            if translated:
                step_desc = translated.rstrip(".")
            else:
                step_desc = f"Executing {event.step_name}"
            
            # Deactivate previous running step
            for s in self.steps:
                if s["status"] == "running":
                    s["status"] = "success"
                    
            self.steps.append({"name": step_desc, "status": "running", "raw_name": event.step_name})
            self.current_step = event.step_name
            self.update()
            
        elif isinstance(event, StepFinished):
            # Mark the finished step as success
            for s in self.steps:
                if s["raw_name"] == event.step_name:
                    s["status"] = "success"
            self.update()
            
        elif isinstance(event, StepFailed):
            # Mark the failed step
            for s in self.steps:
                if s["raw_name"] == event.step_name:
                    s["status"] = "failed"
            self.update()
            
        elif isinstance(event, (WorkflowCompleted, WorkflowFailed)):
            # Complete all pending steps
            for s in self.steps:
                if s["status"] == "running":
                    s["status"] = "success" if isinstance(event, WorkflowCompleted) else "failed"
            self.update()
            # Brief sleep so the user can see completion
            time.sleep(0.1)
