from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from ai.llm_router import any_llm_provider_configured, chat_completion_task
from database import get_db
from db.enrichment import filter_cves_matching_assets
from db.sync_state import get_sync_state_value, set_sync_state_value
from db.types import DbConnection
from preferences.repo import get_alert_stack_assets
from webhooks.destinations import EVENT_DAILY_BRIEF
from webhooks.engine import DISCORD_MAX_CONTENT, dispatch_event

logger = logging.getLogger(__name__)

DailyBriefSlot = Literal["eod", "standup"]

_DAILY_BRIEF_WATERMARK_KEY = "daily_brief:last_eod_end"
_DISABLED_FLAG_VALUES = frozenset({"0", "false", "no", "off", ""})
_MIN_STANDUP_WINDOW = timedelta(minutes=15)

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


async def apply_headline(brief: DailyBrief, *, llm_enabled: bool) -> DailyBrief:
    templated = replace(brief, headline=template_headline(brief), lede_source="template")
    if not llm_enabled or not any_llm_provider_configured():
        return templated
    allowed = {row["cve_id"] for row in brief.kev + brief.stack + brief.watchlist}
    fact_block = format_daily_brief_text(templated, limit=1500)
    completion = await chat_completion_task(
        "pdf_summary",
        messages=[
            {
                "role": "system",
                "content": (
                    "Write 1-3 short sentences for a SOC morning brief. "
                    "Use only CVE IDs present in the user message. No markdown."
                ),
            },
            {"role": "user", "content": fact_block},
        ],
        max_tokens=120,
        context_type="daily_brief",
        context_id=f"{brief.slot}:{brief.window_end_local[:10]}",
    )
    if completion is None or not (completion.content or "").strip():
        return templated
    text = completion.content.strip().split("\n")[0:3]
    lede = " ".join(line.strip() for line in text if line.strip())
    cited = set(re.findall(r"CVE-\d{4}-\d+", lede, flags=re.I))
    cited_norm = {c.upper() for c in cited}
    if cited_norm - {a.upper() for a in allowed} and cited_norm:
        return templated
    return replace(templated, headline=lede[:400], lede_source=completion.provider)


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

    assets = await get_alert_stack_assets(db)
    stack: list[dict[str, str]] = []
    if assets:
        candidate_ids = list(
            dict.fromkeys([r["cve_id"] for r in kev_rows] + [r["cve_id"] for r in crit_rows])
        )
        matched = await filter_cves_matching_assets(db, candidate_ids, assets)
        matched_ids = {row["cve_id"] for row in matched}
        seen: set[str] = set()
        for row in kev_rows:
            cve_id = row["cve_id"]
            if cve_id in matched_ids and cve_id not in seen:
                stack.append(row)
                seen.add(cve_id)
        for row in crit_rows:
            cve_id = row["cve_id"]
            if cve_id in matched_ids and cve_id not in seen:
                stack.append(row)
                seen.add(cve_id)

    counts = {
        "kev_new": len(kev_rows),
        "stack_matches": len(stack),
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


def _env_flag_on(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() not in _DISABLED_FLAG_VALUES


def _brief_timezone() -> str:
    return (
        os.environ.get("SCHEDULER_TIMEZONE")
        or os.environ.get("DEFAULT_TIMEZONE")
        or "UTC"
    ).strip() or "UTC"


def _parse_watermark_utc(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        logger.warning("Invalid daily brief watermark %r — ignoring", raw)
        return None


def brief_to_payload(brief: DailyBrief) -> dict[str, Any]:
    """Structured brief dict attached to webhook payloads / admin preview."""
    return {
        "slot": brief.slot,
        "counts": brief.counts,
        "headline": brief.headline,
        "lede_source": brief.lede_source,
        "kev": brief.kev,
        "stack": brief.stack,
        "watchlist": brief.watchlist,
        "ioc": brief.ioc,
        "ops": brief.ops,
        "window_start_local": brief.window_start_local,
        "window_end_local": brief.window_end_local,
        "tz": brief.tz_name,
    }


async def _window_for_slot(
    db: DbConnection,
    slot: DailyBriefSlot,
    *,
    window_end_utc: datetime,
) -> tuple[datetime, datetime]:
    if slot == "eod":
        return window_end_utc - timedelta(hours=24), window_end_utc
    watermark = _parse_watermark_utc(
        await get_sync_state_value(db, _DAILY_BRIEF_WATERMARK_KEY)
    )
    window_start_utc = watermark or (window_end_utc - timedelta(hours=12))
    return window_start_utc, window_end_utc


async def build_daily_brief_now(slot: DailyBriefSlot) -> tuple[str, DailyBrief]:
    """Collect + headline + format for *now*, ignoring cron enablement flags.

    Used by admin preview / test send so operators can inspect copy while
    ``DAILY_BRIEF_*_ENABLED`` is off. Standup overlapping-window skip is also
    bypassed (preview/test always builds).
    """
    tz_name = _brief_timezone()
    window_end_utc = datetime.now(timezone.utc)
    db = await get_db()
    try:
        window_start_utc, window_end_utc = await _window_for_slot(
            db, slot, window_end_utc=window_end_utc
        )
        brief = await collect_daily_brief(
            db,
            slot=slot,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
            tz_name=tz_name,
        )
        brief = await apply_headline(
            brief,
            llm_enabled=_env_flag_on("DAILY_BRIEF_LLM_ENABLED", "0"),
        )
        text = format_daily_brief_text(brief, limit=DISCORD_MAX_CONTENT)
        return text, brief
    finally:
        await db.close()


async def run_daily_brief_slot(slot: DailyBriefSlot) -> dict[str, Any]:
    flag = "DAILY_BRIEF_EOD_ENABLED" if slot == "eod" else "DAILY_BRIEF_STANDUP_ENABLED"
    if not _env_flag_on(flag, "0"):
        return {"status": "skipped", "reason": "disabled", "slot": slot}

    tz_name = _brief_timezone()
    window_end_utc = datetime.now(timezone.utc)
    db = await get_db()
    try:
        window_start_utc, window_end_utc = await _window_for_slot(
            db, slot, window_end_utc=window_end_utc
        )
        if slot == "standup" and window_end_utc - window_start_utc < _MIN_STANDUP_WINDOW:
            logger.info(
                "Daily brief standup skipped — window shorter than 15 minutes "
                "(start=%s end=%s)",
                window_start_utc.isoformat(),
                window_end_utc.isoformat(),
            )
            return {"status": "skipped", "reason": "overlapping", "slot": slot}

        brief = await collect_daily_brief(
            db,
            slot=slot,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
            tz_name=tz_name,
        )
        brief = await apply_headline(
            brief,
            llm_enabled=_env_flag_on("DAILY_BRIEF_LLM_ENABLED", "0"),
        )
        text = format_daily_brief_text(brief, limit=DISCORD_MAX_CONTENT)
        extra = {"brief": brief_to_payload(brief)}
        local_date = brief.window_end_local[:10]
        result = await dispatch_event(
            EVENT_DAILY_BRIEF,
            text,
            dedupe_key=f"{slot}:{local_date}",
            payload_extra=extra,
        )
        if slot == "eod" and result.get("status") in {"ok", "partial"}:
            await set_sync_state_value(
                db,
                _DAILY_BRIEF_WATERMARK_KEY,
                window_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            await db.commit()
        return {**result, "slot": slot}
    finally:
        await db.close()
