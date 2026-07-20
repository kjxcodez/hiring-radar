"""Saved searches data model definition for hiring-radar."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class SavedSearch(BaseModel):
    """Configuration for a named search query."""
    name: str
    profile: Optional[str] = None
    sources: list[str]
    remote: Optional[bool] = None
    country: Optional[str] = None
    keyword: Optional[str] = None
    exclude: Optional[str] = None
    days: Optional[int] = None
    limit: int
