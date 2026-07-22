"""Diff Engine for property-level field changes detection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class FieldDiff(BaseModel):
    """Represents a change in a single property of an entity."""

    field_name: str
    previous_value: Optional[Any] = None
    current_value: Optional[Any] = None


class CRMDiffEngine:
    """Detects changed values for specific model fields."""

    @staticmethod
    def diff_dicts(old: Dict[str, Any], new: Dict[str, Any], fields: List[str]) -> List[FieldDiff]:
        """Compare lists of fields between two dictionaries."""
        diffs = []
        for field in fields:
            old_val = old.get(field)
            new_val = new.get(field)
            if old_val != new_val:
                diffs.append(FieldDiff(field_name=field, previous_value=old_val, current_value=new_val))
        return diffs

    @staticmethod
    def diff_pydantic(old: BaseModel, new: BaseModel, fields: List[str]) -> List[FieldDiff]:
        """Compare specific fields between two Pydantic models."""
        diffs = []
        for field in fields:
            old_val = getattr(old, field, None)
            new_val = getattr(new, field, None)
            if old_val != new_val:
                diffs.append(FieldDiff(field_name=field, previous_value=old_val, current_value=new_val))
        return diffs
