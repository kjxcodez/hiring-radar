"""Hiring monitoring change detection and alerts package."""

from __future__ import annotations

from app.monitoring.events import ChangeEvent
from app.monitoring.alerts import Alert, AlertEngine
from app.monitoring.digest import DigestGenerator
from app.monitoring.repository import MonitoringRepository
from app.monitoring.cache import MonitoringCache
from app.monitoring.engine import MonitoringEngine

__all__ = [
    "ChangeEvent",
    "Alert",
    "AlertEngine",
    "DigestGenerator",
    "MonitoringRepository",
    "MonitoringCache",
    "MonitoringEngine",
]
