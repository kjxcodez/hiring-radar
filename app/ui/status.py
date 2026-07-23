"""Live status updates engine with spinners."""

from __future__ import annotations

import contextlib
from typing import Iterator
from rich.status import Status
from app.cli.common import console


class LiveStatus:
    """Live status wrapper managing Rich spinners."""

    def __init__(self, spinner: str = "dots", style: str = "bold purple") -> None:
        self.spinner = spinner
        self.style = style
        self._status: Status | None = None

    def update(self, text: str) -> None:
        """Update the status text dynamically in-place."""
        if self._status:
            self._status.update(f"[{self.style}]{text}[/{self.style}]")

    @contextlib.contextmanager
    def run(self, initial_text: str = "Thinking...") -> Iterator[LiveStatus]:
        """Context manager to start and stop the live spinner."""
        with console.status(
            f"[{self.style}]{initial_text}[/{self.style}]",
            spinner=self.spinner
        ) as rich_status:
            self._status = rich_status
            try:
                yield self
            finally:
                self._status = None
