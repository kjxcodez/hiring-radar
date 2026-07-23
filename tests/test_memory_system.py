"""Tests for memory infrastructure, store, indexes, ranking, and retrieval."""

from __future__ import annotations

from pathlib import Path
import time
import uuid
from app.memory.models import MemoryRecord, UserProfile, Preferences
from app.memory.store import MemoryStore
from app.memory.index import MemoryIndex
from app.memory.ranker import rank_memories, calculate_jaccard_similarity
from app.memory.retriever import retrieve_relevant_memories, extract_entities_from_text
from app.memory.profile import learn_from_user_query
from app.memory.compression import compress_conversation_history


def test_memory_store_crud(tmp_path: Path) -> None:
    """Verify loading and saving records in MemoryStore."""
    store = MemoryStore(directory=tmp_path)
    
    rec = MemoryRecord(
        memory_id=str(uuid.uuid4()),
        summary="User likes Python backend",
        timestamp=time.time(),
        importance=4,
        tags=["programming", "python"]
    )
    
    store.save_records("episodic", [rec])
    loaded = store.load_records("episodic")
    
    assert len(loaded) == 1
    assert loaded[0].summary == "User likes Python backend"
    assert loaded[0].importance == 4
    assert "python" in loaded[0].tags


def test_memory_index() -> None:
    """Verify entity and tag indexing."""
    rec = MemoryRecord(
        memory_id="test-id",
        summary="Worked at Stripe using React",
        entities={"company": "Stripe"},
        tags=["frontend", "react"]
    )
    
    idx = MemoryIndex()
    idx.rebuild([rec])
    
    assert "test-id" in idx.search_by_entity("stripe")
    assert "test-id" in idx.search_by_tag("react")
    
    idx.remove("test-id")
    assert "test-id" not in idx.search_by_tag("react")


def test_jaccard_similarity() -> None:
    """Verify string Jaccard calculation."""
    s1 = "I love python programming"
    s2 = "Python programming is awesome"
    
    sim = calculate_jaccard_similarity(s1, s2)
    assert sim > 0.0
    assert calculate_jaccard_similarity(s1, "") == 0.0


def test_hybrid_ranking() -> None:
    """Verify score ordering based on Jaccard similarity and recency."""
    rec1 = MemoryRecord(
        memory_id="rec1",
        summary="React frontend developer profile",
        timestamp=time.time() - 3600,
        importance=5
    )
    rec2 = MemoryRecord(
        memory_id="rec2",
        summary="Python backend developer profile",
        timestamp=time.time(),
        importance=3
    )
    
    results = rank_memories("looking for python profile", [rec1, rec2], {"python"})
    assert results[0].record.memory_id == "rec2"


def test_profile_heuristics(tmp_path: Path) -> None:
    """Verify profile preference auto-learning works cleanly."""
    store = MemoryStore(directory=tmp_path)
    
    from unittest.mock import patch
    with patch("app.memory.profile.global_memory_store", store):
        learn_from_user_query("I only want remote backend jobs in Europe with a salary expectations of 90k")
        
        prof = store.load_profile()
        assert prof.remote_preference is True
        assert prof.preferred_salary == "90k"
