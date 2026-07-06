"""OTX pulses/IOCs, correlation suppressions, prioritization, asset matching. Split from database.py (Phase 3)."""

import json
import asyncio
import aiosqlite
from db.dialect import utcnow_str

from db.cache import set_feed_cache
from db.metadata import _parse_json_list


async def upsert_otx_pulses(
    db: aiosqlite.Connection, pulses: list[dict]
) -> None:
    """Upsert pulse dimension rows (caller commits)."""
    if not pulses:
        return
    await db.executemany(
        """
        INSERT INTO otx_pulses (
            pulse_id, pulse_name, author, created_date, adversary,
            malware_families, tags, targeted_countries, ioc_count, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pulse_id) DO UPDATE SET
            pulse_name = excluded.pulse_name,
            author = excluded.author,
            created_date = excluded.created_date,
            adversary = excluded.adversary,
            malware_families = excluded.malware_families,
            tags = excluded.tags,
            targeted_countries = excluded.targeted_countries,
            ioc_count = excluded.ioc_count,
            fetched_at = excluded.fetched_at
        """,
        [
            (
                p.get("pulse_id") or "",
                p.get("pulse_name") or "",
                p.get("author") or "",
                p.get("created_date") or "",
                p.get("adversary") or "",
                json.dumps(p.get("malware_families") or []),
                json.dumps(p.get("tags") or []),
                json.dumps(p.get("targeted_countries") or []),
                int(p.get("ioc_count") or 0),
                utcnow_str(),
            )
            for p in pulses
            if p.get("pulse_id")
        ],
    )

