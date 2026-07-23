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
        import logging
        logger = logging.getLogger(__name__)

        if not Filesystem.exists(filepath):
            return None
        
        try:
            raw = Filesystem.read_bytes(filepath)
            return deserialize(raw)
        except Exception as exc:
            logger.warning(
                f"Failed to read/deserialize primary file {filepath} (Error: {exc}). "
                "Attempting recovery from backup..."
            )
            backup_path = filepath.with_suffix(filepath.suffix + ".backup")
            if Filesystem.exists(backup_path):
                try:
                    raw_bak = Filesystem.read_bytes(backup_path)
                    recovered = deserialize(raw_bak)
                    logger.info(f"Successfully recovered dataset from backup file: {backup_path}")
                    return recovered
                except Exception as bak_exc:
                    logger.error(
                        f"Failed to read/deserialize backup file {backup_path} (Error: {bak_exc})."
                    )
            else:
                logger.error(f"No backup file found at {backup_path} for recovery.")
            raise exc

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
