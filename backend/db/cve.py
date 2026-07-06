"""CVE CRUD, embeddings, related-CVE lookups, and the shared change-row helpers upsert_cves needs. Split from database.py (Phase 3)."""

import json
import aiosqlite
from db.dialect import utcnow_str


async def cve_exists(db: aiosqlite.Connection, cve_id: str) -> bool:
    rows = await db.execute_fetchall(
        "SELECT 1 FROM cves WHERE cve_id = ? LIMIT 1",
        (cve_id.upper(),),
    )
    return bool(rows)

TRACKED_CVE_FIELDS = frozenset({"cvss_score", "epss_score", "is_kev", "has_poc"})

def _change_value_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            text = f"{value:.6f}".rstrip("0").rstrip(".")
            return text or "0"
        return str(value)
    return str(value)

def _values_differ(old: object, new: object) -> bool:
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    if isinstance(old, float) and isinstance(new, float):
        return abs(old - new) > 1e-9
    return old != new

_SQLITE_IN_CHUNK = 500

_UPSERT_CVE_SQL = """
    INSERT INTO cves (
        cve_id, description, cvss_score, severity, published, modified,
        affected_products, mitre_technique, summary, is_kev, epss_score,
        has_poc, patch_available, has_ai_context, source_urls, cwe_ids, updated_at
    ) VALUES (
        :cve_id, :description, :cvss_score, :severity, :published, :modified,
        :affected_products, :mitre_technique, :summary, :is_kev, :epss_score,
        :has_poc, :patch_available, :has_ai_context, :source_urls, :cwe_ids, :updated_at
    )
    ON CONFLICT(cve_id) DO UPDATE SET
        description = excluded.description,
        cvss_score = excluded.cvss_score,
        severity = excluded.severity,
        published = excluded.published,
        modified = excluded.modified,
        -- LLM-derived products survive feed upserts that carry no CPE data;
        -- any non-empty official product list supersedes them (and clears
        -- the 'llm' provenance marker).
        affected_products = CASE
            WHEN cves.affected_products_source = 'llm'
                 AND (excluded.affected_products IS NULL
                      OR excluded.affected_products IN ('', '[]'))
            THEN cves.affected_products
            ELSE excluded.affected_products
        END,
        affected_products_source = CASE
            WHEN cves.affected_products_source = 'llm'
                 AND (excluded.affected_products IS NULL
                      OR excluded.affected_products IN ('', '[]'))
            THEN 'llm'
            ELSE ''
        END,
        cpe_matches = excluded.cpe_matches,
        mitre_technique = COALESCE(excluded.mitre_technique, cves.mitre_technique),
        summary = COALESCE(excluded.summary, cves.summary),
        has_poc = CASE WHEN excluded.has_poc = 1 THEN 1 ELSE cves.has_poc END,
        patch_available = excluded.patch_available,
        has_ai_context = excluded.has_ai_context,
        source_urls = excluded.source_urls,
        cwe_ids = excluded.cwe_ids,
        updated_at = :updated_at
"""

def _cve_upsert_params(cve: dict) -> dict:
    return {
        "cve_id": cve.get("cve_id", ""),
        "description": cve.get("description", ""),
        "cvss_score": cve.get("cvss_score"),
        "severity": cve.get("severity", "UNKNOWN"),
        "published": cve.get("published", ""),
        "modified": cve.get("modified", ""),
        "affected_products": json.dumps(cve.get("affected_products", [])),
        "cpe_matches": json.dumps(cve.get("cpe_matches", [])),
        "mitre_technique": cve.get("mitre_technique"),
        "summary": cve.get("summary"),
        "is_kev": 1 if cve.get("is_kev") else 0,
        "epss_score": cve.get("epss_score"),
        "has_poc": 1 if cve.get("has_poc") else 0,
        "patch_available": 1 if cve.get("patch_available") else 0,
        "has_ai_context": 1 if cve.get("has_ai_context") else 0,
        "source_urls": json.dumps(cve.get("source_urls", [])),
        "cwe_ids": json.dumps(cve.get("cwe_ids", [])),
        "updated_at": utcnow_str(),
    }

