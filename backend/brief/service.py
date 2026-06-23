"""Server-computed morning brief (read-path only, no ingest)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from database import _normalize_epss_score
from routers.cves import CVE_SELECT, _row_to_cve_dict, _stack_match_clause

_ISO_DATE_LIKE = "____-__-__"


def _stack_profile_id(stack_terms: list[str]) -> str | None:
    if not stack_terms:
        return None
    normalized = ",".join(sorted(t.lower() for t in stack_terms if t))
    if not normalized:
        return None
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"stack:{digest}"


def _brief_cve_item(
    row: dict,
    *,
    reasons: list[str],
    extra: dict | None = None,
) -> dict:
    cve = _row_to_cve_dict(row)
    item: dict[str, Any] = {
        "cve_id": cve["cve_id"],
        "severity": cve.get("severity"),
        "cvss_score": cve.get("cvss_score"),
        "epss_score": cve.get("epss_score"),
        "is_kev": cve.get("is_kev"),
        "has_poc": cve.get("has_poc"),
        "summary": cve.get("summary") or "",
        "description": cve.get("description") or "",
        "published": cve.get("published"),
        "kev_due_date": cve.get("kev_due_date"),
        "reasons": reasons,
    }
    if extra:
        item.update(extra)
    return item


def _stack_filter_sql(stack: str | None) -> tuple[str, list, list[str]]:
    clause, params, terms = _stack_match_clause(stack)
    if clause:
        return f" AND {clause}", params, terms
    return "", [], terms


def _epss_delta(old_value: object, new_value: object) -> tuple[float, float, float] | None:
    """Return (old, new, delta) when both values parse as EPSS scores and delta > 0."""
    old_v = _normalize_epss_score(old_value)
    new_v = _normalize_epss_score(new_value)
    if old_v is None or new_v is None:
        return None
    delta = round(new_v - old_v, 6)
    if delta <= 0:
        return None
    return old_v, new_v, delta


def _build_epss_movers(rows: list, *, limit: int) -> list[dict]:
    """Rank EPSS change rows by positive delta (Python-side, DB-agnostic)."""
    candidates: list[tuple[float, dict]] = []
    for raw_row in rows:
        row = dict(raw_row)
        parsed = _epss_delta(row.get("old_value"), row.get("new_value"))
        if parsed is None:
            continue
        old_v, new_v, delta = parsed
        item = _brief_cve_item(
            row,
            reasons=["epss_mover"],
            extra={
                "epss_delta": delta,
                "epss_old": old_v,
                "epss_new": new_v,
                "changed_at": row["detected_at"],
            },
        )
        candidates.append((delta, item))
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in candidates[:limit]]


async def build_morning_brief(
    db: Any,
    *,
    stack: str | None = None,
    since_hours: int = 24,
    limit: int = 10,
    kev_due_days: int = 14,
) -> dict[str, Any]:
    """Aggregate analyst action queue sections from existing DB state."""
    since_sql = f"-{since_hours} hours"
    stack_sql, stack_params, stack_terms = _stack_filter_sql(stack)
    profile_id = _stack_profile_id(stack_terms)

    # ── EPSS movers (largest positive deltas in window) ─────
    # Rank deltas in Python: SQLite CAST(... AS REAL) is forgiving, but Postgres
    # errors on non-numeric change-history text (while /api/stats still works).
    epss_scan_limit = min(max(limit * 10, limit), 200)
    epss_rows = await db.execute_fetchall(
        f"""
        SELECT ch.cve_id, ch.old_value, ch.new_value, ch.detected_at,
               c.description, c.cvss_score, c.severity, c.published, c.modified,
               c.affected_products, c.affected_products_source, c.mitre_technique,
               c.summary, c.is_kev, c.epss_score, c.has_poc, c.patch_available,
               c.has_ai_context, c.source_urls, c.cwe_ids, c.updated_at,
               (SELECT due_date FROM kev_deadlines k WHERE k.cve_id = c.cve_id) AS kev_due_date
        FROM cve_change_history ch
        JOIN cves c ON c.cve_id = ch.cve_id
        WHERE ch.field_name = 'epss_score'
          AND ch.detected_at >= datetime('now', ?)
          {stack_sql}
        ORDER BY ch.detected_at DESC, ch.id DESC
        LIMIT ?
        """,
        [since_sql, *stack_params, epss_scan_limit],
    )
    epss_items = _build_epss_movers(epss_rows, limit=limit)

    # ── New KEV catalogue entries ───────────────────────────
    new_kev_rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id, c.description, c.cvss_score, c.severity, c.published, c.modified,
               c.affected_products, c.affected_products_source, c.mitre_technique,
               c.summary, c.is_kev, c.epss_score, c.has_poc, c.patch_available,
               c.has_ai_context, c.source_urls, c.cwe_ids, c.updated_at,
               k.date_added AS kev_date_added,
               k.due_date AS kev_due_date
        FROM kev_deadlines k
        JOIN cves c ON c.cve_id = k.cve_id
        WHERE k.date_added IS NOT NULL AND k.date_added != ''
          AND k.date_added LIKE ?
          AND DATE(k.date_added) >= date('now', ?)
          {stack_sql}
        ORDER BY k.date_added DESC
        LIMIT ?
        """,
        [_ISO_DATE_LIKE, since_sql, *stack_params, limit],
    )
    new_kev_items = [
        _brief_cve_item(
            dict(row),
            reasons=["new_kev"],
            extra={"kev_date_added": dict(row)["kev_date_added"]},
        )
        for row in new_kev_rows
    ]

    # ── KEV remediation deadlines due soon ──────────────────
    due_rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id, c.description, c.cvss_score, c.severity, c.published, c.modified,
               c.affected_products, c.affected_products_source, c.mitre_technique,
               c.summary, c.is_kev, c.epss_score, c.has_poc, c.patch_available,
               c.has_ai_context, c.source_urls, c.cwe_ids, c.updated_at,
               k.due_date AS kev_due_date,
               k.date_added AS kev_date_added
        FROM kev_deadlines k
        JOIN cves c ON c.cve_id = k.cve_id
        WHERE k.due_date IS NOT NULL AND k.due_date != ''
          AND k.due_date LIKE ?
          AND DATE(k.due_date) >= DATE('now')
          AND DATE(k.due_date) <= DATE('now', ?)
          {stack_sql}
        ORDER BY k.due_date ASC
        LIMIT ?
        """,
        [_ISO_DATE_LIKE, f"+{kev_due_days} days", *stack_params, limit],
    )
    kev_due_items = [
        _brief_cve_item(
            dict(row),
            reasons=["kev_due_soon"],
            extra={"kev_date_added": dict(row).get("kev_date_added")},
        )
        for row in due_rows
    ]

    # ── Stack matches with recent activity ──────────────────
    stack_items: list[dict] = []
    stack_clause, stack_clause_params, _ = _stack_match_clause(stack)
    if stack_clause and stack_terms:
        stack_rows = await db.execute_fetchall(
            f"""
            {CVE_SELECT}
            WHERE {stack_clause}
              AND (
                published >= datetime('now', ?)
                OR modified >= datetime('now', ?)
                OR EXISTS (
                  SELECT 1 FROM cve_change_history ch
                  WHERE ch.cve_id = c.cve_id
                    AND ch.detected_at >= datetime('now', ?)
                )
              )
            ORDER BY
              CASE WHEN is_kev = 1 THEN 0 ELSE 1 END,
              CASE WHEN epss_score IS NOT NULL THEN epss_score ELSE -1 END DESC,
              published DESC
            LIMIT ?
            """,
            [*stack_clause_params, since_sql, since_sql, since_sql, limit],
        )
        stack_items = [
            _brief_cve_item(dict(row), reasons=["stack_match"])
            for row in stack_rows
        ]

    sections = {
        "epss_movers": {"title": "EPSS movers", "count": len(epss_items), "items": epss_items},
        "new_kev": {"title": "New KEV entries", "count": len(new_kev_items), "items": new_kev_items},
        "kev_due_soon": {
            "title": f"KEV due within {kev_due_days} days",
            "count": len(kev_due_items),
            "items": kev_due_items,
        },
        "stack_matches": {
            "title": "Stack activity",
            "count": len(stack_items),
            "items": stack_items,
        },
    }

    action_queue = _build_action_queue(sections, limit=limit * 2)

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "stack_profile_id": profile_id,
            "stack_terms": stack_terms,
            "since_hours": since_hours,
            "kev_due_days": kev_due_days,
        },
        "sections": sections,
        "action_queue": action_queue,
    }


def _priority_score(item: dict) -> float:
    reasons = item.get("reasons") or []
    score = 0.0
    if "kev_due_soon" in reasons:
        score += 100.0
        due = item.get("kev_due_date") or ""
        if due:
            try:
                due_date = datetime.strptime(due[:10], "%Y-%m-%d").date()
                days_left = (due_date - datetime.now(timezone.utc).date()).days
                score += max(0, 14 - days_left)
            except ValueError:
                pass
    if "new_kev" in reasons:
        score += 90.0
    if "epss_mover" in reasons:
        score += 70.0 + float(item.get("epss_delta") or 0) * 100.0
    if "stack_match" in reasons:
        score += 60.0
        if item.get("is_kev"):
            score += 15.0
        epss = item.get("epss_score")
        if epss is not None:
            score += float(epss) * 20.0
    return score


def _build_action_queue(sections: dict, *, limit: int) -> list[dict]:
    by_id: dict[str, dict] = {}
    for section_key, section in sections.items():
        for item in section.get("items") or []:
            cve_id = item["cve_id"]
            existing = by_id.get(cve_id)
            if existing:
                merged_reasons = list(dict.fromkeys(existing["reasons"] + item["reasons"]))
                existing["reasons"] = merged_reasons
                for k, v in item.items():
                    if k not in ("reasons",) and existing.get(k) in (None, "", []):
                        existing[k] = v
            else:
                by_id[cve_id] = {**item, "reasons": list(item["reasons"])}
    ranked = sorted(by_id.values(), key=_priority_score, reverse=True)
    return ranked[:limit]
