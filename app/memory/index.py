"""In-memory and JSON serialized indexing utilities for memory records."""

from __future__ import annotations

from typing import Dict, List, Set
from app.memory.models import MemoryRecord


class MemoryIndex:
    """Maintains indexed references of memory entities and tags."""

    def __init__(self) -> None:
        self.entity_index: Dict[str, Set[str]] = {}
        self.tag_index: Dict[str, Set[str]] = {}

    def rebuild(self, records: List[MemoryRecord]) -> None:
        """Clear and reconstruct indices from list of records."""
        self.entity_index.clear()
        self.tag_index.clear()
        
        for rec in records:
            self.add(rec)

    def add(self, record: MemoryRecord) -> None:
        """Add record details to indexing maps."""
        for ent_key, ent_val in record.entities.items():
            normalized_ent = ent_val.lower().strip()
            self.entity_index.setdefault(normalized_ent, set()).add(record.memory_id)

        for tag in record.tags:
            normalized_tag = tag.lower().strip()
            self.tag_index.setdefault(normalized_tag, set()).add(record.memory_id)

    def remove(self, record_id: str) -> None:
        """Delete specific record ID from indices."""
        for entry_set in self.entity_index.values():
            entry_set.discard(record_id)
        for tag_set in self.tag_index.values():
            tag_set.discard(record_id)

    def search_by_entity(self, entity_name: str) -> Set[str]:
        """Return memory IDs matching entity name."""
        return self.entity_index.get(entity_name.lower().strip(), set())

    def search_by_tag(self, tag: str) -> Set[str]:
        """Return memory IDs matching tag."""
        return self.tag_index.get(tag.lower().strip(), set())


# Global Index Instance
global_memory_index = MemoryIndex()
