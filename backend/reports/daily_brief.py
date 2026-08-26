from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from db.types import DbConnection

DailyBriefSlot = Literal["eod", "standup"]

COUNT_KEYS = (
    "kev_new",
    "stack_matches",
    "watchlist",
    "ioc_hits",
    "critical_high_new",
    "ops_issues",
)

LIST_DROP_ORDER = ("ops", "ioc", "watchlist", "stack", "kev")

_OPS_CATEGORIES = ("job_error", "api_key_unhealthy", "webhook_failure")


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _placeholder(pg: bool, index: int) -> str:
    return f"${index}" if pg else "?"


@dataclass
class DailyBrief:
    slot: DailyBriefSlot
    tz_name: str
    window_start_local: str
    window_end_local: str
    generated_local: str
    headline: str
    lede_source: str
    counts: dict[str, int]
    kev: list[dict[str, str]]
    stack: list[dict[str, str]]
    watchlist: list[dict[str, str]]
    ioc: list[dict[str, str]]
    ops: list[dict[str, str]]


def _fmt_local(dt: datetime, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")


def _date_local(dt: datetime, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    return dt.astimezone(tz).strftime("%Y-%m-%d")


def _bound_local(dt: datetime, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")


def template_headline(brief: DailyBrief) -> str:
    c = brief.counts
    if all(c[k] == 0 for k in COUNT_KEYS):
        return "Quiet window."
    parts = []
    if c["kev_new"]:
        parts.append(f"{c['kev_new']} new KEV.")
    if c["stack_matches"]:
        parts.append(f"{c['stack_matches']} stack match(es).")
    if c["watchlist"]:
        parts.append(f"Watchlist: {c['watchlist']}.")
    if c["ioc_hits"]:
        parts.append(f"{c['ioc_hits']} IOC hit(s).")
    if c["critical_high_new"] and not c["kev_new"]:
        parts.append(f"{c['critical_high_new']} new Critical/High.")
    if c["ops_issues"]:
        parts.append(f"{c['ops_issues']} ops issue(s).")
    return " ".join(parts) or "Quiet window."


def _line_cve(row: dict[str, str]) -> str:
    sev = (row.get("severity") or "").strip()
    extra = f" · {sev}" if sev else ""
    return f"• {row['cve_id']} — {row['reason']}{extra}"


def _section_counts(brief: DailyBrief) -> dict[str, int]:
    return {
        "kev": brief.counts["kev_new"],
        "stack": brief.counts["stack_matches"],
        "watchlist": brief.counts["watchlist"],
        "ioc": brief.counts["ioc_hits"],
        "ops": brief.counts["ops_issues"],
    }


def format_daily_brief_text(brief: DailyBrief, *, limit: int) -> str:
    slot_label = "EOD" if brief.slot == "eod" else "STANDUP"
    footer_line = (
        f"BRIEFR — generated {brief.generated_local} {brief.tz_name} | "
        f"slot={brief.slot} | facts=local | lede={brief.lede_source}"
    )

    def build_sections(headline_text: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {
            "masthead": [
                f"BRIEFR {slot_label}",
                f"{brief.window_start_local} → {brief.window_end_local} ({brief.tz_name})",
            ],
            "headline": ["// HEADLINE", headline_text or "Quiet window."],
            "counts": ["// COUNTS"]
            + [
                f"KEV new: {brief.counts['kev_new']}",
                f"Stack matches: {brief.counts['stack_matches']}",
                f"Watchlist: {brief.counts['watchlist']}",
                f"IOC hits: {brief.counts['ioc_hits']}",
                f"Critical/High new: {brief.counts['critical_high_new']}",
                f"Ops issues: {brief.counts['ops_issues']}",
            ],
            "kev": ["// KEV"] + [_line_cve(r) for r in brief.kev[:8]],
            "stack": ["// STACK"] + [_line_cve(r) for r in brief.stack[:8]],
            "watchlist": ["// WATCHLIST"] + [_line_cve(r) for r in brief.watchlist[:8]],
            "ioc": ["// IOC"]
            + [
                f"• {r.get('type', '')} {r.get('value', '')} — {r.get('reason', '')}".strip()
                for r in brief.ioc[:5]
            ],
            "ops": ["// OPS"] + [f"• {r['id']} — {r['reason']}" for r in brief.ops[:5]],
            "footer": [footer_line],
        }
        for key in ("kev", "stack", "watchlist", "ioc", "ops"):
            if len(sections[key]) == 1:
                sections[key] = []
        return sections

    def assemble(
        sections: dict[str, list[str]],
        *,
        drop: set[str],
        overflow_notes: list[str],
    ) -> str:
        chunks: list[str] = []
        for name in (
            "masthead",
            "headline",
            "counts",
            "kev",
            "stack",
            "watchlist",
            "ioc",
            "ops",
        ):
            if name in drop:
                continue
            body = sections[name]
            if not body:
                continue
            chunks.append("\n".join(body))
        if overflow_notes:
            chunks.append("\n".join(overflow_notes))
        if "footer" not in drop:
            footer = sections["footer"]
            if footer:
                chunks.append("\n".join(footer))
        return "\n\n".join(chunks)

    headline = brief.headline or "Quiet window."
    dropped: set[str] = set()
    overflow_notes: list[str] = []
    sections = build_sections(headline)

    text = assemble(sections, drop=dropped, overflow_notes=overflow_notes)
    if len(text) <= limit:
        return text

    for name in LIST_DROP_ORDER:
        if name in dropped:
            continue
        count = _section_counts(brief)[name]
        dropped.add(name)
        if count > 0:
            overflow_notes.append(f"+{count} more in BRIEFR.")
        text = assemble(sections, drop=dropped, overflow_notes=overflow_notes)
        if len(text) <= limit:
            return text

    first = headline.split(". ")[0].rstrip(".") + "."
    sections = build_sections(first)
    text = assemble(sections, drop=dropped, overflow_notes=overflow_notes)
    if len(text) <= limit:
        return text

    remaining = [
        name
        for name in ("kev", "stack", "watchlist", "ioc", "ops")
        if name not in dropped and _section_counts(brief)[name] > 0
    ]
    if remaining:
        hidden = sum(_section_counts(brief)[name] for name in remaining)
        dropped.update(remaining)
        overflow_notes = [f"+{hidden} more in BRIEFR."]
        text = assemble(sections, drop=dropped, overflow_notes=overflow_notes)
        if len(text) <= limit:
            return text

    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


async def _fetch_kev(
    db: DbConnection,
    start_date: str,
    end_date: str,
) -> list[dict[str, str]]:
    pg = _is_postgres_connection(db)
    p1, p2 = _placeholder(pg, 1), _placeholder(pg, 2)
    sql = f"""
        SELECT k.cve_id, c.severity, k.short_description
        FROM kev_deadlines k
        LEFT JOIN cves c ON c.cve_id = k.cve_id
        WHERE k.date_added >= {p1} AND k.date_added <= {p2}
        ORDER BY k.date_added DESC, k.cve_id
    """
    rows = await db.execute_fetchall(sql, (start_date, end_date))
    return [
        {
            "cve_id": row["cve_id"],
            "reason": (row["short_description"] or "").strip() or "added to KEV",
            "severity": (row["severity"] or "").strip(),
        }
        for row in rows
    ]


async def _fetch_critical_high(
    db: DbConnection,
    start_bound: str,
    end_bound: str,
) -> list[dict[str, str]]:
    pg = _is_postgres_connection(db)
    p1, p2 = _placeholder(pg, 1), _placeholder(pg, 2)
    sql = f"""
        SELECT cve_id, severity
        FROM cves
        WHERE published >= {p1} AND published < {p2}
          AND UPPER(severity) IN ('CRITICAL', 'HIGH')
        ORDER BY published DESC, cve_id
    """
    rows = await db.execute_fetchall(sql, (start_bound, end_bound))
    return [
        {
            "cve_id": row["cve_id"],
            "reason": "new Critical/High",
            "severity": (row["severity"] or "").strip(),
        }
        for row in rows
    ]


async def _fetch_notifications(
    db: DbConnection,
    *,
    category: str | None,
    categories: tuple[str, ...] | None,
    start_bound: str,
    end_bound: str,
) -> list[dict[str, Any]]:
    pg = _is_postgres_connection(db)
    p_start = _placeholder(pg, 1)
    p_end = _placeholder(pg, 2)
    if category is not None:
        p_cat = _placeholder(pg, 3)
        sql = f"""
            SELECT title, body, entity_type, entity_id, created_at
            FROM user_notifications
            WHERE category = {p_cat}
              AND created_at >= {p_start} AND created_at < {p_end}
            ORDER BY created_at DESC
        """
        params: tuple[Any, ...] = (start_bound, end_bound, category)
    else:
        cats = categories or ()
        placeholders = ", ".join(_placeholder(pg, i + 3) for i in range(len(cats)))
        sql = f"""
            SELECT title, body, entity_type, entity_id, created_at
            FROM user_notifications
            WHERE category IN ({placeholders})
              AND created_at >= {p_start} AND created_at < {p_end}
            ORDER BY created_at DESC
        """
        params = (start_bound, end_bound, *cats)
    return await db.execute_fetchall(sql, params)


def _map_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        reason = (row["title"] or row["body"] or "").strip() or "watchlist alert"
        out.append(
            {
                "cve_id": (row["entity_id"] or "").strip() or "unknown",
                "reason": reason,
                "severity": "",
            }
        )
    return out


def _map_ioc(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        out.append(
            {
                "type": (row["entity_type"] or "").strip(),
                "value": (row["entity_id"] or "").strip(),
                "reason": (row["title"] or row["body"] or "").strip(),
            }
        )
    return out


def _map_ops(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        ident = (row["entity_id"] or row["title"] or "").strip() or "ops"
        reason = (row["body"] or row["title"] or "").strip() or "ops issue"
        out.append({"id": ident, "reason": reason})
    return out


async def collect_daily_brief(
    db: DbConnection,
    *,
    slot: DailyBriefSlot,
    window_start_utc: datetime,
    window_end_utc: datetime,
    tz_name: str,
) -> DailyBrief:
    start_bound = _bound_local(window_start_utc, tz_name)
    end_bound = _bound_local(window_end_utc, tz_name)
    kev_start_date = _date_local(window_start_utc, tz_name)
    kev_end_date = _date_local(window_end_utc, tz_name)
    generated_local = _fmt_local(datetime.now(timezone.utc), tz_name)

    kev_rows = await _fetch_kev(db, kev_start_date, kev_end_date)
    crit_rows = await _fetch_critical_high(db, start_bound, end_bound)
    watch_rows = await _fetch_notifications(
        db,
        category="watchlist",
        categories=None,
        start_bound=start_bound,
        end_bound=end_bound,
    )
    ioc_rows = await _fetch_notifications(
        db,
        category="ioc_watchlist",
        categories=None,
        start_bound=start_bound,
        end_bound=end_bound,
    )
    ops_rows = await _fetch_notifications(
        db,
        category=None,
        categories=_OPS_CATEGORIES,
        start_bound=start_bound,
        end_bound=end_bound,
    )

    watchlist = _map_watchlist(watch_rows)
    ioc = _map_ioc(ioc_rows)
    ops = _map_ops(ops_rows)

    # stack_matches filled in Task 2
    stack: list[dict[str, str]] = []

    counts = {
        "kev_new": len(kev_rows),
        "stack_matches": 0,
        "watchlist": len(watchlist),
        "ioc_hits": len(ioc),
        "critical_high_new": len(crit_rows),
        "ops_issues": len(ops),
    }

    return DailyBrief(
        slot=slot,
        tz_name=tz_name,
        window_start_local=_fmt_local(window_start_utc, tz_name),
        window_end_local=_fmt_local(window_end_utc, tz_name),
        generated_local=generated_local,
        headline="",
        lede_source="template",
        counts=counts,
        kev=kev_rows,
        stack=stack,
        watchlist=watchlist,
        ioc=ioc,
        ops=ops,
    )
