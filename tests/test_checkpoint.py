"""Unit tests for the SyncCheckpoint model."""

from __future__ import annotations

from datetime import datetime

from app.sync.checkpoint import SyncCheckpoint


def test_checkpoint_defaults():
    cp = SyncCheckpoint(provider="greenhouse")
    assert cp.provider == "greenhouse"
    assert cp.last_successful_run is None
    assert cp.last_failed_run is None
    assert cp.duration == 0.0
    assert cp.processed_pages == 0
    assert cp.processed_cursors == []


def test_checkpoint_updates():
    now = datetime.utcnow()
    cp = SyncCheckpoint(
        provider="greenhouse",
        last_successful_run=now,
        duration=12.5,
        processed_pages=3,
        processed_cursors=["cursor1"],
    )
    assert cp.last_successful_run == now
    assert cp.duration == 12.5
    assert cp.processed_pages == 3
    assert cp.processed_cursors == ["cursor1"]
