"""Atomic write operations to prevent file corruption."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


def atomic_write(filepath: Path, data: bytes, backup: bool = False) -> None:
    """Write data to the filepath atomically.

    Guarantees that the file is not left in a partially written or corrupted
    state if the process is interrupted.
    """
    # Ensure target directory exists
    parent = filepath.parent
    parent.mkdir(parents=True, exist_ok=True)

    # Use a tempfile in the same directory to guarantee we're on the same mount point/drive,
    # which is required for an atomic os.replace operation on many systems.
    fd, temp_path_str = tempfile.mkstemp(dir=str(parent), prefix=".tmp_", suffix=".json")
    temp_path = Path(temp_path_str)

    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            # Force write buffer to disk
            try:
                os.fsync(f.fileno())
            except OSError:
                # Fsync might fail on some filesystems or virtual systems, fallback gracefully
                pass

        # Optionally create a backup before replacing the destination file
        if backup and filepath.exists():
            backup_path = filepath.with_suffix(filepath.suffix + ".backup")
            shutil.copy2(filepath, backup_path)

        # Atomically replace the destination file
        os.replace(temp_path, filepath)

    except Exception as exc:
        # Clean up the temp file if anything goes wrong
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise exc
