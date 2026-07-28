"""Admin dashboard API — operator config GET/POST/apply-all.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import os
import pathlib
import re
from typing import Any

from fastapi import BackgroundTasks, HTTPException, Request

from config_schema import (
    APPLY_RESTART,
    APPLY_SCHEDULER_RESCHEDULE,
    RESTART_REQUIRED_KEYS,
    WRITABLE_CONFIG_KEYS,
    get_field,
    list_schema,
    resolved_apply_strategy,
    validate_value,
)
from dependencies import audit

import routers.admin as _admin_pkg

from .helpers import (
    _apply_config_side_effects,
    _config_apply_message,
    _couple_embeddings_auto_on_enable,
    _env_flag_on,
    _mask_config_response_value,
    _mask_key,
    _mask_url,
    _propagate_to_settings,
)
from .router import router

# ── Config ─────────────────────────────────────────────────────────────────


def _get_config_response() -> dict[str, Any]:
    def _env(key: str, default: str = "") -> str:
        return os.environ.get(key, default)

    def _env_int(key: str, default: int) -> int:
        try:
            return int(os.environ.get(key, str(default)))
        except (ValueError, TypeError):
            return default

    # Mask age key file
    age_key_raw = _env("BACKUP_AGE_KEY_FILE")
    if age_key_raw and pathlib.Path(age_key_raw).is_file() and pathlib.Path(age_key_raw).stat().st_size > 0:
        age_key_masked = "*** set ***"
    else:
        age_key_masked = "not configured"

    allowed_origins_raw = _env("ALLOWED_ORIGINS", "http://localhost:5173")
    allowed_origins_list = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]

    return {
        "dotenv_path": str(_admin_pkg._DOTENV_PATH.resolve()),
        "scheduler": {
            "NVD_SYNC_INTERVAL_HOURS": _env_int("NVD_SYNC_INTERVAL_HOURS", 1),
            "KEV_SYNC_INTERVAL_MINUTES": _env_int("KEV_SYNC_INTERVAL_MINUTES", 15),
            "EPSS_SYNC_INTERVAL_HOURS": _env_int("EPSS_SYNC_INTERVAL_HOURS", 6),
            "INCIDENT_FEED_REFRESH_MINUTES": _env_int("INCIDENT_FEED_REFRESH_MINUTES", 30),
            "VULNRICHMENT_SYNC_INTERVAL_HOURS": _env_int("VULNRICHMENT_SYNC_INTERVAL_HOURS", 6),
            "VULNRICHMENT_BRANCH": _env("VULNRICHMENT_BRANCH", "develop"),
            "CVELISTV5_SYNC_INTERVAL_MINUTES": _env_int("CVELISTV5_SYNC_INTERVAL_MINUTES", 30),
            "CVELISTV5_BRANCH": _env("CVELISTV5_BRANCH", "main"),
            "CVELISTV5_INITIAL_SINCE_DAYS": _env_int("CVELISTV5_INITIAL_SINCE_DAYS", 7),
            "CIRCUIT_FAILURE_THRESHOLD": _env_int("CIRCUIT_FAILURE_THRESHOLD", 3),
            "CIRCUIT_COOLDOWN_SECONDS": _env_int("CIRCUIT_COOLDOWN_SECONDS", 60),
            "NVD_SYNC_OVERLAP_MINUTES": _env_int("NVD_SYNC_OVERLAP_MINUTES", 15),
            "SCHEDULER_DB_CONCURRENCY": _env_int("SCHEDULER_DB_CONCURRENCY", 3),
            "SCHEDULER_TIMEZONE": _env("SCHEDULER_TIMEZONE", "Asia/Kolkata"),
            "MITRE_REFRESH_HOUR": _env_int("MITRE_REFRESH_HOUR", 2),
            "MITRE_REFRESH_MINUTE": _env_int("MITRE_REFRESH_MINUTE", 0),
            "CORRELATION_HOUR": _env_int("CORRELATION_HOUR", 1),
            "CORRELATION_MINUTE": _env_int("CORRELATION_MINUTE", 0),
            "CORRELATION_TIMEZONE": _env("CORRELATION_TIMEZONE", "Asia/Kolkata"),
            "OTX_CORRELATION_HOUR": _env_int("OTX_CORRELATION_HOUR", 2),
            "OTX_CORRELATION_MINUTE": _env_int("OTX_CORRELATION_MINUTE", 0),
            "OTX_CORRELATION_TIMEZONE": _env("OTX_CORRELATION_TIMEZONE", "Asia/Kolkata"),
            "CACHE_REFRESH_HOUR": _env_int("CACHE_REFRESH_HOUR", 6),
            "CACHE_REFRESH_MINUTE": _env_int("CACHE_REFRESH_MINUTE", 0),
            "EXPLOIT_SOURCES_SYNC_ENABLED": _env("EXPLOIT_SOURCES_SYNC_ENABLED", "1"),
            "EXPLOIT_SOURCES_SYNC_INTERVAL_HOURS": _env_int("EXPLOIT_SOURCES_SYNC_INTERVAL_HOURS", 24),
            "EXPLOIT_SOURCES_THROTTLE_SECONDS": _env_int("EXPLOIT_SOURCES_THROTTLE_SECONDS", 2),
        },
        "ingest": {
            "MAX_CVES_PER_FETCH": _env_int("MAX_CVES_PER_FETCH", 2000),
            "NVD_DAYS_BACK": _env_int("NVD_DAYS_BACK", 14),
            "KEV_CROSS_FETCH_NVD": _env("KEV_CROSS_FETCH_NVD", "1"),
            "ATLAS_YAML_URL": _env("ATLAS_YAML_URL", ""),
            "MITRE_CVE_MAPPINGS_JSON_URL": _env("MITRE_CVE_MAPPINGS_JSON_URL", ""),
            "DB_PATH": _env("DB_PATH", "briefr.db"),
            "CPE_CATALOG_SYNC_ENABLED": _env("CPE_CATALOG_SYNC_ENABLED", "0"),
            "CPE_CATALOG_SYNC_INTERVAL_HOURS": _env_int("CPE_CATALOG_SYNC_INTERVAL_HOURS", 6),
            "CPE_CATALOG_MAX_PAGES": _env_int("CPE_CATALOG_MAX_PAGES", 10),
            "STACK_BACKFILL_ENABLED": _env("STACK_BACKFILL_ENABLED", "0"),
            "STACK_BACKFILL_MAX_PRODUCTS": _env_int("STACK_BACKFILL_MAX_PRODUCTS", 10),
            "STACK_BACKFILL_MAX_CVES": _env_int("STACK_BACKFILL_MAX_CVES", 5000),
        },
        "ml": {
            "EMBEDDINGS_ENABLED": _env("EMBEDDINGS_ENABLED", "0"),
            "EMBEDDINGS_AUTO_ON_INGEST": _env("EMBEDDINGS_AUTO_ON_INGEST", "1"),
            "EMBEDDINGS_INGEST_MAX_PER_RUN": _env_int("EMBEDDINGS_INGEST_MAX_PER_RUN", 25),
            "EMBEDDINGS_MODEL": _env("EMBEDDINGS_MODEL", "BAAI/bge-small-en-v1.5"),
            "EMBEDDINGS_CACHE_DIR": _env("EMBEDDINGS_CACHE_DIR", ""),
            "EMBEDDINGS_SYNC_INTERVAL_HOURS": _env_int("EMBEDDINGS_SYNC_INTERVAL_HOURS", 6),
            "EMBEDDINGS_MAX_PER_RUN": _env_int("EMBEDDINGS_MAX_PER_RUN", 2000),
            "LLM_PRODUCT_EXTRACTION_ENABLED": _env("LLM_PRODUCT_EXTRACTION_ENABLED", "0"),
            "LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS": _env_int("LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS", 6),
            "LLM_PRODUCT_EXTRACTION_MAX_PER_RUN": _env_int("LLM_PRODUCT_EXTRACTION_MAX_PER_RUN", 25),
            "CORRELATION_PRECOMPUTE_ENABLED": _env("CORRELATION_PRECOMPUTE_ENABLED", "0"),
            "DETECTION_CONTEXT_SYNC_ENABLED": _env("DETECTION_CONTEXT_SYNC_ENABLED", "0"),
            "DETECTION_CONTEXT_LLM_ENABLED": _env("DETECTION_CONTEXT_LLM_ENABLED", "0"),
            "DETECTION_CONTEXT_NUCLEI_ENABLED": _env("DETECTION_CONTEXT_NUCLEI_ENABLED", "1"),
            "POC_GITHUB_SYNC_ENABLED": _env("POC_GITHUB_SYNC_ENABLED", "1"),
            "EXPLOITDB_SYNC_ENABLED": _env("EXPLOITDB_SYNC_ENABLED", "1"),
            "METASPLOIT_SYNC_ENABLED": _env("METASPLOIT_SYNC_ENABLED", "1"),
            "NUCLEI_SYNC_ENABLED": _env("NUCLEI_SYNC_ENABLED", "1"),
        },
        "queue": {
            "PROCRASTINATE_ENABLED": _env("PROCRASTINATE_ENABLED", "0"),
            "API_CALL_EVENTS_ENABLED": _env("API_CALL_EVENTS_ENABLED", "1"),
        },
        "backup": {
            "BACKUP_ENABLED": _env("BACKUP_ENABLED", "1"),
            "BACKUP_DIR": _env("BACKUP_DIR", "/var/lib/briefr/backups"),
            "BACKUP_RETENTION_COUNT": _env_int("BACKUP_RETENTION_COUNT", 100),
            "BACKUP_INTERVAL_HOURS": _env_int("BACKUP_INTERVAL_HOURS", 6),
            "BACKUP_LOG_MAX_BYTES": _env_int("BACKUP_LOG_MAX_BYTES", 5242880),
            "BACKUP_LOG_BACKUP_COUNT": _env_int("BACKUP_LOG_BACKUP_COUNT", 5),
            "BACKUP_AGE_KEY_FILE": age_key_masked,
        },
        "app": {
            "BRIEFR_ENV": _env("BRIEFR_ENV", "development"),
            "DEFAULT_TIMEZONE": _env("DEFAULT_TIMEZONE", "Asia/Kolkata"),
            "ALLOWED_ORIGINS": allowed_origins_list,
            "BRIEFR_STACK_TERMS": _env("BRIEFR_STACK_TERMS", ""),
            "LOG_FORMAT": _env("LOG_FORMAT", "json"),
            "RATE_LIMIT_ENABLED": _env("RATE_LIMIT_ENABLED", "1"),
            "RATE_LIMIT_IOC_PER_MINUTE": _env_int("RATE_LIMIT_IOC_PER_MINUTE", 30),
            "RATE_LIMIT_REFRESH_PER_MINUTE": _env_int("RATE_LIMIT_REFRESH_PER_MINUTE", 10),
            "RATE_LIMIT_ADMIN_READ_PER_MINUTE": _env_int("RATE_LIMIT_ADMIN_READ_PER_MINUTE", 120),
            "RATE_LIMIT_LOGIN_PER_MINUTE": _env_int("RATE_LIMIT_LOGIN_PER_MINUTE", 5),
            "RATE_LIMIT_AUTH_REFRESH_PER_MINUTE": _env_int(
                "RATE_LIMIT_AUTH_REFRESH_PER_MINUTE", 30
            ),
            "RATE_LIMIT_WALLBOARD_PER_MINUTE": _env_int(
                "RATE_LIMIT_WALLBOARD_PER_MINUTE", 60
            ),
            "RATE_LIMIT_SEARCH_TOKEN_PER_MINUTE": _env_int(
                "RATE_LIMIT_SEARCH_TOKEN_PER_MINUTE", 30
            ),
            "DATABASE_URL": (
                re.sub(r"://[^@]+@", "://***@", _env("DATABASE_URL"))
                if _env("DATABASE_URL") else "not configured"
            ),
            "DATABASE_POOL_SIZE": _env_int("DATABASE_POOL_SIZE", 10),
        },
        "api_keys": {
            "NVD_API_KEY": _mask_key(_env("NVD_API_KEY")),
            "VIRUSTOTAL_API_KEY": _mask_key(_env("VIRUSTOTAL_API_KEY")),
            "ABUSEIPDB_API_KEY": _mask_key(_env("ABUSEIPDB_API_KEY")),
            "GREYNOISE_API_KEY": _mask_key(_env("GREYNOISE_API_KEY")),
            "GITHUB_TOKEN": _mask_key(_env("GITHUB_TOKEN")),
            "GROQ_API_KEY": _mask_key(_env("GROQ_API_KEY")),
            "GEMINI_API_KEY": _mask_key(_env("GEMINI_API_KEY")),
            "CEREBRAS_API_KEY": _mask_key(_env("CEREBRAS_API_KEY")),
            "OPENROUTER_API_KEY": _mask_key(_env("OPENROUTER_API_KEY")),
            "ANTHROPIC_API_KEY": _mask_key(_env("ANTHROPIC_API_KEY")),
            "OTX_API_KEY": _mask_key(_env("OTX_API_KEY")),
            "CIRCL_API_KEY": _mask_key(_env("CIRCL_API_KEY")),
            "ABUSECH_AUTH_KEY": _mask_key(_env("ABUSECH_AUTH_KEY")),
        },
        "security": {
            "WALLBOARD_TOKEN": _mask_key(_env("WALLBOARD_TOKEN")),
        },
        "webhooks": {
            "DISCORD_WEBHOOK_URL": _mask_url(_env("DISCORD_WEBHOOK_URL")),
            "DISCORD_WEBHOOK_ENABLED": _env("DISCORD_WEBHOOK_ENABLED", "1"),
            "DISCORD_WEBHOOK_EVENTS": _env("DISCORD_WEBHOOK_EVENTS", ""),
            "TELEGRAM_BOT_TOKEN": _mask_key(_env("TELEGRAM_BOT_TOKEN")),
            "TELEGRAM_CHAT_ID": _env("TELEGRAM_CHAT_ID") or "not configured",
            "TELEGRAM_WEBHOOK_ENABLED": _env("TELEGRAM_WEBHOOK_ENABLED", "1"),
            "TELEGRAM_WEBHOOK_EVENTS": _env("TELEGRAM_WEBHOOK_EVENTS", ""),
            "WEBHOOK_GENERIC_URL": _mask_url(_env("WEBHOOK_GENERIC_URL")),
            "WEBHOOK_GENERIC_ENABLED": _env("WEBHOOK_GENERIC_ENABLED", "1"),
            "WEBHOOK_GENERIC_LABEL": _env("WEBHOOK_GENERIC_LABEL") or "not configured",
            "WEBHOOK_GENERIC_EVENTS": _env("WEBHOOK_GENERIC_EVENTS", ""),
        },
    }


@router.get("/config")
async def get_config(request: Request):
    return _get_config_response()


@router.get("/config/schema")
async def get_config_schema(request: Request):
    """Field metadata (section, type, bounds, help text) for every writable
    config key, so the frontend can render labels/help text and pre-validate
    instead of hardcoding a parallel copy of the key list per section."""
    return list_schema()


@router.post("/config")
async def set_config(request: Request, body: dict):
    key = body.get("key", "")
    value = str(body.get("value", ""))

    if not key or key not in WRITABLE_CONFIG_KEYS:
        raise HTTPException(400, f"Key '{key}' is not writable via this API")

    validation_error = validate_value(key, value)
    if validation_error:
        raise HTTPException(400, validation_error)

    previous_enabled = _env_flag_on(os.environ.get("EMBEDDINGS_ENABLED"), default="0")
    to_write = _couple_embeddings_auto_on_enable(
        [(key, value)],
        previous_enabled=previous_enabled,
    )

    from operator_settings import persist_operator_setting
    from redact import redact_audit_target

    written_keys: list[str] = []
    for write_key, write_value in to_write:
        os.environ[write_key] = write_value
        _propagate_to_settings(write_key, write_value)
        await persist_operator_setting(write_key, write_value)
        written_keys.append(write_key)
        await audit(
            request,
            f"config.set.{write_key}",
            redact_audit_target(f"config.set.{write_key}", write_key, write_value),
        )

    field = get_field(key)
    strategy = resolved_apply_strategy(field) if field else APPLY_RESTART
    side_effects = (
        _apply_config_side_effects(written_keys)
        if strategy == APPLY_SCHEDULER_RESCHEDULE
        or any(
            get_field(k) and resolved_apply_strategy(get_field(k)) == APPLY_SCHEDULER_RESCHEDULE
            for k in written_keys
        )
        else {}
    )

    masked = _mask_config_response_value(key, value)
    return {
        "ok": True,
        "key": key,
        "masked_value": masked,
        "apply_strategy": strategy,
        "warning_restart_required": strategy == APPLY_RESTART,
        "rescheduled_jobs": side_effects.get("rescheduled_jobs", []),
        "coupled_keys": [k for k in written_keys if k != key],
        "message": _config_apply_message(
            written_keys,
            restart_needed=False,
            side_effects=side_effects,
        ),
    }


@router.post("/config/apply-all")
async def apply_all_config(request: Request, background_tasks: BackgroundTasks):
    """Write multiple config keys to the DB-backed app_settings store and trigger a restart."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Body must be a JSON array of {key, value} objects") from None

    if not isinstance(body, list):
        raise HTTPException(400, "Body must be a JSON array of {key, value} objects")

    allowed = WRITABLE_CONFIG_KEYS
    errors: list[str] = []
    validated: list[tuple[str, str]] = []

    # Pass 1: validate all items before writing anything
    for item in body:
        if not isinstance(item, dict):
            errors.append(f"Invalid item: {item!r}")
            continue
        key = str(item.get("key", "")).strip()
        value = str(item.get("value", ""))

        if not key:
            errors.append("Empty key in item")
            continue
        if key not in allowed:
            errors.append(f"Key '{key}' is not in the writable allowlist")
            continue
        validation_error = validate_value(key, value)
        if validation_error:
            errors.append(validation_error)
            continue
        validated.append((key, value))

    if errors:
        raise HTTPException(400, {"errors": errors, "partial_keys": []})

    # Pass 2: write only after full validation passes
    previous_enabled = _env_flag_on(os.environ.get("EMBEDDINGS_ENABLED"), default="0")
    validated = _couple_embeddings_auto_on_enable(
        validated,
        previous_enabled=previous_enabled,
    )
    # Re-validate coupled keys (allowlisted bool)
    for key, value in validated:
        if key not in allowed:
            raise HTTPException(400, {"errors": [f"Key '{key}' is not in the writable allowlist"], "partial_keys": []})
        validation_error = validate_value(key, value)
        if validation_error:
            raise HTTPException(400, {"errors": [validation_error], "partial_keys": []})

    changed_keys: list[str] = []
    from operator_settings import persist_operator_setting

    for key, value in validated:
        os.environ[key] = value
        _propagate_to_settings(key, value)
        await persist_operator_setting(key, value)
        changed_keys.append(key)

    if not changed_keys:
        return {"ok": True, "changed_keys": [], "message": "No changes to apply"}

    changed_summary = ", ".join(changed_keys[:10])
    restart_needed = any(
        (get_field(k) and resolved_apply_strategy(get_field(k)) == APPLY_RESTART)
        or k in RESTART_REQUIRED_KEYS
        for k in changed_keys
    )
    await audit(
        request,
        "config.apply",
        changed_summary,
        metadata={"changed_keys": changed_keys, "restart_needed": restart_needed},
    )

    side_effects = _apply_config_side_effects(changed_keys)
    if restart_needed:
        background_tasks.add_task(_admin_pkg.trigger_graceful_restart)
    message = _config_apply_message(
        changed_keys,
        restart_needed=restart_needed,
        side_effects=side_effects,
    )

    return {
        "ok": True,
        "changed_keys": changed_keys,
        "restart_required": restart_needed,
        "rescheduled_jobs": side_effects.get("rescheduled_jobs", []),
        "message": message,
    }

