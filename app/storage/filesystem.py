"""Filesystem utilities for safe reads, safe writes, and directory creation."""

from __future__ import annotations

from pathlib import Path


class Filesystem:
    """Provides pure filesystem operations without any serialization logic."""

    @staticmethod
    def ensure_dir(path: Path) -> None:
        """Ensure that the parent directory of the path exists."""
        path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def exists(path: Path) -> bool:
        """Check if a path exists."""
        return path.exists()

    @staticmethod
    def read_bytes(path: Path) -> bytes:
        """Read the entire contents of a file as bytes."""
        if not path.exists():
            return b""
        return path.read_bytes()

    @staticmethod
    def write_bytes(path: Path, data: bytes) -> None:
        """Write bytes to a file directly (non-atomic)."""
        Filesystem.ensure_dir(path)
        path.write_bytes(data)

    @staticmethod
    def delete(path: Path) -> None:
        """Delete a file if it exists."""
        if path.exists():
            path.unlink()
