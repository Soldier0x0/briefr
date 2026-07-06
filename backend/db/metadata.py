"""MITRE ATT&CK/ATLAS technique + case-study metadata, AI/ML context, analytics. Split from database.py (Phase 3)."""

import json
import aiosqlite


async def get_cve_count(db: aiosqlite.Connection) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM cves")
    return rows[0]["cnt"] if rows else 0

async def get_timeline_activity_summary(db, *, days: int = 90) -> dict:
    """Days with at least one published CVE in the last N UTC calendar days."""
    window = max(1, min(int(days), 365))
    rows = await db.execute_fetchall(
        """
        SELECT DATE(published) AS day, COUNT(*) AS count
        FROM cves
        WHERE published IS NOT NULL
          AND published != ''
          AND DATE(published) >= DATE('now', ?)
        GROUP BY DATE(published)
        """,
        (f"-{window - 1} days",),
    )
    days_with_data = sum(1 for r in rows if (r["count"] or 0) > 0)
    total_cves = sum(int(r["count"] or 0) for r in rows)
    return {
        "days_with_data": days_with_data,
        "total_cves": total_cves,
        "window_days": window,
    }

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
            technique_id, name, description, tactic, url, platforms, detection
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
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
        SELECT m.technique_id, m.name, m.tactic, m.url, m.description, m.detection
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
            "detection": (r["detection"] or "").strip(),
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
            "cve_count": r["cnt"],
            "count": r["cnt"],
            "url": r["url"],
        }
        for r in rows
    ]

async def get_mitre_technique_count(db: aiosqlite.Connection) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM mitre_techniques")
    return rows[0]["cnt"] if rows else 0

async def replace_atlas_techniques(db: aiosqlite.Connection, techniques: list[dict]) -> None:
    incoming_ids = [t["technique_id"] for t in techniques]
    if incoming_ids:
        placeholders = ",".join("?" * len(incoming_ids))
        await db.execute(
            f"DELETE FROM cve_atlas_map WHERE technique_id NOT IN ({placeholders})",
            tuple(incoming_ids),
        )
        await db.execute(
            f"DELETE FROM atlas_techniques WHERE technique_id NOT IN ({placeholders})",
            tuple(incoming_ids),
        )
    else:
        await db.execute("DELETE FROM cve_atlas_map")
        await db.execute("DELETE FROM atlas_techniques")
    if not techniques:
        return
    await db.executemany(
        """
        INSERT INTO atlas_techniques (
            technique_id, name, description, tactic, tactic_id, url
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(technique_id) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            tactic = excluded.tactic,
            tactic_id = excluded.tactic_id,
            url = excluded.url
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

async def clear_cve_atlas_map(db: aiosqlite.Connection) -> None:
    await db.execute("DELETE FROM cve_atlas_map")

async def upsert_cve_atlas_pairs(
    db: aiosqlite.Connection, pairs: list[tuple[str, str]]
) -> int:
    if not pairs:
        return 0
    await db.executemany(
        """
        INSERT OR IGNORE INTO cve_atlas_map (cve_id, technique_id)
        VALUES (?, ?)
        """,
        pairs,
    )
    return len(pairs)

async def replace_cve_atlas_map_for_cve(
    db: aiosqlite.Connection, cve_id: str, technique_ids: list[str]
) -> None:
    cve_key = cve_id.upper()
    await db.execute("DELETE FROM cve_atlas_map WHERE cve_id = ?", (cve_key,))
    if technique_ids:
        await upsert_cve_atlas_pairs(
            db, [(cve_key, tid.upper()) for tid in technique_ids if tid]
        )

async def get_atlas_techniques_for_cve(
    db: aiosqlite.Connection, cve_id: str
) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT t.technique_id, t.name, t.description, t.tactic, t.url
        FROM cve_atlas_map m
        JOIN atlas_techniques t ON t.technique_id = m.technique_id
        WHERE m.cve_id = ?
        ORDER BY t.technique_id
        """,
        (cve_id.upper(),),
    )
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
    db: aiosqlite.Connection, cve_id: str, *, limit: int = 2
) -> list[dict]:
    cve_key = cve_id.upper()
    rows = await db.execute_fetchall(
        """
        SELECT study_id, name, summary, techniques, target, date, cve_ids
        FROM atlas_case_studies
        WHERE cve_ids LIKE ?
        ORDER BY date DESC, name
        LIMIT ?
        """,
        (f'%"{cve_key}"%', limit),
    )
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

async def count_ai_ml_profile_alerts(
    db: aiosqlite.Connection, frameworks: list[str]
) -> int:
    if not frameworks:
        return 0
    rows = await db.execute_fetchall(
        """
        SELECT cve_id, description, affected_products
        FROM cves
        WHERE has_ai_context = 1
        """
    )
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

async def refresh_all_cve_ai_context(db: aiosqlite.Connection) -> dict[str, int]:
    """Recompute has_ai_context and cve_atlas_map for every CVE."""
    from feeds.ai_context import analyze_cve_ai_context

    rows = await db.execute_fetchall(
        """
        SELECT cve_id, description, affected_products
        FROM cves
        """
    )
    atlas_rows = await db.execute_fetchall(
        "SELECT technique_id FROM atlas_techniques"
    )
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

    if cve_updates:
        await db.executemany(
            "UPDATE cves SET has_ai_context = ? WHERE cve_id = ?",
            cve_updates,
        )

    await db.execute("DELETE FROM cve_atlas_map")
    if atlas_pairs:
        await db.executemany(
            """
            INSERT OR IGNORE INTO cve_atlas_map (cve_id, technique_id)
            VALUES (?, ?)
            """,
            atlas_pairs,
        )

    await db.commit()
    return {"cves_flagged": flagged, "atlas_links": len(atlas_pairs)}

async def replace_mitre_groups(
    db: aiosqlite.Connection, groups: list[dict]
) -> int:
    """Upsert ATT&CK group rows parsed from STIX."""
    if not groups:
        return 0
    await db.executemany(
        """
        INSERT INTO mitre_groups (group_id, name, aliases, description, sectors, url)
        VALUES (:group_id, :name, :aliases, :description, :sectors, :url)
        ON CONFLICT(group_id) DO UPDATE SET
            name        = excluded.name,
            aliases     = excluded.aliases,
            description = excluded.description,
            sectors     = excluded.sectors,
            url         = excluded.url
        """,
        [
            {
                "group_id": g["group_id"],
                "name": g["name"],
                "aliases": json.dumps(g.get("aliases") or []),
                "description": g.get("description") or "",
                "sectors": json.dumps(g.get("sectors") or []),
                "url": g.get("url") or "",
            }
            for g in groups
        ],
    )
    return len(groups)

async def upsert_group_technique_pairs(
    db: aiosqlite.Connection, pairs: list[tuple[str, str]]
) -> int:
    """Insert (group_id, technique_id) links, ignoring duplicates."""
    if not pairs:
        return 0
    await db.executemany(
        "INSERT OR IGNORE INTO group_technique_map (group_id, technique_id) VALUES (?, ?)",
        pairs,
    )
    return len(pairs)

async def get_mitre_group_count(db: aiosqlite.Connection) -> int:
    row = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM mitre_groups")
    return int(row[0]["cnt"]) if row else 0
