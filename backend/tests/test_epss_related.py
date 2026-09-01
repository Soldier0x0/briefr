"""Tests for EPSS history and related CVE queries."""

import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import (
    get_db,
    get_epss_history,
    get_related_cves,
)


async def _db_with_cves() -> object:
    db = await get_db()
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    await db.execute(
        """
        INSERT INTO cves (cve_id, description, cvss_score, severity, published,
                          affected_products, epss_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CVE-2024-0001",
            "TensorFlow remote code execution.",
            9.8,
            "CRITICAL",
            today,
            json.dumps(["google:tensorflow"]),
            0.42,
        ),
    )
    await db.execute(
        """
        INSERT INTO cves (cve_id, description, cvss_score, severity, published,
                          affected_products, epss_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CVE-2024-0002",
            "Another TensorFlow issue.",
            8.1,
            "HIGH",
            today,
            json.dumps(["google:tensorflow"]),
            0.15,
        ),
    )
    await db.execute(
        """
        INSERT INTO cves (cve_id, description, cvss_score, severity, published,
                          affected_products, epss_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CVE-2024-9999",
            "Unrelated nginx bug.",
            5.0,
            "MEDIUM",
            today,
            json.dumps(["nginx:nginx"]),
            0.05,
        ),
    )
    await db.execute(
        "INSERT INTO epss_history (cve_id, score, recorded_date) VALUES (?, ?, ?)",
        ("CVE-2024-0001", 0.30, week_ago),
    )
    await db.execute(
        "INSERT INTO epss_history (cve_id, score, recorded_date) VALUES (?, ?, ?)",
        ("CVE-2024-0001", 0.35, today),
    )
    await db.commit()
    return db


def test_snapshot_sql_captures_score_before_update():
    """Snapshot INSERT mirrors scheduler: old score is stored before UPDATE."""
    import sqlite3

    day = date.today().isoformat()
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE cves (cve_id TEXT PRIMARY KEY, epss_score REAL);
        CREATE TABLE epss_history (
            cve_id TEXT NOT NULL,
            score REAL NOT NULL,
            recorded_date TEXT NOT NULL,
            PRIMARY KEY (cve_id, recorded_date)
        );
        """
    )
    conn.execute("INSERT INTO cves (cve_id, epss_score) VALUES ('CVE-TEST-1', 0.2)")
    conn.execute(
        """
        INSERT OR REPLACE INTO epss_history (cve_id, score, recorded_date)
        SELECT cve_id, epss_score, ?
        FROM cves
        WHERE epss_score IS NOT NULL
        """,
        (day,),
    )
    conn.execute(
        "UPDATE cves SET epss_score = ? WHERE cve_id = ?",
        (0.9, "CVE-TEST-1"),
    )
    row = conn.execute(
        "SELECT score FROM epss_history WHERE cve_id = 'CVE-TEST-1'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == 0.2


def test_get_epss_history_returns_date_score_pairs():
    async def run():
        db = await _db_with_cves()
        history = await get_epss_history(db, "CVE-2024-0001", days=30)
        assert len(history) >= 1
        assert "date" in history[0] and "score" in history[0]
        await db.close()

    asyncio.run(run())


def test_get_related_cves_same_product_excludes_self():
    async def run():
        db = await _db_with_cves()
        related = await get_related_cves(db, "CVE-2024-0001", limit=5)
        ids = {r["cve_id"] for r in related}
        assert "CVE-2024-0001" not in ids
        assert "CVE-2024-0002" in ids
        assert "CVE-2024-9999" not in ids
        await db.close()

    asyncio.run(run())


def test_get_related_cves_empty_when_no_products():
    async def run():
        db = await _db_with_cves()
        await db.execute(
            "INSERT INTO cves (cve_id, description, published, affected_products) "
            "VALUES ('CVE-EMPTY-1', 'x', ?, '[]')",
            (date.today().isoformat(),),
        )
        await db.commit()
        related = await get_related_cves(db, "CVE-EMPTY-1", limit=5)
        assert related == []
        await db.close()

    asyncio.run(run())
