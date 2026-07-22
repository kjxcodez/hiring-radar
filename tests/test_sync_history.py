"""Unit tests for the SyncHistory log manager."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.storage import JsonStorage
from app.sync.history import SyncHistory, SyncHistoryEntry


def test_sync_history_lifecycle(tmp_path: Path):
    history_file = tmp_path / "sync_history.json"
    storage = JsonStorage()
    history = SyncHistory(history_file, storage=storage)

    assert not history.exists()
    assert history.load_all() == []

    entry1 = SyncHistoryEntry(
        provider="greenhouse",
        status="success",
        duration=1.2,
        added_companies=2,
        updated_companies=1,
        added_jobs=4,
    )
    history.append(entry1)
    assert history.exists()

    all_runs = history.load_all()
    assert len(all_runs) == 1
    assert all_runs[0].provider == "greenhouse"
    assert all_runs[0].status == "success"
    assert all_runs[0].added_companies == 2

    history.clear()
    assert not history.exists()
    assert history.load_all() == []
