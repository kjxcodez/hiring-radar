"""Hybrid ranking algorithm for memory record selection."""

from __future__ import annotations

import math
import time
from typing import List, Set
from app.memory.models import MemoryRecord, MemorySearchResult


def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate normalized token-based Jaccard similarity between two strings."""
    tokens1 = set(text1.lower().split())
    tokens2 = set(text2.lower().split())
    if not tokens1 or not tokens2:
        return 0.0
    return len(tokens1.intersection(tokens2)) / len(tokens1.union(tokens2))


def rank_memories(query: str, records: List[MemoryRecord], query_entities: Set[str]) -> List[MemorySearchResult]:
    """Calculate hybrid relevance score for each record and sort them."""
    now = time.time()
    results = []
    
    for rec in records:
        sem_sim = calculate_jaccard_similarity(query, rec.summary)
        
        delta_t = max(0.0, now - rec.timestamp)
        recency = math.exp(-delta_t / 604800.0) * 0.3
        
        importance = (rec.importance / 5.0) * 0.2
        
        overlap = 0.0
        rec_words = set(rec.summary.lower().split())
        for ent in rec.entities.values():
            rec_words.add(ent.lower())
        for tag in rec.tags:
            rec_words.add(tag.lower())
            
        matches = query_entities.intersection(rec_words)
        if matches:
            overlap = 0.3
            
        final_score = sem_sim + recency + importance + overlap
        results.append(MemorySearchResult(record=rec, score=final_score))
        
    results.sort(key=lambda r: r.score, reverse=True)
    return results
