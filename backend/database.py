import os
import json
import aiosqlite
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", "vektor.db")


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS cves (
                cve_id TEXT PRIMARY KEY,
                description TEXT,
                cvss_score REAL,
                severity TEXT,
                published TEXT,
                modified TEXT,
                affected_products TEXT DEFAULT '[]',
                mitre_technique TEXT,
                summary TEXT,
                is_kev INTEGER DEFAULT 0,
                epss_score REAL DEFAULT 0.0,
                patch_available INTEGER DEFAULT 0,
                source_urls TEXT DEFAULT '[]',
                cwe_ids TEXT DEFAULT '[]',
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_cves_severity ON cves(severity);
            CREATE INDEX IF NOT EXISTS idx_cves_published ON cves(published);
            CREATE INDEX IF NOT EXISTS idx_cves_is_kev ON cves(is_kev);
            CREATE INDEX IF NOT EXISTS idx_cves_epss ON cves(epss_score);

            CREATE TABLE IF NOT EXISTS ioc_cache (
                value TEXT PRIMARY KEY,
                ioc_type TEXT NOT NULL,
                result TEXT NOT NULL,
                cached_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_ioc_cached_at ON ioc_cache(cached_at);

            CREATE TABLE IF NOT EXISTS kev_deadlines (
                cve_id TEXT PRIMARY KEY,
                product TEXT,
                short_description TEXT,
                required_action TEXT,
                due_date TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_kev_due_date ON kev_deadlines(due_date);

            CREATE TABLE IF NOT EXISTS api_usage (
                service TEXT NOT NULL,
                date_utc TEXT NOT NULL,
                month_utc TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (service, date_utc)
            );

            CREATE INDEX IF NOT EXISTS idx_api_usage_month ON api_usage(month_utc);
            CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage(date_utc);
        """)
        await db.commit()
    finally:
        await db.close()


async def upsert_cve(db: aiosqlite.Connection, cve: dict) -> None:
    await db.execute(
        """
        INSERT INTO cves (
            cve_id, description, cvss_score, severity, published, modified,
            affected_products, mitre_technique, summary, is_kev, epss_score,
            patch_available, source_urls, cwe_ids, updated_at
        ) VALUES (
            :cve_id, :description, :cvss_score, :severity, :published, :modified,
            :affected_products, :mitre_technique, :summary, :is_kev, :epss_score,
            :patch_available, :source_urls, :cwe_ids, datetime('now')
        )
        ON CONFLICT(cve_id) DO UPDATE SET
            description = excluded.description,
            cvss_score = excluded.cvss_score,
            severity = excluded.severity,
            published = excluded.published,
            modified = excluded.modified,
            affected_products = excluded.affected_products,
            mitre_technique = excluded.mitre_technique,
            patch_available = excluded.patch_available,
            source_urls = excluded.source_urls,
            cwe_ids = excluded.cwe_ids,
            updated_at = datetime('now')
        """,
        {
            "cve_id": cve.get("cve_id", ""),
            "description": cve.get("description", ""),
            "cvss_score": cve.get("cvss_score"),
            "severity": cve.get("severity", "UNKNOWN"),
            "published": cve.get("published", ""),
            "modified": cve.get("modified", ""),
            "affected_products": json.dumps(cve.get("affected_products", [])),
            "mitre_technique": cve.get("mitre_technique"),
            "summary": cve.get("summary"),
            "is_kev": 1 if cve.get("is_kev") else 0,
            "epss_score": cve.get("epss_score", 0.0),
            "patch_available": 1 if cve.get("patch_available") else 0,
            "source_urls": json.dumps(cve.get("source_urls", [])),
            "cwe_ids": json.dumps(cve.get("cwe_ids", [])),
        },
    )


async def mark_cves_as_kev(db: aiosqlite.Connection, cve_ids: list) -> None:
    if not cve_ids:
        return
    placeholders = ",".join("?" * len(cve_ids))
    await db.execute(
        f"UPDATE cves SET is_kev = 1 WHERE cve_id IN ({placeholders})",
        cve_ids,
    )


async def update_epss_scores(db: aiosqlite.Connection, scores: dict) -> None:
    rows = [(score, cve_id) for cve_id, score in scores.items()]
    await db.executemany(
        "UPDATE cves SET epss_score = ? WHERE cve_id = ?",
        rows,
    )


async def upsert_kev(db: aiosqlite.Connection, entry: dict) -> None:
    await db.execute(
        """
        INSERT INTO kev_deadlines (cve_id, product, short_description, required_action, due_date, updated_at)
        VALUES (:cve_id, :product, :short_description, :required_action, :due_date, datetime('now'))
        ON CONFLICT(cve_id) DO UPDATE SET
            product = excluded.product,
            short_description = excluded.short_description,
            required_action = excluded.required_action,
            due_date = excluded.due_date,
            updated_at = datetime('now')
        """,
        {
            "cve_id": entry.get("cveID", ""),
            "product": entry.get("product", ""),
            "short_description": entry.get("shortDescription", ""),
            "required_action": entry.get("requiredAction", ""),
            "due_date": entry.get("dueDate", ""),
        },
    )


async def get_ioc_cache(db: aiosqlite.Connection, value: str) -> dict | None:
    row = await db.execute_fetchall(
        """
        SELECT result FROM ioc_cache
        WHERE value = ? AND cached_at > datetime('now', '-6 hours')
        """,
        (value,),
    )
    if row:
        return json.loads(row[0]["result"])
    return None


async def set_ioc_cache(db: aiosqlite.Connection, value: str, ioc_type: str, result: dict) -> None:
    await db.execute(
        """
        INSERT INTO ioc_cache (value, ioc_type, result, cached_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(value) DO UPDATE SET
            result = excluded.result,
            cached_at = datetime('now')
        """,
        (value, ioc_type, json.dumps(result)),
    )


async def get_cve_count(db: aiosqlite.Connection) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM cves")
    return rows[0]["cnt"] if rows else 0


async def get_last_updated(db: aiosqlite.Connection) -> str | None:
    rows = await db.execute_fetchall(
        "SELECT MAX(updated_at) as ts FROM cves"
    )
    return rows[0]["ts"] if rows else None


async def get_all_cve_ids(db: aiosqlite.Connection) -> list:
    rows = await db.execute_fetchall("SELECT cve_id FROM cves")
    return [r["cve_id"] for r in rows]
