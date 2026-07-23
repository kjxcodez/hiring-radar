"""Retriever coordinating query entity extraction, search, and top-k selection."""

from __future__ import annotations

import time
from typing import List, Set
from app.cli.common import get_container
from app.memory.models import MemoryRecord
from app.memory.store import global_memory_store
from app.memory.ranker import rank_memories


def extract_entities_from_text(text: str) -> Set[str]:
    """Parse entities (technologies, companies, keywords) from input text."""
    entities = set()
    
    try:
        container = get_container()
        if container:
            companies = container.company_repo.load_all()
            for co in companies:
                co_name = co.get("name", "") if isinstance(co, dict) else getattr(co, "name", "")
                if co_name.lower() in text.lower():
                    entities.add(co_name.lower())
    except Exception:
        pass
        
    stack_keywords = {"python", "javascript", "react", "typescript", "node", "rust", "go", "java", "aws", "docker"}
    for word in text.lower().replace(",", " ").replace(".", " ").split():
        if word in stack_keywords:
            entities.add(word)
            
    return entities


def retrieve_relevant_memories(query: str, top_k: int = 5) -> List[MemoryRecord]:
    """Retrieve top-k relevant memories using hybrid ranking."""
    records = global_memory_store.load_records("episodic")
    if not records:
        return []
        
    query_entities = extract_entities_from_text(query)
    ranked = rank_memories(query, records, query_entities)
    top_results = ranked[:top_k]
    
    retrieved_records = []
    for res in top_results:
        rec = res.record
        rec.last_accessed = time.time()
        rec.retrieval_count += 1
        retrieved_records.append(rec)
        
    all_records = {r.memory_id: r for r in records}
    for r in retrieved_records:
        all_records[r.memory_id] = r
    global_memory_store.save_records("episodic", list(all_records.values()))
    
    return retrieved_records
