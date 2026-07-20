"""Multi-destination webhook dispatch engine (V1.4 Theme 2)."""

from __future__ import annotations

import logging
from typing import Any

from database import (
    clear_webhook_destination_dedupe,
    get_db,
    record_webhook_delivery,
    claim_webhook_destination_sent,
    clear_webhook_destination_dedupe_for_dest,
)
from webhooks.destinations import (
    EVENT_BACKUP_FAILURE,
    EVENT_HEALTH,
    EVENT_KEV_ALERT,
    EVENT_KEV_BACKLOG,
    EVENT_IOC_WATCHLIST_HIT,
    EVENT_WATCHLIST_ALERT,
    WebhookDestination,
    load_destinations,
    normalize_event_type,
)
from webhooks.ssrf import (
    safe_webhook_request,
    webhook_json_payload,
)

logger = logging.getLogger(__name__)

DISCORD_MAX_CONTENT = 2000
TELEGRAM_MAX_TEXT = 4096
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
WEBHOOK_RETRIES = 2


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


async def _deliver_discord(dest: WebhookDestination, message: str) -> None:
    url = dest.config.get("url", "")
    payload = {"content": _truncate(message, DISCORD_MAX_CONTENT)}
    response = await safe_webhook_request(
        dest.health_source,
        "POST",
        url,
        json=payload,
        retries=WEBHOOK_RETRIES,
    )
    response.raise_for_status()


async def _deliver_telegram(dest: WebhookDestination, message: str) -> None:
    token = dest.config.get("token", "")
    chat_id = dest.config.get("chat_id", "")
    if not token or not chat_id:
        raise ValueError("telegram destination missing token or chat_id")
    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": _truncate(message, TELEGRAM_MAX_TEXT),
        "disable_web_page_preview": True,
    }
    response = await safe_webhook_request(
        dest.health_source,
        "POST",
        url,
        json=payload,
        retries=WEBHOOK_RETRIES,
    )
    response.raise_for_status()


async def _deliver_generic(
    dest: WebhookDestination,
    message: str,
    *,
    event_type: str,
    dedupe_key: str | None,
) -> None:
    url = dest.config.get("url", "")
    payload = webhook_json_payload(message, event_type=event_type, dedupe_key=dedupe_key)
    response = await safe_webhook_request(
        dest.health_source,
        "POST",
        url,
        json=payload,
        retries=WEBHOOK_RETRIES,
    )
    response.raise_for_status()


async def deliver_to_destination(
    dest: WebhookDestination,
    message: str,
    *,
    event_type: str,
    dedupe_key: str | None = None,
) -> dict[str, Any]:
    try:
        if dest.kind == "discord":
            await _deliver_discord(dest, message)
        elif dest.kind == "telegram":
            await _deliver_telegram(dest, message)
        elif dest.kind == "generic":
            await _deliver_generic(dest, message, event_type=event_type, dedupe_key=dedupe_key)
        else:
            raise ValueError(f"unknown destination kind: {dest.kind}")
        return {"destination_id": dest.id, "ok": True, "error": None}
    except Exception as exc:
        return {"destination_id": dest.id, "ok": False, "error": str(exc)[:300]}


