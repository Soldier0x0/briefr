"""Admin dashboard API — database engine and migration.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, HTTPException, Request

from database import DB_PATH
from dependencies import audit
from settings import settings

from .router import router

# ── Database engine & migration ────────────────────────────────────────────


@router.get("/database")
async def get_database_info(request: Request):
    from db.config import is_postgres, resolve_database_url

    current_url = resolve_database_url()
    on_postgres = is_postgres(current_url)
    info: dict[str, Any] = {
        "engine": "postgresql" if on_postgres else "sqlite",
        "require_postgres": settings.briefr_require_postgres,
        "writes_sqlite": not on_postgres and not settings.briefr_require_postgres,
    }
    if on_postgres:
        info["postgres_dsn_redacted"] = re.sub(r"://[^@]+@", "://***@", current_url)
    else:
        db_path = Path(DB_PATH)
        info["sqlite_path"] = str(db_path)
        info["sqlite_size_bytes"] = db_path.stat().st_size if db_path.exists() else 0
    return info


@router.post("/database/test-connection")
async def test_database_connection(request: Request, body: dict):
    from migration.sqlite_to_postgres import test_connection

    database_url = str(body.get("database_url", "")).strip()
    if not database_url:
        raise HTTPException(400, "database_url is required")
    return await test_connection(database_url)


@router.post("/database/migrate")
async def start_database_migration(request: Request, background_tasks: BackgroundTasks, body: dict):
    from db.config import is_postgres
    from migration.sqlite_to_postgres import reserve_migration_slot, run_migration

    database_url = str(body.get("database_url", "")).strip()
    confirm_text = str(body.get("confirm_text", "")).strip()
    if not database_url:
        raise HTTPException(400, "database_url is required")
    if not is_postgres(database_url):
        raise HTTPException(400, "database_url must be a postgresql:// URL")
    if confirm_text != "migrate":
        raise HTTPException(400, "Type 'migrate' to confirm")

    # Reserve the slot synchronously (not in the background task) so a second
    # rapid request can't slip past the check before the first task starts.
    try:
        await reserve_migration_slot()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))

    await audit(request, "database.migrate.start", re.sub(r"://[^@]+@", "://***@", database_url))
    background_tasks.add_task(run_migration, database_url, DB_PATH, _reserved=True)
    return {"ok": True, "message": "Migration started — poll /api/admin/database/migrate/status"}


@router.get("/database/migrate/status")
async def get_database_migration_status(request: Request):
    from migration.sqlite_to_postgres import get_status_with_fallback

    return await get_status_with_fallback()

