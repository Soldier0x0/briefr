"""Send alert messages to Telegram and/or Discord via resilient_client.

Channels are independent: set DISCORD_WEBHOOK_URL and/or TELEGRAM_BOT_TOKEN +
TELEGRAM_CHAT_ID. When no channel is configured, send_alert is a no-op.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from resilient_client import resilient_request

logger = logging.getLogger(__name__)

WEBHOOK_RETRIES = 2
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
DISCORD_MAX_CONTENT = 2000
TELEGRAM_MAX_TEXT = 4096


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def discord_configured() -> bool:
    return bool(_env("DISCORD_WEBHOOK_URL"))


def telegram_configured() -> bool:
    return bool(_env("TELEGRAM_BOT_TOKEN") and _env("TELEGRAM_CHAT_ID"))


def webhooks_enabled() -> bool:
    return discord_configured() or telegram_configured()


def configured_channels() -> list[str]:
    channels: list[str] = []
    if discord_configured():
        channels.append("discord")
    if telegram_configured():
        channels.append("telegram")
    return channels


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


async def _send_discord(message: str) -> None:
    url = _env("DISCORD_WEBHOOK_URL")
    if not url:
        return
    payload = {"content": _truncate(message, DISCORD_MAX_CONTENT)}
    response = await resilient_request(
        "webhook.discord",
        "POST",
        url,
        json=payload,
        retries=WEBHOOK_RETRIES,
    )
    response.raise_for_status()


async def _send_telegram(message: str) -> None:
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": _truncate(message, TELEGRAM_MAX_TEXT),
        "disable_web_page_preview": True,
    }
    response = await resilient_request(
        "webhook.telegram",
        "POST",
        url,
        json=payload,
        retries=WEBHOOK_RETRIES,
    )
    response.raise_for_status()


async def send_alert(message: str) -> dict[str, Any]:
    """Deliver message to every configured channel; skip when none are set."""
    if not webhooks_enabled():
        return {"status": "skipped", "reason": "no_webhook_channels", "sent": []}

    sent: list[str] = []
    errors: dict[str, str] = {}

    if discord_configured():
        try:
            await _send_discord(message)
            sent.append("discord")
        except Exception as exc:
            errors["discord"] = str(exc)[:300]
            logger.error("Discord webhook delivery failed: %s", exc)

    if telegram_configured():
        try:
            await _send_telegram(message)
            sent.append("telegram")
        except Exception as exc:
            errors["telegram"] = str(exc)[:300]
            logger.error("Telegram webhook delivery failed: %s", exc)

    status = "ok" if sent and not errors else "partial" if sent else "failed"
    return {"status": status, "sent": sent, "errors": errors}
