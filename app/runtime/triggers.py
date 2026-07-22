from enum import Enum


class TriggerSource(str, Enum):
    """The trigger source initiating a workflow execution."""
    MANUAL = "manual"
    CLI = "cli"
    CRON = "cron"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    DASHBOARD = "dashboard"
