"""Hydrate operator settings from DB at startup (env wins over DB over .env).

Secret-typed keys in `app_settings` are encrypted at rest when
`BRIEFR_SETTINGS_KEY` is set (ADR-006). Process env still wins.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from config_schema import WRITABLE_CONFIG_KEYS, get_field
from database import get_db, list_app_settings, set_app_setting
from settings import PROCESS_ENV_KEYS
from settings_crypto import decrypt_secret, encrypt_secret, is_encrypted_value

logger = logging.getLogger(__name__)

_DOTENV_PATH = Path(__file__).resolve().parent / ".env"


def _is_secret_key(key: str) -> bool:
    field = get_field(key)
    return bool(field and field.type == "secret")


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
        stored = str(value)
        try:
            if is_encrypted_value(stored) or _is_secret_key(key):
                stored = decrypt_secret(stored)
        except ValueError as exc:
            logger.warning(
                "Skipping app_settings key %s during hydrate: %s",
                key,
                exc,
            )
            continue
        os.environ[key] = stored
        applied += 1
    if applied:
        logger.info("Hydrated %d operator setting(s) from app_settings", applied)
    return applied


async def bootstrap_operator_settings() -> None:
    await seed_app_settings_from_dotenv()
    await hydrate_operator_settings_from_db()


async def persist_operator_setting(key: str, value: str) -> None:
    """Persist a writable setting. Secrets are encrypted when the settings key is set."""
    to_store = value
    if _is_secret_key(key):
        encrypted = encrypt_secret(value)
        if encrypted is None:
            logger.info(
                "Skipping app_settings persist for secret %s "
                "(set BRIEFR_SETTINGS_KEY to store encrypted secrets in DB; "
                ".env / process env still apply)",
                key,
            )
            return
        to_store = encrypted

    db = await get_db()
    try:
        await set_app_setting(db, key, to_store)
        await db.commit()
    finally:
        await db.close()
