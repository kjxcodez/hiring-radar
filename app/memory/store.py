"""Thread-safe persistent storage manager for local memory JSON databases."""

from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import List, Optional
from app.config import settings
from app.memory.models import MemoryRecord, UserProfile, Preferences, ConversationSummary


class MemoryStore:
    """Manages CRUD interfaces on memory JSON files with file locking."""

    def __init__(self, directory: Optional[Path] = None) -> None:
        self.directory = directory or (settings.output_dir / "memory")
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _get_path(self, name: str) -> Path:
        return self.directory / f"{name}.json"

    def load_records(self, name: str) -> List[MemoryRecord]:
        """Load list of episodic MemoryRecord objects."""
        path = self._get_path(name)
        if not path.exists():
            return []
            
        with self._lock:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return [MemoryRecord(**item) for item in data]
            except Exception:
                return []

    def save_records(self, name: str, records: List[MemoryRecord]) -> None:
        """Persist list of episodic MemoryRecord objects."""
        path = self._get_path(name)
        with self._lock:
            try:
                data = [rec.model_dump() for rec in records]
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass

    def load_profile(self) -> UserProfile:
        """Load evolving UserProfile."""
        path = self._get_path("profile")
        if not path.exists():
            return UserProfile()
            
        with self._lock:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return UserProfile(**data)
            except Exception:
                return UserProfile()

    def save_profile(self, profile: UserProfile) -> None:
        """Save evolving UserProfile."""
        path = self._get_path("profile")
        with self._lock:
            try:
                path.write_text(json.dumps(profile.model_dump(), indent=2), encoding="utf-8")
            except Exception:
                pass

    def load_preferences(self) -> Preferences:
        """Load free-form Preferences dictionary."""
        path = self._get_path("preferences")
        if not path.exists():
            return Preferences()
            
        with self._lock:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return Preferences(**data)
            except Exception:
                return Preferences()

    def save_preferences(self, prefs: Preferences) -> None:
        """Save free-form Preferences dictionary."""
        path = self._get_path("preferences")
        with self._lock:
            try:
                path.write_text(json.dumps(prefs.model_dump(), indent=2), encoding="utf-8")
            except Exception:
                pass

    def load_summaries(self) -> List[ConversationSummary]:
        """Load conversation summaries list."""
        path = self._get_path("summaries")
        if not path.exists():
            return []
            
        with self._lock:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return [ConversationSummary(**item) for item in data]
            except Exception:
                return []

    def save_summaries(self, summaries: List[ConversationSummary]) -> None:
        """Save conversation summaries list."""
        path = self._get_path("summaries")
        with self._lock:
            try:
                data = [s.model_dump() for s in summaries]
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass

    def clear(self) -> None:
        """Purge all memory data files."""
        with self._lock:
            for name in ["working", "episodic", "profile", "preferences", "summaries", "index"]:
                path = self._get_path(name)
                if path.exists():
                    try:
                        path.unlink()
                    except Exception:
                        pass


# Global Memory Store Instance
global_memory_store = MemoryStore()
