"""Hydrate operator settings from DB at startup (env wins over DB over .env)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from config_schema import WRITABLE_CONFIG_KEYS, get_field
from database import get_db, list_app_settings, set_app_setting
from settings import PROCESS_ENV_KEYS

logger = logging.getLogger(__name__)

_DOTENV_PATH = Path(__file__).resolve().parent / ".env"


async def seed_app_settings_from_dotenv() -> int:
    """One-time import of .env writable keys into DB when absent."""
    if not _DOTENV_PATH.is_file():
        return 0

    from dotenv import dotenv_values

    values = dotenv_values(_DOTENV_PATH)
    seeded = 0
    db = await get_db()
    try:
        from db.app_settings import get_app_setting

        for key in WRITABLE_CONFIG_KEYS:
            field = get_field(key)
            if field and field.type == "secret":
                continue
            raw = values.get(key)
            if raw is None or str(raw).strip() == "":
                continue
            if await get_app_setting(db, key) is not None:
                continue
            await set_app_setting(db, key, str(raw))
            seeded += 1
        if seeded:
            await db.commit()
    finally:
        await db.close()
    if seeded:
        logger.info("Seeded %d operator setting(s) from .env into app_settings", seeded)
    return seeded


async def hydrate_operator_settings_from_db() -> int:
    """Apply DB operator settings to os.environ (skips process-level env keys)."""
    db = await get_db()
    try:
        rows = await list_app_settings(db)
    finally:
        await db.close()

    applied = 0
    for row in rows:
        key = row["key"]
        if key in PROCESS_ENV_KEYS:
            continue
        value = row.get("value")
        if value is None:
            continue
        os.environ[key] = str(value)
        applied += 1
    if applied:
        logger.info("Hydrated %d operator setting(s) from app_settings", applied)
    return applied


async def bootstrap_operator_settings() -> None:
    await seed_app_settings_from_dotenv()
    await hydrate_operator_settings_from_db()


async def persist_operator_setting(key: str, value: str) -> None:
    db = await get_db()
    try:
        await set_app_setting(db, key, value)
        await db.commit()
    finally:
        await db.close()
