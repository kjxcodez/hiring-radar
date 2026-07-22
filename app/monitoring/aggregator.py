"""Event aggregator collapsing, deduplicating, and prioritizing change logs."""

from __future__ import annotations

from typing import Dict, List
from app.monitoring.events import ChangeEvent


class EventAggregator:
    """Consolidates and groups change events."""

    @staticmethod
    def collapse_and_deduplicate(events: List[ChangeEvent]) -> List[ChangeEvent]:
        """Keep only the most recent event of a given type per company/job."""
        seen = {}
        # Sort by timestamp so the latest overrides
        for ev in sorted(events, key=lambda e: e.timestamp):
            key = (ev.company_name, ev.job_url or "", ev.event_type)
            seen[key] = ev
        return list(seen.values())

    @staticmethod
    def group_by_company(events: List[ChangeEvent]) -> Dict[str, List[ChangeEvent]]:
        """Return a mapping of company names to their related change events."""
        grouped = {}
        for ev in events:
            if ev.company_name not in grouped:
                grouped[ev.company_name] = []
            grouped[ev.company_name].append(ev)
        return grouped

    @staticmethod
    def filter_by_severity(events: List[ChangeEvent], min_severity: str = "Low") -> List[ChangeEvent]:
        """Filter list of events by a minimum severity threshold."""
        severity_order = ["Informational", "Low", "Medium", "High", "Critical"]
        try:
            min_idx = severity_order.index(min_severity)
        except ValueError:
            min_idx = 0

        filtered = []
        for ev in events:
            try:
                ev_idx = severity_order.index(ev.severity)
            except ValueError:
                ev_idx = 0
            if ev_idx >= min_idx:
                filtered.append(ev)
        return filtered
