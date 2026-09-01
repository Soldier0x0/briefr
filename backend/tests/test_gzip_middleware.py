"""I2: GZipMiddleware compresses large JSON API responses."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db, init_db

def test_api_cves_supports_gzip_encoding():
    asyncio.run(init_db())

    async def seed() -> None:
        db = await get_db()
        try:
            for i in range(20):
                cve_id = f"CVE-2026-GZIP-{i:04d}"
                await db.execute(
                    """
                    INSERT INTO cves (
                        cve_id, description, severity, published, modified, is_kev, has_poc
                    ) VALUES (
                        ?, ?, 'HIGH', datetime('now'), datetime('now'), 0, 0
                    )
                    """,
                    (
                        cve_id,
                        "Long enough description payload to ensure the JSON list response "
                        "exceeds the GZipMiddleware minimum size threshold for compression.",
                    ),
                )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get("/api/cves?limit=20", headers={"Accept-Encoding": "gzip"})

    assert res.status_code == 200
    assert res.headers.get("content-encoding") == "gzip"
    body = res.json()
    assert len(body.get("data", [])) == 20
