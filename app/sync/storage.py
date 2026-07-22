"""Storage coordinator managing sync checkpoints and raw snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from app.storage import JsonStorage
from app.sync.checkpoint import SyncCheckpoint
from app.sync.snapshot import Snapshot


class SyncStorage:
    """Manages files representing checkpoints and snapshots."""

    def __init__(self, output_dir: Path, storage: Optional[JsonStorage] = None) -> None:
        self.output_dir = output_dir
        self.storage = storage or JsonStorage()
        self.checkpoints_file = output_dir / "sync_checkpoints.json"
        self.snapshots_dir = output_dir / "snapshots"

    def _ensure_dirs(self) -> None:
        """Ensure output directory and snapshots directory exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Checkpoints
    # ------------------------------------------------------------------

    def load_all_checkpoints(self) -> Dict[str, SyncCheckpoint]:
        """Load all checkpoints from disk."""
        if not self.storage.exists(self.checkpoints_file):
            return {}
        try:
            data = self.storage.read(self.checkpoints_file)
            if not data or not isinstance(data, dict):
                return {}
            return {k: SyncCheckpoint.model_validate(v) for k, v in data.items()}
        except Exception:
            return {}

    def load_checkpoint(self, provider: str) -> SyncCheckpoint:
        """Load the checkpoint for a specific provider, returning default if missing."""
        checkpoints = self.load_all_checkpoints()
        if provider in checkpoints:
            return checkpoints[provider]
        return SyncCheckpoint(provider=provider)

    def save_checkpoint(self, checkpoint: SyncCheckpoint) -> None:
        """Save a checkpoint back to the checkpoints dictionary."""
        self._ensure_dirs()
        checkpoints = self.load_all_checkpoints()
        checkpoints[checkpoint.provider] = checkpoint
        data = {k: v.model_dump(mode="json") for k, v in checkpoints.items()}
        self.storage.write(self.checkpoints_file, data)

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def _snapshot_file(self, provider: str) -> Path:
        """Return the path to the snapshot file for *provider*."""
        return self.snapshots_dir / f"{provider}_snapshot.json"

    def load_snapshot(self, provider: str) -> Optional[Snapshot]:
        """Load the previous snapshot for *provider*."""
        file_path = self._snapshot_file(provider)
        if not self.storage.exists(file_path):
            return None
        try:
            data = self.storage.read(file_path)
            if not data or not isinstance(data, dict):
                return None
            return Snapshot.model_validate(data)
        except Exception:
            return None

    def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save a new snapshot for *provider*."""
        self._ensure_dirs()
        file_path = self._snapshot_file(snapshot.provider)
        data = snapshot.model_dump(mode="json")
        self.storage.write(file_path, data)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Wipe all checkpoints and snapshots."""
        if self.storage.exists(self.checkpoints_file):
            self.storage.delete(self.checkpoints_file)
        if self.snapshots_dir.exists():
            for f in self.snapshots_dir.glob("*.json"):
                self.storage.delete(f)
            # Delete directory if empty
            try:
                self.snapshots_dir.rmdir()
            except OSError:
                pass
