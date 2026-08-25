"""Emit in-app notifications when monitor rules fire."""

from __future__ import annotations

import logging
import re

from db.user_notifications import insert_notification, list_active_user_ids
from redact import mask_webhook_delivery_error

logger = logging.getLogger(__name__)

_DIGITS_RE = re.compile(r"\d+")


def _normalize_for_dedupe(error_text: str) -> str:
    """Collapse digit runs so dedupe keys stay stable when errors embed
    changing values (HTTP status codes, timestamps, ports)."""
    return _DIGITS_RE.sub("#", error_text)

SCOPE_ANALYST = "analyst"
SCOPE_OPERATOR = "operator"


async def _emit_to_users(
    db,
    *,
    scope: str,
    user_ids: list[int],
    category: str,
    severity: str,
    title: str,
    body: str = "",
    entity_type: str = "",
    entity_id: str = "",
    dedupe_key: str,
) -> int:
    created = 0
    for user_id in user_ids:
        try:
            if await insert_notification(
                db,
                user_id=user_id,
                scope=scope,
                category=category,
                severity=severity,
                title=title,
                body=body,
                entity_type=entity_type,
                entity_id=entity_id,
                dedupe_key=dedupe_key,
            ):
                created += 1
        except Exception as exc:
            logger.warning(
                "Failed to insert notification for user %s (%s): %s",
                user_id,
                dedupe_key,
                exc,
            )
    return created


async def emit_watchlist_notification(
    db,
    *,
    cve_id: str,
    reason: str,
    detail: str,
    dedupe_key: str,
    severity: str = "high",
) -> int:
    user_ids = await list_active_user_ids(db, scope=SCOPE_ANALYST)
    if not user_ids:
        return 0
    title = f"{cve_id} — {reason}"
    return await _emit_to_users(
        db,
        scope=SCOPE_ANALYST,
        user_ids=user_ids,
        category="watchlist",
        severity=severity,
        title=title,
        body=detail,
        entity_type="cve",
        entity_id=cve_id.upper(),
        dedupe_key=dedupe_key,
    )


async def emit_ioc_watchlist_notification(
    db,
    *,
    user_id: int,
    ioc_value: str,
    source: str,
    summary: str,
    dedupe_key: str,
) -> int:
    return await _emit_to_users(
        db,
        scope=SCOPE_ANALYST,
        user_ids=[int(user_id)],
        category="ioc_watchlist",
        severity="high",
        title=f"IOC watchlist hit ({source})",
        body=summary[:500],
        entity_type="ioc",
        entity_id=ioc_value,
        dedupe_key=dedupe_key,
    )


async def emit_job_error_notification(
    db,
    *,
    job_id: str,
    error_message: str,
    dedupe_key: str,
) -> int:
    user_ids = await list_active_user_ids(db, scope=SCOPE_OPERATOR)
    if not user_ids:
        return 0
    body = (error_message or "Scheduler job reported an error.")[:500]
    return await _emit_to_users(
        db,
        scope=SCOPE_OPERATOR,
        user_ids=user_ids,
        category="job_error",
        severity="critical",
        title=f"Job failed: {job_id}",
        body=body,
        entity_type="job",
        entity_id=job_id,
        dedupe_key=dedupe_key,
    )


async def emit_api_key_unhealthy_notification(
    db,
    *,
    provider: str,
    error: str,
    dedupe_key: str,
) -> int:
    user_ids = await list_active_user_ids(db, scope=SCOPE_OPERATOR)
    if not user_ids:
        return 0
    return await _emit_to_users(
        db,
        scope=SCOPE_OPERATOR,
        user_ids=user_ids,
        category="api_key_unhealthy",
        severity="high",
        title=f"API key unhealthy: {provider}",
        body=(error or "Health ping failed")[:500],
        entity_type="api_key",
        entity_id=provider,
        dedupe_key=dedupe_key,
    )


async def emit_webhook_failure_notification(
    db,
    *,
    destination_id: str,
    label: str | None,
    error: str,
    event_type: str = "",
    dedupe_key: str | None = None,
) -> int:
    """Operator alert when a webhook destination delivery fails (REL-4 / E9-2)."""
    user_ids = await list_active_user_ids(db, scope=SCOPE_OPERATOR)
    if not user_ids:
        return 0
    safe_error = mask_webhook_delivery_error(error) or "Delivery failed"
    title_label = (label or destination_id).strip() or destination_id
    body_parts = [safe_error]
    if event_type:
        body_parts.append(f"Event: {event_type}")
    body = " — ".join(body_parts)[:500]
    key = dedupe_key or (
        f"webhook:{destination_id}:{_normalize_for_dedupe(safe_error)}"
    )
    return await _emit_to_users(
        db,
        scope=SCOPE_OPERATOR,
        user_ids=user_ids,
        category="webhook_failure",
        severity="high",
        title=f"Webhook delivery failed: {title_label}",
        body=body,
        entity_type="webhook",
        entity_id=destination_id,
        dedupe_key=key,
    )
