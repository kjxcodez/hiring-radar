"""Synchronization and Change Detection Engine package.

Exposes models and managers to track crawls incrementally, detect changes
between runs, and preserve synchronization checkpoints and histories.
"""

from __future__ import annotations

from app.sync.checkpoint import SyncCheckpoint
from app.sync.diff import DiffEngine, SnapshotDiff
from app.sync.engine import SyncEngine
from app.sync.fingerprint import generate_company_fingerprint, generate_job_fingerprint
from app.sync.history import SyncHistory, SyncHistoryEntry
from app.sync.metrics import SyncMetrics
from app.sync.snapshot import Snapshot
from app.sync.storage import SyncStorage

__all__ = [
    "SyncCheckpoint",
    "DiffEngine",
    "SnapshotDiff",
    "SyncEngine",
    "generate_company_fingerprint",
    "generate_job_fingerprint",
    "SyncHistory",
    "SyncHistoryEntry",
    "SyncMetrics",
    "Snapshot",
    "SyncStorage",
]