async def replace_otx_cve_pulses(
    db: aiosqlite.Connection, cve_id: str, pulses: list[dict]
) -> None:
    key = cve_id.upper()
    await db.execute("DELETE FROM otx_cve_pulses WHERE cve_id = ?", (key,))
    if pulses:
        await upsert_otx_pulses(db, pulses)
        await db.executemany(
            """
            INSERT INTO otx_cve_pulses (
                cve_id, pulse_id, pulse_name, author, created_date,
                adversary, malware_families, ioc_count, tags, targeted_countries,
                fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    key,
                    p.get("pulse_id") or "",
                    p.get("pulse_name") or "",
                    p.get("author") or "",
                    p.get("created_date") or "",
                    p.get("adversary") or "",
                    json.dumps(p.get("malware_families") or []),
                    int(p.get("ioc_count") or 0),
                    json.dumps(p.get("tags") or []),
                    json.dumps(p.get("targeted_countries") or []),
                    utcnow_str(),
                )
                for p in pulses
                if p.get("pulse_id")
            ],
        )

async def store_otx_cve_pulses(
    db: aiosqlite.Connection, cve_id: str, pulses: list[dict]
) -> None:
    key = cve_id.upper()
    await replace_otx_cve_pulses(db, key, pulses)
    await set_feed_cache(db, f"otx:cve:{key}", {"pulses": pulses})

async def read_otx_cve_pulses(
    db: aiosqlite.Connection, cve_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    rows = await db.execute_fetchall(
        """
        SELECT pulse_id, pulse_name, author, created_date, adversary,
               malware_families, ioc_count, tags, targeted_countries
        FROM otx_cve_pulses
        WHERE cve_id = ?
          AND fetched_at > datetime('now', ?)
        ORDER BY created_date DESC
        """,
        (cve_id.upper(), f"-{max_age_hours} hours"),
    )
    if not rows:
        return None
    return [
        {
            "pulse_id": row["pulse_id"],
            "pulse_name": row["pulse_name"],
            "author": row["author"],
            "created_date": row["created_date"],
            "adversary": row["adversary"],
            "malware_families": json.loads(row["malware_families"] or "[]"),
            "ioc_count": row["ioc_count"],
            "tags": json.loads(row["tags"] or "[]"),
            "targeted_countries": json.loads(row["targeted_countries"] or "[]"),
        }
        for row in rows
    ]

_NUM_IOC_LOCKS = 64

_pulse_ioc_locks = [asyncio.Lock() for _ in range(_NUM_IOC_LOCKS)]

def _pulse_ioc_lock(pulse_id: str) -> asyncio.Lock:
    """Fixed-size lock pool — avoids unbounded growth from per-pulse lock dicts."""
    return _pulse_ioc_locks[hash(pulse_id) % _NUM_IOC_LOCKS]

async def replace_otx_pulse_iocs(
    db: aiosqlite.Connection, pulse_id: str, iocs: list[dict]
) -> None:
    from correlation.ioc_normalize import normalize_ioc_row

    normalized_rows: list[tuple] = []
    for row in iocs:
        norm = normalize_ioc_row(row)
        if norm is None:
            continue
        normalized_rows.append(
            (
                pulse_id,
                norm.get("ioc_type") or "",
                norm.get("ioc_value") or "",
                norm.get("description") or "",
                utcnow_str(),
            )
        )
    if not normalized_rows:
        await db.execute("DELETE FROM otx_pulse_iocs WHERE pulse_id = ?", (pulse_id,))
        return
    new_keys = {(row[1], row[2]) for row in normalized_rows}
    await db.executemany(
        """
        INSERT INTO otx_pulse_iocs (
            pulse_id, ioc_type, ioc_value, description, fetched_at
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(pulse_id, ioc_type, ioc_value) DO UPDATE SET
            description = excluded.description,
            fetched_at = excluded.fetched_at
        """,
        normalized_rows,
    )
    existing = await db.execute_fetchall(
        """
        SELECT ioc_type, ioc_value
        FROM otx_pulse_iocs
        WHERE pulse_id = ?
        """,
        (pulse_id,),
    )
    stale = [
        (pulse_id, row["ioc_type"], row["ioc_value"])
        for row in existing
        if (row["ioc_type"], row["ioc_value"]) not in new_keys
    ]
    if stale:
        await db.executemany(
            """
            DELETE FROM otx_pulse_iocs
            WHERE pulse_id = ? AND ioc_type = ? AND ioc_value = ?
            """,
            stale,
        )

async def store_otx_pulse_iocs(
    db: aiosqlite.Connection, pulse_id: str, iocs: list[dict]
) -> None:
    async with _pulse_ioc_lock(pulse_id):
        await replace_otx_pulse_iocs(db, pulse_id, iocs)
        await set_feed_cache(db, f"otx:pulse:{pulse_id}", {"iocs": iocs})

async def read_otx_pulse_iocs(
    db: aiosqlite.Connection, pulse_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    rows = await db.execute_fetchall(
        """
        SELECT ioc_type, ioc_value, description
        FROM otx_pulse_iocs
        WHERE pulse_id = ?
          AND fetched_at > datetime('now', ?)
        """,
        (pulse_id, f"-{max_age_hours} hours"),
    )
    if not rows:
        return None
    return [
        {
            "ioc_type": row["ioc_type"],
            "ioc_value": row["ioc_value"],
            "description": row["description"],
        }
        for row in rows
    ]

async def list_correlation_suppressions(
    db: aiosqlite.Connection, cve_id: str
) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT id, cve_id, scope, scope_key, reason, dismissed_by, created_at
        FROM correlation_suppressions
        WHERE cve_id = ?
        ORDER BY created_at DESC
        """,
        (cve_id.upper(),),
    )
    return [dict(row) for row in rows]

async def insert_correlation_suppression(
    db: aiosqlite.Connection,
    cve_id: str,
    scope: str,
    scope_key: str,
    reason: str = "",
    dismissed_by: str = "",
) -> dict:
    await db.execute(
        """
        INSERT INTO correlation_suppressions (cve_id, scope, scope_key, reason, dismissed_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(cve_id, scope, scope_key) DO UPDATE SET
            reason = excluded.reason,
            dismissed_by = excluded.dismissed_by,
            created_at = excluded.created_at
        """,
        (cve_id.upper(), scope, scope_key, reason, dismissed_by, utcnow_str()),
    )
    rows = await db.execute_fetchall(
        """
        SELECT id, cve_id, scope, scope_key, reason, dismissed_by, created_at
        FROM correlation_suppressions
        WHERE cve_id = ? AND scope = ? AND scope_key = ?
        """,
        (cve_id.upper(), scope, scope_key),
    )
    return dict(rows[0]) if rows else {
        "cve_id": cve_id.upper(),
        "scope": scope,
        "scope_key": scope_key,
        "reason": reason,
        "dismissed_by": dismissed_by,
    }

async def delete_correlation_suppression(
    db: aiosqlite.Connection, cve_id: str, scope: str, scope_key: str
) -> bool:
    cursor = await db.execute(
        """
        DELETE FROM correlation_suppressions
        WHERE cve_id = ? AND scope = ? AND scope_key = ?
        """,
        (cve_id.upper(), scope, scope_key),
    )
    return (cursor.rowcount or 0) > 0

async def get_recent_cve_ids_for_otx(
    db: aiosqlite.Connection, days: int = 7
) -> list[str]:
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = await db.execute_fetchall(
        """
        SELECT cve_id FROM cves
        WHERE published IS NOT NULL
          AND published != ''
          AND published >= ?
        ORDER BY published DESC
        """,
        (cutoff,),
    )
    return [row["cve_id"] for row in rows]

async def get_cves_missing_otx_pulses(
    db: aiosqlite.Connection, limit: int = 200
) -> list[str]:
    """CVEs with no OTX pulse rows yet, tier-prioritized for continuous sync."""
    prioritized = await get_prioritized_cve_ids_for_otx(db, backlog_cap=limit * 2)
    if not prioritized:
        return []

    missing: list[str] = []
    chunk = 100
    for i in range(0, len(prioritized), chunk):
        batch = prioritized[i : i + chunk]
        placeholders = ",".join("?" for _ in batch)
        rows = await db.execute_fetchall(
            f"""
            SELECT c.cve_id
            FROM cves c
            WHERE c.cve_id IN ({placeholders})
              AND NOT EXISTS (
                SELECT 1 FROM otx_cve_pulses o WHERE o.cve_id = c.cve_id
              )
            """,
            tuple(batch),
        )
        have = {row["cve_id"] for row in rows}
        for cid in batch:
            if cid in have:
                missing.append(cid)
            if len(missing) >= limit:
                return missing
    return missing

async def get_embedding_boosted_cve_ids_for_otx(
    db: aiosqlite.Connection, limit: int = 150
) -> list[dict]:
    """
    CVEs semantically similar to KEV/watchlist anchors that lack OTX pulses.
    Used as P1b tier when EMBEDDINGS_ENABLED=1.
    """
    from ml.embeddings import embeddings_enabled, find_similar_cves

    if not embeddings_enabled() or limit <= 0:
        return []

    anchors = await db.execute_fetchall(
        """
        SELECT c.cve_id
        FROM cves c
        LEFT JOIN watchlist w ON w.cve_id = c.cve_id AND w.state = 'pin'
        WHERE COALESCE(c.is_kev, 0) = 1 OR w.cve_id IS NOT NULL
        ORDER BY COALESCE(c.epss_score, 0) DESC
        LIMIT 15
        """
    )
    if not anchors:
        return []

    candidates: list[str] = []
    seen: set[str] = set()
    for row in anchors:
        anchor_id = row["cve_id"]
        similar = await find_similar_cves(db, anchor_id, limit=20)
        if not similar:
            continue
        for item in similar:
            cid = item.get("cve_id")
            if cid and cid not in seen:
                seen.add(cid)
                candidates.append(cid)

    if not candidates:
        return []

    placeholders = ",".join("?" for _ in candidates)
    rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id
        FROM cves c
        WHERE c.cve_id IN ({placeholders})
          AND NOT EXISTS (
            SELECT 1 FROM otx_cve_pulses o WHERE o.cve_id = c.cve_id
          )
        """,
        tuple(candidates),
    )
    missing_set = {row["cve_id"] for row in rows}
    ordered = [cid for cid in candidates if cid in missing_set]
    return [{"cve_id": c} for c in ordered[:limit]]

async def get_prioritized_cve_ids_for_otx(
    db: aiosqlite.Connection,
    days: int | None = None,
    backlog_cap: int = 200,
) -> list[str]:
    """
    Tiered CVE set for OTX pulse refresh (P0 → P3).
    P0: KEV or watchlisted. P1: high EPSS, PoC, or changed in 7d.
    P2: published within sync window. P3: backlog cap by recency.
    """
    from correlation.config import get_otx_cve_sync_days

    window_days = days if days is not None else get_otx_cve_sync_days()
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(rows: list) -> None:
        for row in rows:
            cid = row["cve_id"]
            if cid not in seen:
                seen.add(cid)
                ordered.append(cid)

    p0 = await db.execute_fetchall(
        """
        SELECT c.cve_id
        FROM cves c
        LEFT JOIN watchlist w ON w.cve_id = c.cve_id AND w.state = 'pin'
        WHERE COALESCE(c.is_kev, 0) = 1 OR w.cve_id IS NOT NULL
        ORDER BY c.published DESC
        """
    )
    _add(p0)

    p1 = await db.execute_fetchall(
        """
        SELECT c.cve_id
        FROM cves c
        WHERE (
            COALESCE(c.epss_score, 0) >= 0.5
            OR COALESCE(c.has_poc, 0) = 1
            OR datetime(c.modified) >= datetime('now', '-7 days')
        )
        ORDER BY COALESCE(c.epss_score, 0) DESC, c.published DESC
        LIMIT 500
        """
    )
    _add(p1)

    try:
        from ml.embeddings import embeddings_enabled

        if embeddings_enabled():
            p1b = await get_embedding_boosted_cve_ids_for_otx(db, limit=150)
            _add(p1b)
    except Exception:
        pass

    p2 = await db.execute_fetchall(
        """
        SELECT cve_id FROM cves
        WHERE DATE(published) >= DATE('now', ?)
        ORDER BY published DESC
        """,
        (f"-{window_days} days",),
    )
    _add(p2)

    if len(ordered) < backlog_cap:
        p3 = await db.execute_fetchall(
            """
            SELECT cve_id FROM cves
            ORDER BY published DESC
            LIMIT ?
            """,
            (backlog_cap,),
        )
        _add(p3)

    return ordered[:backlog_cap] if backlog_cap > 0 else ordered

async def match_cves_for_assets(
    db: aiosqlite.Connection, assets: list[dict]
) -> dict[str, int]:
    """Score every CVE in the database against analyst assets (in-memory request only)."""
    from matching.cpe import score_cve_for_assets

    rows = await db.execute_fetchall(
        "SELECT cve_id, cpe_matches, affected_products FROM cves"
    )
    scores: dict[str, int] = {}
    for row in rows:
        cpe_matches = _parse_json_list(row["cpe_matches"])
        if not cpe_matches:
            for entry in _parse_json_list(row["affected_products"]):
                if isinstance(entry, str) and ":" in entry:
                    vendor, product = entry.split(":", 1)
                    cpe_matches.append({"vendor": vendor, "product": product})

        score = score_cve_for_assets(cpe_matches, assets)
        if score > 0:
            scores[row["cve_id"]] = score
    return scores
