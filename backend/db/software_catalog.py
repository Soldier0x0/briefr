"""software_catalog persistence + autocomplete (Q3)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from db.config import is_postgres
from db.types import DbConnection

logger = logging.getLogger(__name__)

_UPSERT_PG = """
INSERT INTO software_catalog (
    cpe_uri, vendor, product, version, display_name, category, title,
    versions_json, updated_at
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9
)
ON CONFLICT (cpe_uri) DO UPDATE SET
    vendor = EXCLUDED.vendor,
    product = EXCLUDED.product,
    version = EXCLUDED.version,
    display_name = EXCLUDED.display_name,
    category = EXCLUDED.category,
    title = EXCLUDED.title,
    versions_json = EXCLUDED.versions_json,
    updated_at = EXCLUDED.updated_at
"""

_UPSERT_SQLITE = """
INSERT INTO software_catalog (
    cpe_uri, vendor, product, version, display_name, category, title,
    versions_json, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(cpe_uri) DO UPDATE SET
    vendor = excluded.vendor,
    product = excluded.product,
    version = excluded.version,
    display_name = excluded.display_name,
    category = excluded.category,
    title = excluded.title,
    versions_json = excluded.versions_json,
    updated_at = excluded.updated_at
"""


def categorize_cpe(*, part: str, vendor: str, product: str) -> str:
    """Map CPE part + heuristics → stack category."""
    p = (product or "").lower()
    v = (vendor or "").lower()
    part = (part or "").lower()

    if part == "o":
        return "os"

    web = (
        "httpd", "http_server", "nginx", "iis", "tomcat", "jetty",
        "websphere", "weblogic", "apache",
    )
    if any(k in p for k in web):
        return "web_server"

    db = (
        "postgresql", "mysql", "mariadb", "mongodb", "redis", "sqlite",
        "sql_server", "oracle", "database", "elasticsearch", "cassandra",
    )
    if any(k in p for k in db):
        return "database"

    fw = (
        "fortios", "pan-os", "asa", "firewall", "adaptive_security",
        "big-ip", "sophos",
    )
    if any(k in p for k in fw) or any(k in v for k in ("fortinet", "paloaltonetworks")):
        return "firewall"

    lib = ("openssl", "lib", "glibc", "busybox", "zlib", "curl")
    if any(p.startswith(k) or k in p for k in lib):
        return "library"

    if part == "a":
        return "app"
    return "other"


def parse_cpe23(cpe_uri: str) -> dict[str, str]:
    """Parse CPE 2.3 URI into fields (best-effort)."""
    raw = (cpe_uri or "").strip()
    if raw.startswith("cpe:/"):
        # Convert 2.2-ish to pieces when possible
        body = raw[5:]
        parts = body.split(":")
        while len(parts) < 5:
            parts.append("*")
        return {
            "part": parts[0] if parts else "*",
            "vendor": parts[1] if len(parts) > 1 else "*",
            "product": parts[2] if len(parts) > 2 else "*",
            "version": parts[3] if len(parts) > 3 else "*",
        }
    parts = raw.split(":")
    # cpe:2.3:part:vendor:product:version:...
    if len(parts) >= 6 and parts[0] == "cpe":
        return {
            "part": parts[2],
            "vendor": parts[3],
            "product": parts[4],
            "version": parts[5],
        }
    return {"part": "*", "vendor": "*", "product": "*", "version": "*"}


def display_name_for(vendor: str, product: str, title: str | None = None) -> str:
    if title and title.strip():
        return title.strip()[:200]
    prod = (product or "").replace("_", " ").strip()
    vend = (vendor or "").replace("_", " ").strip()
    if vend and vend not in ("*", "-") and prod:
        return f"{vend} {prod}"[:200]
    return (prod or vend or "unknown")[:200]


async def upsert_catalog_rows(db: DbConnection, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = _UPSERT_PG if is_postgres() else _UPSERT_SQLITE
    now = datetime.now(timezone.utc)
    ts: Any = now if is_postgres() else now.replace(tzinfo=None).isoformat(sep=" ")
    params_batch: list[tuple] = []
    for row in rows:
        versions = row.get("versions_json")
        if isinstance(versions, (list, dict)):
            versions = json.dumps(versions)
        params_batch.append(
            (
                row["cpe_uri"],
                row["vendor"],
                row["product"],
                row.get("version"),
                row.get("display_name"),
                row.get("category") or "other",
                row.get("title"),
                versions,
                ts,
            )
        )
    await db.executemany(sql, params_batch)
    return len(params_batch)


async def suggest_software(
    db: DbConnection,
    *,
    query: str,
    limit: int = 20,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Autocomplete after ≥3 characters. Groups by vendor+product."""
    q = (query or "").strip()
    if len(q) < 3:
        return []
    limit = max(1, min(int(limit), 50))
    like = f"%{q.lower()}%"
    cat = (category or "").strip().lower() or None

    if is_postgres():
        params: list[Any] = [like, limit]
        cat_sql = ""
        if cat:
            cat_sql = " AND category = $3"
            params = [like, limit, cat]
        rows = await db.execute_fetchall(
            f"""
            SELECT vendor, product,
                   COALESCE(MAX(display_name), MAX(product)) AS display_name,
                   COALESCE(MAX(category), 'other') AS category,
                   ARRAY_AGG(DISTINCT version) FILTER (
                     WHERE version IS NOT NULL
                       AND version NOT IN ('*', '-', '')
                   ) AS versions
            FROM software_catalog
            WHERE (
                lower(product) LIKE $1
                OR lower(COALESCE(display_name, '')) LIKE $1
                OR lower(vendor) LIKE $1
            )
            {cat_sql}
            GROUP BY vendor, product
            ORDER BY
              CASE WHEN lower(product) LIKE $1 THEN 0 ELSE 1 END,
              display_name
            LIMIT $2
            """,
            tuple(params),
        )
    else:
        params_s: list[Any] = [like, like, like]
        cat_sql = ""
        if cat:
            cat_sql = " AND category = ?"
            params_s.append(cat)
        params_s.append(limit)
        rows = await db.execute_fetchall(
            f"""
            SELECT vendor, product,
                   COALESCE(MAX(display_name), product) AS display_name,
                   COALESCE(MAX(category), 'other') AS category,
                   GROUP_CONCAT(DISTINCT version) AS versions
            FROM software_catalog
            WHERE (
                lower(product) LIKE ?
                OR lower(COALESCE(display_name, '')) LIKE ?
                OR lower(vendor) LIKE ?
            )
            {cat_sql}
            GROUP BY vendor, product
            ORDER BY display_name
            LIMIT ?
            """,
            tuple(params_s),
        )

    out: list[dict[str, Any]] = []
    for row in rows or []:
        try:
            d = dict(row)
        except Exception:
            d = {
                "vendor": row[0],
                "product": row[1],
                "display_name": row[2],
                "category": row[3],
                "versions": row[4] if len(row) > 4 else None,
            }
        versions = d.get("versions")
        if isinstance(versions, str):
            versions = [v for v in versions.split(",") if v and v not in ("*", "-")]
        elif versions is None:
            versions = []
        else:
            versions = [v for v in list(versions) if v and v not in ("*", "-")]
        # Dedupe + cap
        seen: set[str] = set()
        clean: list[str] = []
        for v in versions:
            s = str(v)
            if s not in seen:
                seen.add(s)
                clean.append(s)
            if len(clean) >= 12:
                break
        out.append(
            {
                "vendor": d.get("vendor"),
                "product": d.get("product"),
                "display_name": d.get("display_name") or d.get("product"),
                "category": d.get("category") or "other",
                "versions": clean,
            }
        )
    return out


async def lookup_catalog_titles(
    db: DbConnection,
    pairs: list[tuple[str, str]],
) -> dict[tuple[str, str], str]:
    """Return catalog `title` for each (vendor, product). Empty titles omitted."""
    cleaned: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for vendor, product in pairs:
        vend = (vendor or "").strip().lower()
        prod = (product or "").strip().lower()
        if not vend or not prod or (vend, prod) in seen:
            continue
        seen.add((vend, prod))
        cleaned.append((vend, prod))
    if not cleaned:
        return {}

    clauses: list[str] = []
    params: list[Any] = []
    pg = is_postgres()
    for vendor, product in cleaned:
        if pg:
            i = len(params)
            clauses.append(f"(lower(vendor) = ${i + 1} AND lower(product) = ${i + 2})")
        else:
            clauses.append("(lower(vendor) = ? AND lower(product) = ?)")
        params.extend([vendor, product])
    rows = await db.execute_fetchall(
        f"""
        SELECT lower(vendor) AS vendor, lower(product) AS product,
               MAX(NULLIF(TRIM(title), '')) AS title
        FROM software_catalog
        WHERE {' OR '.join(clauses)}
        GROUP BY lower(vendor), lower(product)
        """,
        tuple(params),
    )
    out: dict[tuple[str, str], str] = {}
    for row in rows or []:
        title = (row["title"] or "").strip()
        if not title:
            continue
        out[(str(row["vendor"]), str(row["product"]))] = title[:200]
    return out
