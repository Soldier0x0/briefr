"""Send alert messages via the V1.4 webhook engine.

Destinations are configured through env vars and/or the webhook_destinations
table. When no destination is configured, send_alert is a no-op.
"""

from __future__ import annotations

from typing import Any

from webhooks.destinations import configured_channels, webhooks_enabled
from webhooks.engine import send_alert as _send_alert
from webhooks.engine import send_test_message as _send_test_message

__all__ = [
    "configured_channels",
    "discord_configured",
    "send_alert",
    "send_test_message",
    "telegram_configured",
    "webhooks_enabled",
]


async def discord_configured() -> bool:
    return "discord" in await configured_channels()


async def telegram_configured() -> bool:
    return "telegram" in await configured_channels()


async def send_test_message(channel: str, message: str) -> dict:
    """Send a test message to a single destination."""
    return await _send_test_message(channel, message)


async def send_alert(message: str, *, event_type: str = "kev_alert") -> dict[str, Any]:
    """Deliver message to every configured destination (no dedupe)."""
    return await _send_alert(message, event_type=event_type)
