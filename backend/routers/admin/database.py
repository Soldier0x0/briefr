"""Admin dashboard API — database engine and migration.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException, Request
from settings import settings

from .router import router

# ── Database engine & migration ────────────────────────────────────────────


def _mask_database_url_credentials(database_url: str) -> str:
    """Redact the userinfo (password) from a database URL for audit logging."""
    try:
        parts = urlsplit(database_url)
    except ValueError:
        return "***"
    if "@" not in parts.netloc:
        return database_url
    hostinfo = parts.netloc.rsplit("@", 1)[1]
    masked = f"***@{hostinfo}"
    return urlunsplit((parts.scheme, masked, parts.path, parts.query, parts.fragment))


@router.get("/database")
async def get_database_info(request: Request):
    import shutil

    from database import get_db
    from db.config import resolve_database_url
    from db.database_metrics import fetch_database_metrics

    current_url = resolve_database_url()
    info: dict[str, Any] = {
        "engine": "postgresql",
        "require_postgres": settings.briefr_require_postgres,
        "postgres_dsn_redacted": _mask_database_url_credentials(current_url),
    }

    partition_total = 0
    try:
        du = shutil.disk_usage(".")
        partition_total = du.total
    except OSError:
        pass

    db = await get_db()
    try:
        info["metrics"] = await fetch_database_metrics(
            db,
            db_path="postgresql",
            partition_total_bytes=partition_total,
        )
    finally:
        await db.close()

    return info


@router.post("/database/test-connection")
async def test_database_connection(request: Request, body: dict):
    import asyncpg

    from db.config import postgres_dsn

    database_url = str(body.get("database_url", "")).strip()
    if not database_url:
        raise HTTPException(400, "database_url is required")
    try:
        dsn = postgres_dsn(database_url)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        conn = await asyncpg.connect(dsn=dsn, timeout=10)
        try:
            version = await conn.fetchval("SELECT version()")
        finally:
            await conn.close()
        return {"ok": True, "server_version": version}
    except Exception:
        return {
            "ok": False,
            "error": "Could not connect to the database. Check DATABASE_URL and server logs.",
        }