def _append_upsert_change_rows(
    cve_id: str,
    cve: dict,
    prior: dict | None,
    history: list[tuple[str, str, str, str]],
) -> None:
    incoming_poc = 1 if cve.get("has_poc") else 0
    incoming_kev = 1 if cve.get("is_kev") else 0
    new_poc = (1 if prior["has_poc"] or incoming_poc else 0) if prior else incoming_poc
    new_cvss = cve.get("cvss_score")

    if prior:
        if _values_differ(prior["cvss_score"], new_cvss):
            history.append(
                (
                    cve_id,
                    "cvss_score",
                    _change_value_str(prior["cvss_score"]),
                    _change_value_str(new_cvss),
                )
            )
        if prior["has_poc"] == 0 and new_poc == 1:
            history.append((cve_id, "has_poc", "0", "1"))
    else:
        if incoming_kev:
            history.append((cve_id, "is_kev", "0", "1"))
        if incoming_poc:
            history.append((cve_id, "has_poc", "0", "1"))
        if new_cvss is not None:
            history.append(
                (cve_id, "cvss_score", "", _change_value_str(new_cvss))
            )

async def _insert_cve_changes_batch(
    db: aiosqlite.Connection,
    rows: list[tuple[str, str, str, str]],
) -> None:
    if not rows:
        return
    await db.executemany(
        """
        INSERT INTO cve_change_history (cve_id, field_name, old_value, new_value, detected_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [(*r, utcnow_str()) for r in rows],
    )

async def _load_cve_change_snapshots(
    db: aiosqlite.Connection, cve_ids: list[str]
) -> dict[str, dict]:
    snapshots: dict[str, dict] = {}
    normalized = [c.upper() for c in cve_ids if c]
    for i in range(0, len(normalized), _SQLITE_IN_CHUNK):
        chunk = normalized[i : i + _SQLITE_IN_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        rows = await db.execute_fetchall(
            f"""
            SELECT cve_id, cvss_score, epss_score, is_kev, has_poc
            FROM cves WHERE cve_id IN ({placeholders})
            """,
            chunk,
        )
        for row in rows:
            snapshots[row["cve_id"]] = {
                "cvss_score": row["cvss_score"],
                "epss_score": row["epss_score"],
                "is_kev": int(row["is_kev"] or 0),
                "has_poc": int(row["has_poc"] or 0),
            }
    return snapshots

def _cve_id_filter_clause(cve_ids: list[str] | None) -> tuple[str, list[str]]:
    if not cve_ids:
        return "", []
    normalized = [c.upper() for c in cve_ids if c]
    if not normalized:
        return "", []
    placeholders = ",".join("?" * len(normalized))
    return f" AND cve_id IN ({placeholders})", normalized

async def upsert_cves(db: aiosqlite.Connection, cves: list[dict]) -> None:
    if not cves:
        return
    valid = [c for c in cves if (c.get("cve_id") or "").strip()]
    if not valid:
        return

    ids = [(c.get("cve_id") or "").upper() for c in valid]
    snapshots = await _load_cve_change_snapshots(db, ids)
    history: list[tuple[str, str, str, str]] = []

    from feeds.ai_context import analyze_cve_ai_context

    for cve in valid:
        cve_id = (cve.get("cve_id") or "").upper()
        has_ai, _atlas_tids = analyze_cve_ai_context(cve)
        cve["has_ai_context"] = has_ai
        _append_upsert_change_rows(cve_id, cve, snapshots.get(cve_id), history)
        await db.execute(_UPSERT_CVE_SQL, _cve_upsert_params(cve))

    await _insert_cve_changes_batch(db, history)

async def upsert_cve(db: aiosqlite.Connection, cve: dict) -> None:
    await upsert_cves(db, [cve])

async def get_cves_needing_intel_enrichment(
    db: aiosqlite.Connection,
    *,
    limit: int = 5000,
) -> list[str]:
    """CVE IDs that may still benefit from vulnrichment / cvelist enrichment."""
    rows = await db.execute_fetchall(
        """
        SELECT cve_id FROM cves
        WHERE cvss_score IS NULL
           OR severity IS NULL
           OR severity = 'UNKNOWN'
           OR cwe_ids IS NULL
           OR cwe_ids = '[]'
           OR cwe_ids = ''
        ORDER BY published DESC, cve_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [row["cve_id"] for row in rows]

async def apply_additive_cve_enrichments(
    db: aiosqlite.Connection,
    enrichments: list[dict],
) -> int:
    """Merge scheduler intel into cves without downgrading richer NVD fields."""
    from feeds.cve_record_v5 import merge_additive_cve_fields

    if not enrichments:
        return 0

    updated = 0
    for incoming in enrichments:
        cve_id = (incoming.get("cve_id") or "").upper()
        if not cve_id:
            continue

        rows = await db.execute_fetchall(
            """
            SELECT cve_id, description, cvss_score, severity, published, modified,
                   affected_products, cwe_ids
            FROM cves WHERE cve_id = ?
            """,
            (cve_id,),
        )

        if rows:
            existing = dict(rows[0])
            changes = merge_additive_cve_fields(existing, incoming) or {}
            ssvc = incoming.get("ssvc")
            if not changes and not (isinstance(ssvc, dict) and ssvc.get("decisions")):
                continue
            params = {"cve_id": cve_id}
            set_parts: list[str] = []
            if "cvss_score" in changes:
                set_parts.append("cvss_score = :cvss_score")
                params["cvss_score"] = changes["cvss_score"]
            if "severity" in changes:
                set_parts.append("severity = :severity")
                params["severity"] = changes["severity"]
            if "description" in changes:
                set_parts.append("description = :description")
                params["description"] = changes["description"]
            if "published" in changes:
                set_parts.append("published = :published")
                params["published"] = changes["published"]
            if "modified" in changes:
                set_parts.append("modified = :modified")
                params["modified"] = changes["modified"]
            if "cwe_ids" in changes:
                set_parts.append("cwe_ids = :cwe_ids")
                params["cwe_ids"] = json.dumps(changes["cwe_ids"])
            if "affected_products" in changes:
                set_parts.append("affected_products = :affected_products")
                params["affected_products"] = json.dumps(changes["affected_products"])
            if set_parts:
                set_parts.append("updated_at = :updated_at")
                params["updated_at"] = utcnow_str()
                await db.execute(
                    f"UPDATE cves SET {', '.join(set_parts)} WHERE cve_id = :cve_id",
                    params,
                )
                updated += 1
        else:
            await upsert_cve(db, incoming)
            updated += 1

        ssvc = incoming.get("ssvc")
        if isinstance(ssvc, dict) and ssvc.get("decisions"):
            from db.cache import set_feed_cache

            await set_feed_cache(db, f"ssvc:{cve_id}", ssvc)
            if rows and not changes:
                updated += 1

    return updated

async def delete_cves_by_ids(db: aiosqlite.Connection, cve_ids: list[str]) -> int:
    """Remove CVE rows (and purge legacy rejected-description rows). Caller commits."""
    normalized = sorted({c.strip().upper() for c in cve_ids if c and str(c).strip()})
    deleted = 0
    for i in range(0, len(normalized), _SQLITE_IN_CHUNK):
        chunk = normalized[i : i + _SQLITE_IN_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        cursor = await db.execute(
            f"DELETE FROM cves WHERE cve_id IN ({placeholders})",
            chunk,
        )
        deleted += cursor.rowcount
    return deleted

async def purge_legacy_rejected_cves(db: aiosqlite.Connection) -> int:
    """Delete rows ingested before reject-filtering (NVD 'Rejected reason:' text)."""
    cursor = await db.execute(
        """
        DELETE FROM cves
        WHERE LOWER(description) LIKE 'rejected reason:%'
        """
    )
    return cursor.rowcount

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

async def upsert_cve_embedding(
    db: aiosqlite.Connection, cve_id: str, model: str, dim: int, vector: bytes
) -> None:
    """Store one embedding BLOB (float32 little-endian). One row per CVE;
    a model change replaces the old vector on the next backfill pass."""
    await db.execute(
        """
        INSERT INTO cve_embeddings (cve_id, model, dim, vector, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(cve_id) DO UPDATE SET
            model = excluded.model,
            dim = excluded.dim,
            vector = excluded.vector,
            updated_at = excluded.updated_at
        """,
        (cve_id.upper(), model, dim, vector, utcnow_str()),
    )

async def get_cve_embedding(
    db: aiosqlite.Connection, cve_id: str, model: str
) -> bytes | None:
    rows = await db.execute_fetchall(
        "SELECT vector FROM cve_embeddings WHERE cve_id = ? AND model = ?",
        (cve_id.upper(), model),
    )
    return rows[0]["vector"] if rows else None

async def get_all_cve_embeddings(
    db: aiosqlite.Connection, model: str, exclude_cve_id: str | None = None
) -> list[tuple[str, bytes]]:
    """All stored vectors for one model — input to the brute-force cosine scan."""
    if exclude_cve_id:
        rows = await db.execute_fetchall(
            "SELECT cve_id, vector FROM cve_embeddings WHERE model = ? AND cve_id != ?",
            (model, exclude_cve_id.upper()),
        )
    else:
        rows = await db.execute_fetchall(
            "SELECT cve_id, vector FROM cve_embeddings WHERE model = ?",
            (model,),
        )
    return [(row["cve_id"], row["vector"]) for row in rows]

async def count_cve_embeddings(db: aiosqlite.Connection, model: str) -> int:
    rows = await db.execute_fetchall(
        "SELECT COUNT(*) AS n FROM cve_embeddings WHERE model = ?", (model,)
    )
    return int(rows[0]["n"]) if rows else 0

async def get_cves_missing_embeddings(
    db: aiosqlite.Connection, model: str, limit: int = 500
) -> list[dict]:
    """CVEs with a description but no vector for the active model (newest first)."""
    rows = await db.execute_fetchall(
        """
        SELECT c.cve_id, c.description
        FROM cves c
        LEFT JOIN cve_embeddings e
          ON e.cve_id = c.cve_id AND e.model = ?
        WHERE e.cve_id IS NULL
          AND c.description IS NOT NULL
          AND c.description != ''
        ORDER BY c.published DESC
        LIMIT ?
        """,
        (model, limit),
    )
    return [{"cve_id": row["cve_id"], "description": row["description"]} for row in rows]

async def get_cve_summaries_by_ids(
    db: aiosqlite.Connection, cve_ids: list[str]
) -> dict[str, dict]:
    """Hydrate related-CVE cards (same fields the product heuristic returns)."""
    result: dict[str, dict] = {}
    normalized = [c.upper() for c in cve_ids if c]
    for i in range(0, len(normalized), _SQLITE_IN_CHUNK):
        chunk = normalized[i : i + _SQLITE_IN_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        rows = await db.execute_fetchall(
            f"""
            SELECT cve_id, description, cvss_score, severity, published, epss_score
            FROM cves WHERE cve_id IN ({placeholders})
            """,
            chunk,
        )
        for row in rows:
            result[row["cve_id"]] = {
                "cve_id": row["cve_id"],
                "description": row["description"] or "",
                "cvss_score": row["cvss_score"],
                "severity": row["severity"],
                "published": row["published"],
                "epss_score": row["epss_score"],
            }
    return result

async def get_cves_for_llm_product_extraction(
    db: aiosqlite.Connection, limit: int = 25, retry_hours: float = 168
) -> list[dict]:
    """CVEs with no CPE data and no affected products yet (NVD-unanalyzed).

    Skips CVEs attempted within the negative-cache window
    (feed_cache key ``llm_products:<cve_id>``).
    """
    rows = await db.execute_fetchall(
        """
        SELECT c.cve_id, c.description
        FROM cves c
        LEFT JOIN feed_cache fc
          ON fc.cache_key = 'llm_products:' || c.cve_id
         AND fc.cached_at > datetime('now', ?)
        WHERE fc.cache_key IS NULL
          AND (c.affected_products IS NULL OR c.affected_products IN ('', '[]'))
          AND (c.cpe_matches IS NULL OR c.cpe_matches IN ('', '[]'))
          AND c.description IS NOT NULL
          AND c.description != ''
        ORDER BY c.published DESC
        LIMIT ?
        """,
        (f"-{retry_hours} hours", limit),
    )
    return [{"cve_id": row["cve_id"], "description": row["description"]} for row in rows]

async def set_llm_affected_products(
    db: aiosqlite.Connection, cve_id: str, products: list[str]
) -> bool:
    """Write LLM-derived products ONLY if the field is still empty; mark
    provenance so the data stays distinguishable from official CPE."""
    if not products:
        return False
    cursor = await db.execute(
        """
        UPDATE cves
        SET affected_products = ?,
            affected_products_source = 'llm',
            updated_at = ?
        WHERE cve_id = ?
          AND (affected_products IS NULL OR affected_products IN ('', '[]'))
        """,
        (json.dumps(products), utcnow_str(), cve_id.upper()),
    )
    return cursor.rowcount > 0