async def dispatch_event(
    event_type: str,
    message: str,
    *,
    dedupe_key: str | None = None,
    destinations: list[WebhookDestination] | None = None,
    skip_dedupe: bool = False,
) -> dict[str, Any]:
    """Send an event to every enabled destination subscribed to event_type."""
    normalized = normalize_event_type(event_type)
    if normalized not in {
        EVENT_KEV_ALERT,
        EVENT_KEV_BACKLOG,
        EVENT_IOC_WATCHLIST_HIT,
        EVENT_BACKUP_FAILURE,
        EVENT_HEALTH,
        EVENT_WATCHLIST_ALERT,
    }:
        return {
            "status": "failed",
            "reason": "unknown_event_type",
            "event_type": normalized,
            "sent": [],
            "errors": {},
        }

    active = destinations if destinations is not None else await load_destinations()
    if not any(dest.enabled for dest in active):
        return {
            "status": "skipped",
            "reason": "no_webhook_destinations",
            "event_type": normalized,
            "sent": [],
            "errors": {},
        }

    if dedupe_key and not skip_dedupe:
        pass  # per-destination dedupe checked inside the delivery loop

    targets = [dest for dest in active if dest.subscribes_to(normalized)]
    if not targets:
        return {
            "status": "skipped",
            "reason": "no_subscribers",
            "event_type": normalized,
            "sent": [],
            "errors": {},
        }

    sent: list[str] = []
    errors: dict[str, str] = {}
    skipped_dedupe: list[str] = []
    for dest in targets:
        if dedupe_key and not skip_dedupe:
            db = await get_db()
            try:
                # Claim dedupe key before sending to prevent concurrent TOCTOU (IDEM-001)
                claimed = await claim_webhook_destination_sent(
                    db, dest.id, normalized, dedupe_key
                )
                if not claimed:
                    skipped_dedupe.append(dest.id)
                    continue
                await db.commit()
            finally:
                await db.close()

        result = await deliver_to_destination(
            dest,
            message,
            event_type=normalized,
            dedupe_key=dedupe_key,
        )
        db = await get_db()
        try:
            await record_webhook_delivery(
                db,
                destination_id=dest.id,
                event_type=normalized,
                dedupe_key=dedupe_key,
                status="ok" if result["ok"] else "failed",
                error=result["error"],
            )
            await db.commit()
            if not result["ok"] and result["error"]:
                try:
                    from notifications.emit import emit_webhook_failure_notification

                    await emit_webhook_failure_notification(
                        db,
                        destination_id=dest.id,
                        label=dest.label,
                        error=result["error"],
                        event_type=normalized,
                    )
                    await db.commit()
                except Exception as exc:
                    rollback = getattr(db, "rollback", None)
                    if rollback is not None:
                        try:
                            await rollback()
                        except Exception:
                            pass
                    logger.warning(
                        "Failed to emit webhook failure notification for %s: %s",
                        dest.id,
                        exc,
                    )
        finally:
            await db.close()

        if result["ok"]:
            sent.append(dest.id)
        else:
            # If delivery failed, rollback the dedupe claim so it can be retried (IDEM-001 retry safety)
            if dedupe_key and not skip_dedupe:
                db = await get_db()
                try:
                    await clear_webhook_destination_dedupe_for_dest(
                        db, dest.id, normalized, dedupe_key
                    )
                    await db.commit()
                finally:
                    await db.close()
            if result["error"]:
                errors[dest.id] = result["error"]
                logger.error(
                    "Webhook delivery failed for %s (%s): %s",
                    dest.id,
                    normalized,
                    result["error"],
                )

    if sent and not errors:
        status = "ok"
    elif not sent and skipped_dedupe and not errors:
        status = "skipped"
    elif sent:
        status = "partial"
    else:
        status = "failed"
    return {
        "status": status,
        "event_type": normalized,
        "dedupe_key": dedupe_key,
        "sent": sent,
        "errors": errors,
        **(
            {"reason": "deduped", "skipped_dedupe": skipped_dedupe}
            if status == "skipped" and skipped_dedupe
            else {}
        ),
    }


async def clear_event_dedupe(event_type: str, dedupe_key: str) -> None:
    db = await get_db()
    try:
        await clear_webhook_destination_dedupe(db, normalize_event_type(event_type), dedupe_key)
        await db.commit()
    finally:
        await db.close()


async def send_test_message(destination_id: str, message: str) -> dict[str, Any]:
    destinations = await load_destinations()
    dest = next((item for item in destinations if item.id == destination_id), None)
    if dest is None:
        return {
            "ok": False,
            "destination_id": destination_id,
            "delivered_at": None,
            "error": "unknown destination",
        }

    from datetime import datetime, timezone

    result = await deliver_to_destination(
        dest,
        message,
        event_type=EVENT_HEALTH,
        dedupe_key=None,
    )
    delivered_at = None
    if result["ok"]:
        delivered_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "ok": result["ok"],
        "destination_id": destination_id,
        "channel": destination_id,
        "delivered_at": delivered_at,
        "error": result["error"],
    }


async def send_alert(message: str, *, event_type: str = EVENT_KEV_ALERT) -> dict[str, Any]:
    """Backward-compatible alert sender without dedupe."""
    return await dispatch_event(event_type, message, skip_dedupe=True)
