"""MITRE ATT&CK/ATLAS technique + case-study metadata, AI/ML context, analytics. Split from database.py (Phase 3).

Postgres-native (Post-B Phase 1): queries use explicit ``$n`` placeholders on Postgres
and ``?`` on SQLite — no reliance on ``db/dialect.py`` regex translation for this module.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from db.types import DbConnection

_COUNT_CVES_SQL = "SELECT COUNT(*) as cnt FROM cves"

_TIMELINE_ACTIVITY_SQLITE = """
SELECT DATE(published) AS day, COUNT(*) AS count
FROM cves
WHERE published IS NOT NULL
  AND published != ''
  AND DATE(published) >= ?
GROUP BY DATE(published)
"""

_TIMELINE_ACTIVITY_PG = """
SELECT published::date AS day, COUNT(*) AS count
FROM cves
WHERE published IS NOT NULL
  AND published != ''
  AND published >= $1
GROUP BY published::date
"""

_MAX_UPDATED_SQL = "SELECT MAX(updated_at) as ts FROM cves"

_SELECT_ALL_CVE_IDS_SQL = "SELECT cve_id FROM cves"

_DELETE_MITRE_TECHNIQUES_SQL = "DELETE FROM mitre_techniques"

_INSERT_MITRE_TECHNIQUE_SQLITE = """
INSERT INTO mitre_techniques (
    technique_id, name, description, tactic, url, platforms, detection
) VALUES (?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_MITRE_TECHNIQUE_PG = """
INSERT INTO mitre_techniques (
    technique_id, name, description, tactic, url, platforms, detection
) VALUES ($1, $2, $3, $4, $5, $6, $7)
"""

_DELETE_CVE_TECHNIQUE_MAP_SQL = "DELETE FROM cve_technique_map"

_INSERT_CVE_TECHNIQUE_PAIR_SQLITE = """
INSERT OR IGNORE INTO cve_technique_map (cve_id, technique_id)
VALUES (?, ?)
"""

_INSERT_CVE_TECHNIQUE_PAIR_PG = """
INSERT INTO cve_technique_map (cve_id, technique_id)
VALUES ($1, $2)
ON CONFLICT (cve_id, technique_id) DO NOTHING
"""

_TECHNIQUES_FOR_CVE_SQLITE = """
SELECT m.technique_id, m.name, m.tactic, m.url, m.description, m.detection
FROM cve_technique_map c
JOIN mitre_techniques m ON c.technique_id = m.technique_id
WHERE c.cve_id = ?
ORDER BY m.technique_id
"""

_TECHNIQUES_FOR_CVE_PG = """
SELECT m.technique_id, m.name, m.tactic, m.url, m.description, m.detection
FROM cve_technique_map c
JOIN mitre_techniques m ON c.technique_id = m.technique_id
WHERE c.cve_id = $1
ORDER BY m.technique_id
"""

_TOP_TECHNIQUES_SQLITE = """
SELECT m.technique_id, m.name, m.tactic, m.url, COUNT(*) AS cnt
FROM cve_technique_map c
JOIN mitre_techniques m ON c.technique_id = m.technique_id
GROUP BY m.technique_id, m.name, m.tactic, m.url
ORDER BY cnt DESC, m.technique_id
LIMIT ?
"""

_TOP_TECHNIQUES_PG = """
SELECT m.technique_id, m.name, m.tactic, m.url, COUNT(*) AS cnt
FROM cve_technique_map c
JOIN mitre_techniques m ON c.technique_id = m.technique_id
GROUP BY m.technique_id, m.name, m.tactic, m.url
ORDER BY cnt DESC, m.technique_id
LIMIT $1
"""

_COUNT_MITRE_TECHNIQUES_SQL = "SELECT COUNT(*) AS cnt FROM mitre_techniques"

_UPSERT_ATLAS_TECHNIQUE_SQLITE = """
INSERT INTO atlas_techniques (
    technique_id, name, description, tactic, tactic_id, url
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(technique_id) DO UPDATE SET
    name = excluded.name,
    description = excluded.description,
    tactic = excluded.tactic,
    tactic_id = excluded.tactic_id,
    url = excluded.url
"""

_UPSERT_ATLAS_TECHNIQUE_PG = """
INSERT INTO atlas_techniques (
    technique_id, name, description, tactic, tactic_id, url
) VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT(technique_id) DO UPDATE SET
    name = excluded.name,
    description = excluded.description,
    tactic = excluded.tactic,
    tactic_id = excluded.tactic_id,
    url = excluded.url
"""

_DELETE_ATLAS_CASE_STUDIES_SQL = "DELETE FROM atlas_case_studies"

_INSERT_ATLAS_CASE_STUDY_SQLITE = """
INSERT INTO atlas_case_studies (
    study_id, name, summary, summary_full, techniques,
    target, date, study_type, cve_ids
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_ATLAS_CASE_STUDY_PG = """
INSERT INTO atlas_case_studies (
    study_id, name, summary, summary_full, techniques,
    target, date, study_type, cve_ids
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
"""

_COUNT_ATLAS_TECHNIQUES_SQL = "SELECT COUNT(*) AS cnt FROM atlas_techniques"

_ATLAS_TECHNIQUES_GROUPED_SQL = """
SELECT technique_id, name, description, tactic, tactic_id, url
FROM atlas_techniques
ORDER BY tactic, technique_id
"""

_ATLAS_CASE_STUDIES_SQLITE = """
SELECT study_id, name, summary, summary_full, techniques,
       target, date, study_type, cve_ids
FROM atlas_case_studies
ORDER BY date DESC, name
LIMIT ?
"""

_ATLAS_CASE_STUDIES_PG = """
SELECT study_id, name, summary, summary_full, techniques,
       target, date, study_type, cve_ids
FROM atlas_case_studies
ORDER BY date DESC, name
LIMIT $1
"""

_DELETE_CVE_ATLAS_MAP_SQL = "DELETE FROM cve_atlas_map"

_INSERT_CVE_ATLAS_PAIR_SQLITE = """
INSERT OR IGNORE INTO cve_atlas_map (cve_id, technique_id)
VALUES (?, ?)
"""

_INSERT_CVE_ATLAS_PAIR_PG = """
INSERT INTO cve_atlas_map (cve_id, technique_id)
VALUES ($1, $2)
ON CONFLICT (cve_id, technique_id) DO NOTHING
"""

_DELETE_CVE_ATLAS_MAP_FOR_CVE_SQLITE = "DELETE FROM cve_atlas_map WHERE cve_id = ?"
_DELETE_CVE_ATLAS_MAP_FOR_CVE_PG = "DELETE FROM cve_atlas_map WHERE cve_id = $1"

_ATLAS_TECHNIQUES_FOR_CVE_SQLITE = """
SELECT t.technique_id, t.name, t.description, t.tactic, t.url
FROM cve_atlas_map m
JOIN atlas_techniques t ON t.technique_id = m.technique_id
WHERE m.cve_id = ?
ORDER BY t.technique_id
"""

_ATLAS_TECHNIQUES_FOR_CVE_PG = """
SELECT t.technique_id, t.name, t.description, t.tactic, t.url
FROM cve_atlas_map m
JOIN atlas_techniques t ON t.technique_id = m.technique_id
WHERE m.cve_id = $1
ORDER BY t.technique_id
"""

_ATLAS_CASE_STUDIES_FOR_CVE_SQLITE = """
SELECT study_id, name, summary, techniques, target, date, cve_ids
FROM atlas_case_studies
WHERE cve_ids LIKE ?
ORDER BY date DESC, name
LIMIT ?
"""

_ATLAS_CASE_STUDIES_FOR_CVE_PG = """
SELECT study_id, name, summary, techniques, target, date, cve_ids
FROM atlas_case_studies
WHERE cve_ids LIKE $1
ORDER BY date DESC, name
LIMIT $2
"""

_AI_ML_PROFILE_CVES_SQL = """
SELECT cve_id, description, affected_products
FROM cves
WHERE has_ai_context = 1
"""

_REFRESH_CVE_ROWS_SQL = """
SELECT cve_id, description, affected_products
FROM cves
"""

_SELECT_ATLAS_TECHNIQUE_IDS_SQL = "SELECT technique_id FROM atlas_techniques"

_UPDATE_HAS_AI_CONTEXT_SQLITE = "UPDATE cves SET has_ai_context = ? WHERE cve_id = ?"
_UPDATE_HAS_AI_CONTEXT_PG = "UPDATE cves SET has_ai_context = $1 WHERE cve_id = $2"

_REPLACE_MITRE_GROUPS_SQLITE = """
INSERT INTO mitre_groups (group_id, name, aliases, description, sectors, url)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(group_id) DO UPDATE SET
    name        = excluded.name,
    aliases     = excluded.aliases,
    description = excluded.description,
    sectors     = excluded.sectors,
    url         = excluded.url
"""

_REPLACE_MITRE_GROUPS_PG = """
INSERT INTO mitre_groups (group_id, name, aliases, description, sectors, url)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT(group_id) DO UPDATE SET
    name        = excluded.name,
    aliases     = excluded.aliases,
    description = excluded.description,
    sectors     = excluded.sectors,
    url         = excluded.url
"""

_INSERT_GROUP_TECHNIQUE_PAIR_SQLITE = """
INSERT OR IGNORE INTO group_technique_map (group_id, technique_id)
VALUES (?, ?)
"""

_INSERT_GROUP_TECHNIQUE_PAIR_PG = """
INSERT INTO group_technique_map (group_id, technique_id)
VALUES ($1, $2)
ON CONFLICT (group_id, technique_id) DO NOTHING
"""

_COUNT_MITRE_GROUPS_SQL = "SELECT COUNT(*) AS cnt FROM mitre_groups"


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _in_placeholders(count: int, *, pg: bool, start: int = 1) -> str:
    if pg:
        return ", ".join(f"${i}" for i in range(start, start + count))
    return ", ".join("?" for _ in range(count))


def _cutoff_date_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()


async def get_cve_count(db: DbConnection) -> int:
    rows = await db.execute_fetchall(_COUNT_CVES_SQL)
    return rows[0]["cnt"] if rows else 0


async def get_timeline_activity_summary(db: DbConnection, *, days: int = 90) -> dict:
    """Days with at least one published CVE in the last N UTC calendar days."""
    window = max(1, min(int(days), 365))
    cutoff = _cutoff_date_days_ago(window - 1)
    sql = _TIMELINE_ACTIVITY_PG if _is_postgres_connection(db) else _TIMELINE_ACTIVITY_SQLITE
    rows = await db.execute_fetchall(sql, (cutoff,))
    days_with_data = sum(1 for r in rows if (r["count"] or 0) > 0)
    total_cves = sum(int(r["count"] or 0) for r in rows)
    return {
        "days_with_data": days_with_data,
        "total_cves": total_cves,
        "window_days": window,
    }


async def get_last_updated(db: DbConnection) -> str | None:
    rows = await db.execute_fetchall(_MAX_UPDATED_SQL)
    return rows[0]["ts"] if rows else None


async def get_all_cve_ids(db: DbConnection) -> list:
    rows = await db.execute_fetchall(_SELECT_ALL_CVE_IDS_SQL)
    return [r["cve_id"] for r in rows]


async def get_all_cve_ids_set(db: DbConnection) -> set[str]:
    rows = await db.execute_fetchall(_SELECT_ALL_CVE_IDS_SQL)
    return {r["cve_id"] for r in rows}


async def replace_mitre_techniques(db: DbConnection, techniques: list[dict]) -> None:
    await db.execute(_DELETE_MITRE_TECHNIQUES_SQL)
    if not techniques:
        return
    sql = (
        _INSERT_MITRE_TECHNIQUE_PG
        if _is_postgres_connection(db)
        else _INSERT_MITRE_TECHNIQUE_SQLITE
    )
    await db.executemany(
        sql,
        [
            (
                t["technique_id"],
                t["name"],
                t.get("description", ""),
                t.get("tactic", ""),
                t["url"],
                json.dumps(t.get("platforms", [])),
                t.get("detection", ""),
            )
            for t in techniques
        ],
    )


async def clear_cve_technique_map(db: DbConnection) -> None:
    await db.execute(_DELETE_CVE_TECHNIQUE_MAP_SQL)


async def upsert_cve_technique_pairs(
    db: DbConnection, pairs: list[tuple[str, str]], *, chunk_size: int = 5000
) -> int:
    if not pairs:
        return 0
    sql = (
        _INSERT_CVE_TECHNIQUE_PAIR_PG
        if _is_postgres_connection(db)
        else _INSERT_CVE_TECHNIQUE_PAIR_SQLITE
    )
    for i in range(0, len(pairs), chunk_size):
        chunk = pairs[i : i + chunk_size]
        await db.executemany(sql, chunk)
    return len(pairs)


async def get_techniques_for_cve(db: DbConnection, cve_id: str) -> list[dict]:
    sql = _TECHNIQUES_FOR_CVE_PG if _is_postgres_connection(db) else _TECHNIQUES_FOR_CVE_SQLITE
    rows = await db.execute_fetchall(sql, (cve_id.upper(),))
    return [
        {
            "id": r["technique_id"],
            "name": r["name"],
            "tactic": r["tactic"],
            "url": r["url"],
            "detection": (r["detection"] or "").strip(),
            "description": (r["description"] or "").strip(),
        }
        for r in rows
    ]


async def get_top_techniques(db: DbConnection, limit: int = 10) -> list[dict]:
    sql = _TOP_TECHNIQUES_PG if _is_postgres_connection(db) else _TOP_TECHNIQUES_SQLITE
    rows = await db.execute_fetchall(sql, (limit,))
    return [
        {
            "technique_id": r["technique_id"],
            "name": r["name"],
            "tactic": r["tactic"],
            "cve_count": r["cnt"],
            "count": r["cnt"],
            "url": r["url"],
        }
        for r in rows
    ]


async def get_mitre_technique_count(db: DbConnection) -> int:
    rows = await db.execute_fetchall(_COUNT_MITRE_TECHNIQUES_SQL)
    return rows[0]["cnt"] if rows else 0


async def replace_atlas_techniques(db: DbConnection, techniques: list[dict]) -> None:
    incoming_ids = [t["technique_id"] for t in techniques]
    pg = _is_postgres_connection(db)
    if incoming_ids:
        placeholders = _in_placeholders(len(incoming_ids), pg=pg, start=1)
        params = tuple(incoming_ids)
        await db.execute(
            f"DELETE FROM cve_atlas_map WHERE technique_id NOT IN ({placeholders})",
            params,
        )
        await db.execute(
            f"DELETE FROM atlas_techniques WHERE technique_id NOT IN ({placeholders})",
            params,
        )
    else:
        await db.execute(_DELETE_CVE_ATLAS_MAP_SQL)
        await db.execute("DELETE FROM atlas_techniques")
    if not techniques:
        return
    sql = _UPSERT_ATLAS_TECHNIQUE_PG if pg else _UPSERT_ATLAS_TECHNIQUE_SQLITE
    await db.executemany(
        sql,
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


async def replace_atlas_case_studies(db: DbConnection, studies: list[dict]) -> None:
    await db.execute(_DELETE_ATLAS_CASE_STUDIES_SQL)
    if not studies:
        return
    sql = (
        _INSERT_ATLAS_CASE_STUDY_PG
        if _is_postgres_connection(db)
        else _INSERT_ATLAS_CASE_STUDY_SQLITE
    )
    await db.executemany(
        sql,
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


async def get_atlas_technique_count(db: DbConnection) -> int:
    rows = await db.execute_fetchall(_COUNT_ATLAS_TECHNIQUES_SQL)
    return rows[0]["cnt"] if rows else 0


async def get_atlas_techniques_grouped(db: DbConnection) -> list[dict]:
    rows = await db.execute_fetchall(_ATLAS_TECHNIQUES_GROUPED_SQL)
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
    db: DbConnection, *, limit: int = 50
) -> list[dict]:
    sql = _ATLAS_CASE_STUDIES_PG if _is_postgres_connection(db) else _ATLAS_CASE_STUDIES_SQLITE
    rows = await db.execute_fetchall(sql, (limit,))
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


async def clear_cve_atlas_map(db: DbConnection) -> None:
    await db.execute(_DELETE_CVE_ATLAS_MAP_SQL)


async def upsert_cve_atlas_pairs(
    db: DbConnection, pairs: list[tuple[str, str]]
) -> int:
    if not pairs:
        return 0
    sql = (
        _INSERT_CVE_ATLAS_PAIR_PG
        if _is_postgres_connection(db)
        else _INSERT_CVE_ATLAS_PAIR_SQLITE
    )
    await db.executemany(sql, pairs)
    return len(pairs)


async def replace_cve_atlas_map_for_cve(
    db: DbConnection, cve_id: str, technique_ids: list[str]
) -> None:
    cve_key = cve_id.upper()
    delete_sql = (
        _DELETE_CVE_ATLAS_MAP_FOR_CVE_PG
        if _is_postgres_connection(db)
        else _DELETE_CVE_ATLAS_MAP_FOR_CVE_SQLITE
    )
    await db.execute(delete_sql, (cve_key,))
    if technique_ids:
        await upsert_cve_atlas_pairs(
            db, [(cve_key, tid.upper()) for tid in technique_ids if tid]
        )


async def get_atlas_techniques_for_cve(
    db: DbConnection, cve_id: str
) -> list[dict]:
    sql = (
        _ATLAS_TECHNIQUES_FOR_CVE_PG
        if _is_postgres_connection(db)
        else _ATLAS_TECHNIQUES_FOR_CVE_SQLITE
    )
    rows = await db.execute_fetchall(sql, (cve_id.upper(),))
    return [
        {
            "technique_id": r["technique_id"],
            "id": r["technique_id"],
            "name": r["name"],
            "description": r["description"],
            "tactic": r["tactic"],
            "url": r["url"],
        }
        for r in rows
    ]


async def get_atlas_case_studies_for_cve(
    db: DbConnection, cve_id: str, *, limit: int = 2
) -> list[dict]:
    cve_key = cve_id.upper()
    sql = (
        _ATLAS_CASE_STUDIES_FOR_CVE_PG
        if _is_postgres_connection(db)
        else _ATLAS_CASE_STUDIES_FOR_CVE_SQLITE
    )
    rows = await db.execute_fetchall(sql, (f'%"{cve_key}"%', limit))
    return [
        {
            "study_id": row["study_id"],
            "name": row["name"],
            "summary": row["summary"],
            "techniques": _parse_json_list(row["techniques"]),
            "target": row["target"],
            "incident_date": row["date"],
        }
        for row in rows
    ]


# ── Forge case-study cross-links (forge-redesign.md §4/FR-3) ──────────
#
# atlas_case_studies (MITRE ATLAS — AI/ML threats) and mitre_techniques
# (MITRE ATT&CK Enterprise — Forge's coverage map) are separate taxonomies;
# a case study's own `techniques` list is ATLAS technique IDs, not ATT&CK
# ones. The only shared key is the CVE: a case study references cve_ids,
# and cve_technique_map links the same CVEs to ATT&CK technique_ids. Both
# helpers below join through that shared CVE set, in Python — the ATLAS
# case-study table is small (MITRE's bundle, not a live feed), so this
# avoids per-technique round trips (an N+1 across ~100+ coverage rows).

async def get_case_study_counts_by_technique(db: DbConnection) -> dict[str, int]:
    """Distinct case-study count per ATT&CK technique_id, for the Forge
    coverage map's "Case studies (n)" chip (forge-redesign.md §4)."""
    study_rows = await db.execute_fetchall(
        "SELECT study_id, cve_ids FROM atlas_case_studies"
    )
    studies_by_cve: dict[str, set[str]] = {}
    for row in study_rows:
        for cve_id in _parse_json_list(row["cve_ids"]):
            studies_by_cve.setdefault(str(cve_id).upper(), set()).add(row["study_id"])
    if not studies_by_cve:
        return {}

    map_rows = await db.execute_fetchall(
        "SELECT technique_id, cve_id FROM cve_technique_map"
    )
    counts: dict[str, set[str]] = {}
    for row in map_rows:
        study_ids = studies_by_cve.get((row["cve_id"] or "").upper())
        if not study_ids:
            continue
        counts.setdefault(row["technique_id"], set()).update(study_ids)
    return {tid: len(ids) for tid, ids in counts.items()}


async def get_case_studies_for_technique(
    db: DbConnection, technique_id: str, *, limit: int = 5
) -> list[dict]:
    """Case studies for one ATT&CK technique (via shared CVEs), for the Hunt
    Pack rail's case-study section."""
    cve_rows = await db.execute_fetchall(
        "SELECT DISTINCT cve_id FROM cve_technique_map WHERE technique_id = ?",
        (technique_id,),
    )
    cve_ids = {(row["cve_id"] or "").upper() for row in cve_rows if row["cve_id"]}
    if not cve_ids:
        return []

    study_rows = await db.execute_fetchall(
        "SELECT study_id, name, summary, target, date, cve_ids FROM atlas_case_studies"
    )
    seen: set[str] = set()
    out: list[dict] = []
    for row in study_rows:
        if row["study_id"] in seen:
            continue
        study_cves = {str(c).upper() for c in _parse_json_list(row["cve_ids"])}
        if not (study_cves & cve_ids):
            continue
        seen.add(row["study_id"])
        out.append({
            "study_id": row["study_id"],
            "name": row["name"],
            "summary": row["summary"],
            "target": row["target"],
            "incident_date": row["date"],
        })
        if len(out) >= limit:
            break
    return out


async def count_ai_ml_profile_alerts(
    db: DbConnection, frameworks: list[str]
) -> int:
    if not frameworks:
        return 0
    rows = await db.execute_fetchall(_AI_ML_PROFILE_CVES_SQL)
    from feeds.ai_context import cve_matches_declared_frameworks

    count = 0
    for row in rows:
        cve = {
            "description": row["description"],
            "affected_products": _parse_json_list(row["affected_products"])
            if isinstance(row["affected_products"], str)
            else row["affected_products"],
        }
        if cve_matches_declared_frameworks(cve, frameworks):
            count += 1
    return count


async def refresh_all_cve_ai_context(db: DbConnection) -> dict[str, int]:
    """Recompute has_ai_context and cve_atlas_map for every CVE."""
    from feeds.ai_context import analyze_cve_ai_context

    rows = await db.execute_fetchall(_REFRESH_CVE_ROWS_SQL)
    atlas_rows = await db.execute_fetchall(_SELECT_ATLAS_TECHNIQUE_IDS_SQL)
    known_atlas = {r["technique_id"] for r in atlas_rows}

    cve_updates: list[tuple[int, str]] = []
    atlas_pairs: list[tuple[str, str]] = []
    flagged = 0

    for row in rows:
        cve_id = row["cve_id"]
        products = _parse_json_list(row["affected_products"])
        cve = {"description": row["description"], "affected_products": products}
        has_ai, tids = analyze_cve_ai_context(cve)
        cve_updates.append((1 if has_ai else 0, cve_id))
        if has_ai:
            flagged += 1
        cve_key = cve_id.upper()
        for tid in tids:
            if tid in known_atlas:
                atlas_pairs.append((cve_key, tid.upper()))

    pg = _is_postgres_connection(db)
    update_sql = _UPDATE_HAS_AI_CONTEXT_PG if pg else _UPDATE_HAS_AI_CONTEXT_SQLITE
    insert_atlas_sql = _INSERT_CVE_ATLAS_PAIR_PG if pg else _INSERT_CVE_ATLAS_PAIR_SQLITE

    if cve_updates:
        await db.executemany(update_sql, cve_updates)

    await db.execute(_DELETE_CVE_ATLAS_MAP_SQL)
    if atlas_pairs:
        await db.executemany(insert_atlas_sql, atlas_pairs)

    await db.commit()
    return {"cves_flagged": flagged, "atlas_links": len(atlas_pairs)}


async def replace_mitre_groups(
    db: DbConnection, groups: list[dict]
) -> int:
    """Upsert ATT&CK group rows parsed from STIX."""
    if not groups:
        return 0
    sql = _REPLACE_MITRE_GROUPS_PG if _is_postgres_connection(db) else _REPLACE_MITRE_GROUPS_SQLITE
    await db.executemany(
        sql,
        [
            (
                g["group_id"],
                g["name"],
                json.dumps(g.get("aliases") or []),
                g.get("description") or "",
                json.dumps(g.get("sectors") or []),
                g.get("url") or "",
            )
            for g in groups
        ],
    )
    return len(groups)


async def upsert_group_technique_pairs(
    db: DbConnection, pairs: list[tuple[str, str]]
) -> int:
    """Insert (group_id, technique_id) links, ignoring duplicates."""
    if not pairs:
        return 0
    sql = (
        _INSERT_GROUP_TECHNIQUE_PAIR_PG
        if _is_postgres_connection(db)
        else _INSERT_GROUP_TECHNIQUE_PAIR_SQLITE
    )
    await db.executemany(sql, pairs)
    return len(pairs)


async def get_mitre_group_count(db: DbConnection) -> int:
    row = await db.execute_fetchall(_COUNT_MITRE_GROUPS_SQL)
    return int(row[0]["cnt"]) if row else 0
