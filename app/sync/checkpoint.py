"""Synchronization checkpoint model tracking state metadata per provider."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class SyncCheckpoint(BaseModel):
    """Tracks metadata about sync status per provider for reliability."""

    provider: str
    last_successful_run: Optional[datetime] = None
    last_failed_run: Optional[datetime] = None
    duration: float = 0.0
    processed_pages: int = 0
    processed_cursors: List[str] = Field(default_factory=list)
    etag: Optional[str] = None
    last_modified: Optional[str] = None
