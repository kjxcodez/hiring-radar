"""Runtime event notifications dispatcher for email, Telegram, and CLI alert panels."""

from __future__ import annotations

import logging
from app.notify.telegram import send_telegram_message

logger = logging.getLogger(__name__)


def trigger_runtime_notification(event_type: str, details: dict) -> None:
    """Send Telegram or log notifications for system state changes and task events."""
    msg = f"🔔 Hiring Radar Event: {event_type}\nDetails: {details}"
    
    logger.info(msg)
    
    try:
        send_telegram_message(msg)
    except Exception as e:
        logger.debug("Failed to send Telegram notification: %s", e)
