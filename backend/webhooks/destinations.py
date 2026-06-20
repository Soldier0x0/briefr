"""Webhook destination configuration — env seeds plus DB overrides (V1.4)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import aiosqlite

from database import get_db

EVENT_KEV_ALERT = "kev_alert"
EVENT_BACKUP_FAILURE = "backup_failure"
EVENT_HEALTH = "health"

ALL_EVENT_TYPES = (EVENT_KEV_ALERT, EVENT_BACKUP_FAILURE, EVENT_HEALTH)

LEGACY_EVENT_ALIASES = {
    "kev_stack": EVENT_KEV_ALERT,
    "backup_deadman": EVENT_BACKUP_FAILURE,
}


def normalize_event_type(event_type: str) -> str:
    return LEGACY_EVENT_ALIASES.get(event_type, event_type)


def parse_event_types(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return list(ALL_EVENT_TYPES)
    if isinstance(raw, list):
        values = raw
    else:
        text = raw.strip()
        if not text:
            return list(ALL_EVENT_TYPES)
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = []
            values = parsed if isinstance(parsed, list) else []
        else:
            values = [part.strip() for part in text.split(",") if part.strip()]
    normalized = []
    for item in values:
        event = normalize_event_type(str(item))
        if event in ALL_EVENT_TYPES and event not in normalized:
            normalized.append(event)
    return normalized or list(ALL_EVENT_TYPES)


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _truthy(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


@dataclass
class WebhookDestination:
    id: str
    kind: str
    label: str
    enabled: bool
    event_types: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    source: str = "env"

    @property
    def health_source(self) -> str:
        return f"webhook.{self.id}"

    def subscribes_to(self, event_type: str) -> bool:
        return self.enabled and normalize_event_type(event_type) in self.event_types


def _discord_destination() -> WebhookDestination | None:
    url = _env("DISCORD_WEBHOOK_URL")
    if not url:
        return None
    return WebhookDestination(
        id="discord",
        kind="discord",
        label="Discord",
        enabled=_truthy("DISCORD_WEBHOOK_ENABLED", True),
        event_types=parse_event_types(_env("DISCORD_WEBHOOK_EVENTS") or None),
        config={"url": url},
        source="env",
    )


def _telegram_destination() -> WebhookDestination | None:
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return None
    return WebhookDestination(
        id="telegram",
        kind="telegram",
        label="Telegram",
        enabled=_truthy("TELEGRAM_WEBHOOK_ENABLED", True),
        event_types=parse_event_types(_env("TELEGRAM_WEBHOOK_EVENTS") or None),
        config={"token": token, "chat_id": chat_id},
        source="env",
    )


def _generic_destination() -> WebhookDestination | None:
    url = _env("WEBHOOK_GENERIC_URL")
    if not url:
        return None
    return WebhookDestination(
        id="generic",
        kind="generic",
        label=_env("WEBHOOK_GENERIC_LABEL") or "Generic HTTPS",
        enabled=_truthy("WEBHOOK_GENERIC_ENABLED", True),
        event_types=parse_event_types(_env("WEBHOOK_GENERIC_EVENTS") or None),
        config={"url": url},
        source="env",
    )


def load_env_destinations() -> list[WebhookDestination]:
    destinations: list[WebhookDestination] = []
    for builder in (_discord_destination, _telegram_destination, _generic_destination):
        dest = builder()
        if dest is not None:
            destinations.append(dest)
    return destinations


def _row_to_destination(row: aiosqlite.Row) -> WebhookDestination:
    try:
        config = json.loads(row["config_json"] or "{}")
    except json.JSONDecodeError:
        config = {}
    if not isinstance(config, dict):
        config = {}
    return WebhookDestination(
        id=row["id"],
        kind=row["kind"],
        label=row["label"] or row["id"],
        enabled=bool(row["enabled"]),
        event_types=parse_event_types(row["event_types"]),
        config=config,
        source=row["source"] or "db",
    )


async def sync_env_destinations_to_db() -> None:
    """Upsert env-configured destinations so admin can toggle them in DB."""
    env_dests = {dest.id: dest for dest in load_env_destinations()}
    db = await get_db()
    try:
        for dest in env_dests.values():
            await db.execute(
                """
                INSERT INTO webhook_destinations (
                    id, kind, label, enabled, event_types, config_json, source
                ) VALUES (?, ?, ?, ?, ?, ?, 'env')
                ON CONFLICT(id) DO UPDATE SET
                    kind = excluded.kind,
                    label = excluded.label,
                    config_json = excluded.config_json,
                    source = 'env',
                    updated_at = datetime('now')
                """,
                (
                    dest.id,
                    dest.kind,
                    dest.label,
                    int(dest.enabled),
                    json.dumps(dest.event_types),
                    json.dumps(dest.config),
                ),
            )
        await db.commit()
    finally:
        await db.close()


async def load_destinations() -> list[WebhookDestination]:
    env_dests = {dest.id: dest for dest in load_env_destinations()}
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT id, kind, label, enabled, event_types, config_json, source
            FROM webhook_destinations
            ORDER BY id
            """
        )
    finally:
        await db.close()

    if not rows:
        return list(env_dests.values())

    merged: dict[str, WebhookDestination] = dict(env_dests)
    for row in rows:
        db_dest = _row_to_destination(row)
        env_dest = env_dests.get(db_dest.id)
        if env_dest is not None:
            merged[db_dest.id] = WebhookDestination(
                id=db_dest.id,
                kind=env_dest.kind,
                label=db_dest.label or env_dest.label,
                enabled=db_dest.enabled,
                event_types=db_dest.event_types,
                config=env_dest.config,
                source="env",
            )
        else:
            merged[db_dest.id] = db_dest
    return sorted(merged.values(), key=lambda d: d.id)


def webhooks_enabled() -> bool:
    return any(dest.enabled for dest in load_env_destinations())


def configured_channels() -> list[str]:
    return [dest.id for dest in load_env_destinations() if dest.enabled]
