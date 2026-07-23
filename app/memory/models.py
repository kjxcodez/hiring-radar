"""Pydantic schemas defining multi-layered memory structures."""

from __future__ import annotations

import time
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    """A single episodic or factual memory record."""
    memory_id: str
    timestamp: float = Field(default_factory=time.time)
    summary: str
    entities: Dict[str, str] = Field(default_factory=dict)
    importance: int = 3
    tags: List[str] = Field(default_factory=list)
    source: str = "user"
    confidence: float = 1.0
    last_accessed: float = Field(default_factory=time.time)
    retrieval_count: int = 0


class UserProfile(BaseModel):
    """Evolving profile mapping of user preferences."""
    preferred_roles: List[str] = Field(default_factory=list)
    preferred_salary: Optional[str] = None
    preferred_locations: List[str] = Field(default_factory=list)
    remote_preference: Optional[bool] = None
    tech_stack: List[str] = Field(default_factory=list)
    preferred_companies: List[str] = Field(default_factory=list)
    seniority: Optional[str] = None
    preferred_industries: List[str] = Field(default_factory=list)
    preferred_communication_style: Optional[str] = None


class Preferences(BaseModel):
    """Free-form key-value preferences dict."""
    preferences: Dict[str, str] = Field(default_factory=dict)


class ConversationSummary(BaseModel):
    """Bullet summaries of conversations."""
    summary: str
    timestamp: float = Field(default_factory=time.time)


class MemorySearchResult(BaseModel):
    """A search match return value with relevance score."""
    record: MemoryRecord
    score: float
