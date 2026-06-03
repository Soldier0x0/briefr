import os
import json
import aiosqlite
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", "briefr.db")


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
                epss_score REAL,
                has_poc INTEGER DEFAULT 0,
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
                date_added TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_kev_due_date ON kev_deadlines(due_date);
            CREATE INDEX IF NOT EXISTS idx_kev_date_added ON kev_deadlines(date_added);

            CREATE TABLE IF NOT EXISTS api_usage (
                service TEXT NOT NULL,
                date_utc TEXT NOT NULL,
                month_utc TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (service, date_utc)
            );

            CREATE INDEX IF NOT EXISTS idx_api_usage_month ON api_usage(month_utc);
            CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage(date_utc);

            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS mitre_techniques (
                technique_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                tactic TEXT DEFAULT '',
                url TEXT NOT NULL,
                platforms TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS cve_technique_map (
                cve_id TEXT NOT NULL,
                technique_id TEXT NOT NULL,
                PRIMARY KEY (cve_id, technique_id),
                FOREIGN KEY (technique_id) REFERENCES mitre_techniques(technique_id)
            );

            CREATE INDEX IF NOT EXISTS idx_cve_technique_map_technique
                ON cve_technique_map(technique_id);
            CREATE INDEX IF NOT EXISTS idx_cve_technique_map_cve
                ON cve_technique_map(cve_id);

            CREATE TABLE IF NOT EXISTS atlas_techniques (
                technique_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                tactic TEXT DEFAULT '',
                tactic_id TEXT DEFAULT '',
                url TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_atlas_techniques_tactic
                ON atlas_techniques(tactic);

            CREATE TABLE IF NOT EXISTS atlas_case_studies (
                study_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                summary TEXT DEFAULT '',
                summary_full TEXT DEFAULT '',
                techniques TEXT DEFAULT '[]',
                target TEXT DEFAULT '',
                date TEXT DEFAULT '',
                study_type TEXT DEFAULT '',
                cve_ids TEXT DEFAULT '[]'
            );

            CREATE INDEX IF NOT EXISTS idx_atlas_case_studies_date
                ON atlas_case_studies(date);

            CREATE TABLE IF NOT EXISTS epss_history (
                cve_id TEXT NOT NULL,
                score REAL NOT NULL,
                recorded_date TEXT NOT NULL,
                PRIMARY KEY (cve_id, recorded_date)
            );

            CREATE INDEX IF NOT EXISTS idx_epss_history_cve_date
                ON epss_history(cve_id, recorded_date);

            CREATE TABLE IF NOT EXISTS cve_exploits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL DEFAULT 'poc',
                source TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                published_date TEXT DEFAULT '',
                fetched_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_cve_exploits_cve
                ON cve_exploits(cve_id);

            CREATE TABLE IF NOT EXISTS feed_cache (
                cache_key TEXT PRIMARY KEY,
                result TEXT NOT NULL,
                cached_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_feed_cache_cached_at
                ON feed_cache(cached_at);
        """)
        await db.commit()

        for migration in (
            "ALTER TABLE kev_deadlines ADD COLUMN date_added TEXT DEFAULT ''",
            "ALTER TABLE cves ADD COLUMN has_poc INTEGER DEFAULT 0",
        ):
            try:
                await db.execute(migration)
                await db.commit()
            except Exception:
                pass

        try:
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_cves_has_poc ON cves(has_poc)"
            )
            await db.commit()
        except Exception:
            pass

        await db.execute(
            "UPDATE cves SET epss_score = NULL WHERE epss_score = 0.0"
        )
        await db.commit()
    finally:
        await db.close()


async def upsert_cve(db: aiosqlite.Connection, cve: dict) -> None:
    await db.execute(
        """
        INSERT INTO cves (
            cve_id, description, cvss_score, severity, published, modified,
            affected_products, mitre_technique, summary, is_kev, epss_score,
            has_poc, patch_available, source_urls, cwe_ids, updated_at
        ) VALUES (
            :cve_id, :description, :cvss_score, :severity, :published, :modified,
            :affected_products, :mitre_technique, :summary, :is_kev, :epss_score,
            :has_poc, :patch_available, :source_urls, :cwe_ids, datetime('now')
        )
        ON CONFLICT(cve_id) DO UPDATE SET
            description = excluded.description,
            cvss_score = excluded.cvss_score,
            severity = excluded.severity,
            published = excluded.published,
            modified = excluded.modified,
            affected_products = excluded.affected_products,
            mitre_technique = COALESCE(excluded.mitre_technique, cves.mitre_technique),
            summary = COALESCE(excluded.summary, cves.summary),
            has_poc = CASE WHEN excluded.has_poc = 1 THEN 1 ELSE cves.has_poc END,
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
            "epss_score": cve.get("epss_score"),
            "has_poc": 1 if cve.get("has_poc") else 0,
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


async def snapshot_epss_scores(db: aiosqlite.Connection, recorded_date: str | None = None) -> int:
    """Persist current EPSS scores before a bulk update (one row per CVE per day)."""
    from datetime import date

    day = recorded_date or date.today().isoformat()
    cursor = await db.execute(
        """
        INSERT OR REPLACE INTO epss_history (cve_id, score, recorded_date)
        SELECT cve_id, epss_score, ?
        FROM cves
        WHERE epss_score IS NOT NULL
        """,
        (day,),
    )
    return cursor.rowcount


async def update_epss_scores(db: aiosqlite.Connection, scores: dict) -> None:
    rows = [(score, cve_id.upper()) for cve_id, score in scores.items()]
    await db.executemany(
        "UPDATE cves SET epss_score = ? WHERE cve_id = ?",
        rows,
    )


async def get_epss_history(
    db: aiosqlite.Connection, cve_id: str, days: int = 30
) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT recorded_date AS date, score
        FROM epss_history
        WHERE cve_id = ?
          AND recorded_date >= DATE('now', ?)
        ORDER BY recorded_date ASC
        """,
        (cve_id.upper(), f"-{days - 1} days"),
    )
    return [{"date": row["date"], "score": row["score"]} for row in rows]


async def get_related_cves(
    db: aiosqlite.Connection, cve_id: str, limit: int = 5
) -> list[dict]:
    """CVEs sharing an affected product (vendor:product), published in last 30 days."""
    cve_key = cve_id.upper()
    rows = await db.execute_fetchall(
        "SELECT affected_products FROM cves WHERE cve_id = ?",
        (cve_key,),
    )
    if not rows:
        return []

    raw = rows[0]["affected_products"] or "[]"
    try:
        products = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        products = []

    products = [p for p in products if isinstance(p, str) and ":" in p]
    if not products:
        return []

    conditions: list[str] = []
    params: list = [cve_key]
    for product in products[:10]:
        needle = f'%"{product.lower()}"%'
        conditions.append("LOWER(affected_products) LIKE ?")
        params.append(needle)

    where_products = "(" + " OR ".join(conditions) + ")"
    params.append(limit)

    related = await db.execute_fetchall(
        f"""
        SELECT cve_id, description, cvss_score, severity, published, epss_score
        FROM cves
        WHERE cve_id != ?
          AND published IS NOT NULL
          AND published != ''
          AND DATE(published) >= DATE('now', '-30 days')
          AND {where_products}
        ORDER BY
          CASE WHEN cvss_score IS NULL THEN -1 ELSE cvss_score END DESC,
          published DESC
        LIMIT ?
        """,
        params,
    )

    seen: set[str] = set()
    out: list[dict] = []
    for row in related:
        rid = row["cve_id"]
        if rid in seen:
            continue
        seen.add(rid)
        out.append(
            {
                "cve_id": rid,
                "description": row["description"] or "",
                "cvss_score": row["cvss_score"],
                "severity": row["severity"],
                "published": row["published"],
                "epss_score": row["epss_score"],
            }
        )
        if len(out) >= limit:
            break
    return out




async def backfill_display_fields(db: aiosqlite.Connection) -> int:
    """Fill MITRE / PoC from stored NVD fields when missing (no auto plain-summary)."""
    from enrichment.cve import extract_mitre_from_urls, has_public_poc_from_urls

    rows = await db.execute_fetchall(
        """
        SELECT cve_id, description, source_urls, mitre_technique, has_poc
        FROM cves
        WHERE mitre_technique IS NULL OR has_poc = 0
        """
    )
    updated = 0
    for row in rows:
        urls = json.loads(row["source_urls"] or "[]")
        mitre = row["mitre_technique"] or extract_mitre_from_urls(urls)
        poc_flag = row["has_poc"]
        if not poc_flag:
            poc_flag = 1 if has_public_poc_from_urls(urls) else 0
        if not mitre and not poc_flag:
            continue
        await db.execute(
            """
            UPDATE cves
            SET mitre_technique = COALESCE(?, mitre_technique),
                has_poc = CASE WHEN ? = 1 THEN 1 ELSE has_poc END
            WHERE cve_id = ?
            """,
            (mitre, poc_flag, row["cve_id"]),
        )
        updated += 1
    return updated


async def strip_auto_generated_summaries(db: aiosqlite.Connection) -> int:
    """Remove NVD first-sentence summaries so Plain English filter is meaningful."""
    from enrichment.cve import is_auto_generated_summary

    rows = await db.execute_fetchall(
        """
        SELECT cve_id, description, summary
        FROM cves
        WHERE summary IS NOT NULL AND TRIM(summary) != ''
        """
    )
    cleared = 0
    for row in rows:
        if is_auto_generated_summary(row["summary"], row["description"]):
            await db.execute(
                "UPDATE cves SET summary = NULL WHERE cve_id = ?",
                (row["cve_id"],),
            )
            cleared += 1
    return cleared




async def backfill_has_poc(db: aiosqlite.Connection) -> int:
    """Set has_poc from stored reference URLs (no NVD re-fetch)."""
    from enrichment.cve import has_public_poc_from_urls

    rows = await db.execute_fetchall(
        "SELECT cve_id, source_urls FROM cves WHERE has_poc = 0"
    )
    updated = 0
    for row in rows:
        urls = json.loads(row["source_urls"] or "[]")
        if not has_public_poc_from_urls(urls):
            continue
        await db.execute(
            "UPDATE cves SET has_poc = 1 WHERE cve_id = ?",
            (row["cve_id"],),
        )
        updated += 1
    return updated

async def enrich_kev_summaries(db: aiosqlite.Connection) -> int:
    """Fill plain-English summary from CISA KEV short descriptions."""
    cursor = await db.execute(
        """
        UPDATE cves
        SET summary = (
            SELECT k.short_description
            FROM kev_deadlines k
            WHERE k.cve_id = cves.cve_id
              AND k.short_description IS NOT NULL
              AND k.short_description != ''
        )
        WHERE is_kev = 1
          AND (summary IS NULL OR summary = '')
          AND EXISTS (
            SELECT 1 FROM kev_deadlines k
            WHERE k.cve_id = cves.cve_id
              AND k.short_description IS NOT NULL
              AND k.short_description != ''
          )
        """
    )
    return cursor.rowcount


async def upsert_kev(db: aiosqlite.Connection, entry: dict) -> None:
    await db.execute(
        """
        INSERT INTO kev_deadlines (cve_id, product, short_description, required_action, due_date, date_added, updated_at)
        VALUES (:cve_id, :product, :short_description, :required_action, :due_date, :date_added, datetime('now'))
        ON CONFLICT(cve_id) DO UPDATE SET
            product = excluded.product,
            short_description = excluded.short_description,
            required_action = excluded.required_action,
            due_date = excluded.due_date,
            date_added = excluded.date_added,
            updated_at = datetime('now')
        """,
        {
            "cve_id": entry.get("cveID", ""),
            "product": entry.get("product", ""),
            "short_description": entry.get("shortDescription", ""),
            "required_action": entry.get("requiredAction", ""),
            "due_date": entry.get("dueDate", ""),
            "date_added": entry.get("dateAdded", ""),
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


async def get_feed_cache(
    db: aiosqlite.Connection, cache_key: str, max_age_hours: float
) -> dict | None:
    row = await db.execute_fetchall(
        """
        SELECT result FROM feed_cache
        WHERE cache_key = ?
          AND cached_at > datetime('now', ?)
        """,
        (cache_key, f"-{max_age_hours} hours"),
    )
    if row:
        return json.loads(row[0]["result"])
    return None


async def set_feed_cache(db: aiosqlite.Connection, cache_key: str, result: dict) -> None:
    await db.execute(
        """
        INSERT INTO feed_cache (cache_key, result, cached_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(cache_key) DO UPDATE SET
            result = excluded.result,
            cached_at = datetime('now')
        """,
        (cache_key, json.dumps(result)),
    )


async def get_cached_cve_exploits(
    db: aiosqlite.Connection, cve_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    cached = await get_feed_cache(db, f"sploitus:{cve_id.upper()}", max_age_hours)
    if cached is None:
        return None
    return cached.get("exploits", [])


async def store_cve_exploits(
    db: aiosqlite.Connection, cve_id: str, exploits: list[dict]
) -> None:
    await replace_cve_exploits(db, cve_id, exploits)
    await set_feed_cache(
        db,
        f"sploitus:{cve_id.upper()}",
        {"exploits": exploits},
    )


async def replace_cve_exploits(
    db: aiosqlite.Connection, cve_id: str, exploits: list[dict]
) -> None:
    key = cve_id.upper()
    await db.execute("DELETE FROM cve_exploits WHERE cve_id = ?", (key,))
    for exp in exploits:
        await db.execute(
            """
            INSERT INTO cve_exploits (
                cve_id, title, type, source, url, published_date, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                key,
                exp.get("title") or "",
                exp.get("type") or "poc",
                exp.get("source") or "",
                exp.get("url") or "",
                exp.get("published_date") or "",
            ),
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


async def get_all_cve_ids_set(db: aiosqlite.Connection) -> set[str]:
    rows = await db.execute_fetchall("SELECT cve_id FROM cves")
    return {r["cve_id"] for r in rows}


async def replace_mitre_techniques(db: aiosqlite.Connection, techniques: list[dict]) -> None:
    await db.execute("DELETE FROM mitre_techniques")
    if not techniques:
        return
    await db.executemany(
        """
        INSERT INTO mitre_techniques (
            technique_id, name, description, tactic, url, platforms
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                t["technique_id"],
                t["name"],
                t.get("description", ""),
                t.get("tactic", ""),
                t["url"],
                json.dumps(t.get("platforms", [])),
            )
            for t in techniques
        ],
    )


async def clear_cve_technique_map(db: aiosqlite.Connection) -> None:
    await db.execute("DELETE FROM cve_technique_map")


async def upsert_cve_technique_pairs(
    db: aiosqlite.Connection, pairs: list[tuple[str, str]], *, chunk_size: int = 5000
) -> int:
    if not pairs:
        return 0
    sql = """
        INSERT OR IGNORE INTO cve_technique_map (cve_id, technique_id)
        VALUES (?, ?)
    """
    for i in range(0, len(pairs), chunk_size):
        chunk = pairs[i : i + chunk_size]
        await db.executemany(sql, chunk)
    return len(pairs)


async def get_techniques_for_cve(db: aiosqlite.Connection, cve_id: str) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT m.technique_id, m.name, m.tactic, m.url, m.description
        FROM cve_technique_map c
        JOIN mitre_techniques m ON c.technique_id = m.technique_id
        WHERE c.cve_id = ?
        ORDER BY m.technique_id
        """,
        (cve_id.upper(),),
    )
    return [
        {
            "id": r["technique_id"],
            "name": r["name"],
            "tactic": r["tactic"],
            "url": r["url"],
            "description": (r["description"] or "").strip(),
        }
        for r in rows
    ]


async def get_top_techniques(db: aiosqlite.Connection, limit: int = 10) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT m.technique_id, m.name, m.tactic, m.url, COUNT(*) AS cnt
        FROM cve_technique_map c
        JOIN mitre_techniques m ON c.technique_id = m.technique_id
        GROUP BY m.technique_id, m.name, m.tactic, m.url
        ORDER BY cnt DESC, m.technique_id
        LIMIT ?
        """,
        (limit,),
    )
    return [
        {
            "technique_id": r["technique_id"],
            "name": r["name"],
            "tactic": r["tactic"],
            "count": r["cnt"],
            "url": r["url"],
        }
        for r in rows
    ]


async def get_mitre_technique_count(db: aiosqlite.Connection) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM mitre_techniques")
    return rows[0]["cnt"] if rows else 0


async def replace_atlas_techniques(db: aiosqlite.Connection, techniques: list[dict]) -> None:
    await db.execute("DELETE FROM atlas_techniques")
    if not techniques:
        return
    await db.executemany(
        """
        INSERT INTO atlas_techniques (
            technique_id, name, description, tactic, tactic_id, url
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                t["technique_id"],
                t["name"],
                t.get("description", ""),
                t.get("tactic", ""),
                t.get("tactic_id", ""),
                t["url"],
            )
            for t in techniques
        ],
    )


async def replace_atlas_case_studies(db: aiosqlite.Connection, studies: list[dict]) -> None:
    await db.execute("DELETE FROM atlas_case_studies")
    if not studies:
        return
    await db.executemany(
        """
        INSERT INTO atlas_case_studies (
            study_id, name, summary, summary_full, techniques,
            target, date, study_type, cve_ids
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                s["study_id"],
                s["name"],
                s.get("summary", ""),
                s.get("summary_full", ""),
                json.dumps(s.get("techniques", [])),
                s.get("target", ""),
                s.get("date", ""),
                s.get("study_type", ""),
                json.dumps(s.get("cve_ids", [])),
            )
            for s in studies
        ],
    )


async def get_atlas_technique_count(db: aiosqlite.Connection) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM atlas_techniques")
    return rows[0]["cnt"] if rows else 0


async def get_atlas_techniques_grouped(db: aiosqlite.Connection) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT technique_id, name, description, tactic, tactic_id, url
        FROM atlas_techniques
        ORDER BY tactic, technique_id
        """
    )
    groups: dict[str, dict] = {}
    for row in rows:
        tactic_name = row["tactic"] or "Uncategorized"
        tactic_id = row["tactic_id"] or tactic_name
        key = tactic_id
        if key not in groups:
            groups[key] = {
                "tactic_id": tactic_id,
                "tactic_name": tactic_name,
                "techniques": [],
            }
        groups[key]["techniques"].append(
            {
                "technique_id": row["technique_id"],
                "name": row["name"],
                "description": row["description"],
                "url": row["url"],
            }
        )
    return sorted(groups.values(), key=lambda g: g["tactic_name"])


def _parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


async def get_atlas_case_studies(
    db: aiosqlite.Connection, *, limit: int = 50
) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT study_id, name, summary, summary_full, techniques,
               target, date, study_type, cve_ids
        FROM atlas_case_studies
        ORDER BY date DESC, name
        LIMIT ?
        """,
        (limit,),
    )
    return [
        {
            "study_id": r["study_id"],
            "name": r["name"],
            "summary": r["summary"],
            "summary_full": r["summary_full"],
            "techniques": _parse_json_list(r["techniques"]),
            "target": r["target"],
            "date": r["date"],
            "study_type": r["study_type"],
            "cve_ids": _parse_json_list(r["cve_ids"]),
        }
        for r in rows
    ]

NVD_SYNC_WATERMARK_KEY = "nvd_last_mod_end"


async def get_nvd_sync_watermark(db: aiosqlite.Connection) -> str | None:
    rows = await db.execute_fetchall(
        "SELECT value FROM sync_state WHERE key = ?",
        (NVD_SYNC_WATERMARK_KEY,),
    )
    return rows[0]["value"] if rows else None


async def set_nvd_sync_watermark(db: aiosqlite.Connection, value: str) -> None:
    await db.execute(
        """
        INSERT INTO sync_state (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = datetime('now')
        """,
        (NVD_SYNC_WATERMARK_KEY, value),
    )


async def seed_nvd_watermark_from_cves(db: aiosqlite.Connection) -> str | None:
    rows = await db.execute_fetchall(
        """
        SELECT MAX(modified) AS latest
        FROM cves
        WHERE modified IS NOT NULL AND modified != ''
        """
    )
    latest = rows[0]["latest"] if rows else None
    if not latest:
        return None
    await set_nvd_sync_watermark(db, latest)
    return latest


async def resolve_nvd_watermark(db: aiosqlite.Connection, *, min_cves: int = 10) -> str | None:
    watermark = await get_nvd_sync_watermark(db)
    if watermark:
        return watermark
    count = await get_cve_count(db)
    if count < min_cves:
        return None
    return await seed_nvd_watermark_from_cves(db)

