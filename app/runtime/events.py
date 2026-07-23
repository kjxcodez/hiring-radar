"""Thread-safe event bus for runtime notifications and decoupled updates."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Event(BaseModel):
    """An event emitted by the agent runtime subsystems."""
    event_type: str
    timestamp: float = Field(default_factory=time.time)
    data: Dict[str, Any] = Field(default_factory=dict)


class EventBus:
    """Centralized event publisher/subscriber broker."""

    def __init__(self, history_limit: int = 1000) -> None:
        self.history_limit = history_limit
        self.history: List[Event] = []
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Register a subscriber listener callback for an event type."""
        self._subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast an event to all registered listener subscribers."""
        event = Event(event_type=event_type, data=data)
        
        self.history.append(event)
        if len(self.history) > self.history_limit:
            self.history.pop(0)

        callbacks = self._subscribers.get(event_type, [])
        for cb in callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error("Error in subscriber callback for event '%s': %s", event_type, e)


# Global Event Bus Instance
global_event_bus = EventBus()
