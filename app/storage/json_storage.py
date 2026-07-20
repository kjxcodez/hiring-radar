"""High-level JSON storage backend coordinating safe reads and atomic writes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.storage.filesystem import Filesystem
from app.storage.atomic import atomic_write
from app.storage.serializer import serialize, deserialize


class JsonStorage:
    """Orchestrates filesystem reads/writes and serialization for JSON datasets."""

    def read(self, filepath: Path) -> Any:
        """Read and deserialize JSON data from the file."""
        if not Filesystem.exists(filepath):
            return None
        raw = Filesystem.read_bytes(filepath)
        return deserialize(raw)

    def write(self, filepath: Path, data: Any, backup: bool = False) -> None:
        """Serialize and atomically write data to the file."""
        raw = serialize(data)
        atomic_write(filepath, raw, backup=backup)

    def exists(self, filepath: Path) -> bool:
        """Check if the given storage file exists."""
        return Filesystem.exists(filepath)

    def delete(self, filepath: Path) -> None:
        """Delete the storage file if it exists."""
        Filesystem.delete(filepath)
