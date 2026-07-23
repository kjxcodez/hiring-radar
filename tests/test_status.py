"""Tests for Live Status Spinner UI module."""

from __future__ import annotations

from app.ui.status import LiveStatus


def test_live_status_updates() -> None:
    """Verify live status updating runs successfully."""
    status = LiveStatus()
    with status.run("Starting up") as s:
        s.update("Step 2")
        s.update("Step 3")
