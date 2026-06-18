"""Env-configured outbound webhook alerts (Telegram and/or Discord)."""

from webhooks.alerts import check_backup_deadman, process_kev_stack_alerts
from webhooks.sender import send_alert, webhooks_enabled

__all__ = [
    "check_backup_deadman",
    "process_kev_stack_alerts",
    "send_alert",
    "webhooks_enabled",
]
