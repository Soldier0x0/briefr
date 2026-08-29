from __future__ import annotations

import html
import logging
import os
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from ai.llm_router import any_llm_provider_configured, chat_completion_task
from database import get_db, get_feed_cache
from db.enrichment import filter_cves_matching_assets
from db.sync_state import get_sync_state_value, set_sync_state_value
from db.types import DbConnection
from preferences.repo import get_alert_stack_assets
from redact import mask_webhook_delivery_error
from reports.market_clusters import (
    UNANALYZED_LABEL,
    cluster_published,
    format_market_section,
    is_unmapped_product,
    unmapped_coverage,
)
from webhooks.destinations import EVENT_DAILY_BRIEF
from webhooks.engine import DISCORD_MAX_CONTENT, TELEGRAM_MAX_TEXT, dispatch_event

logger = logging.getLogger(__name__)

DailyBriefSlot = Literal["eod", "standup"]

_DAILY_BRIEF_WATERMARK_KEY = "daily_brief:last_eod_end"
_DISABLED_FLAG_VALUES = frozenset({"0", "false", "no", "off", ""})
_MIN_STANDUP_WINDOW = timedelta(minutes=15)
_LIST_QUERY_LIMIT = 50
_MARKET_QUERY_LIMIT = 5000
_OPS_REASON_LIMIT = 120
_IOC_SUMMARY_RE = re.compile(
    r"^IOC watchlist hit\s*\((?P<source>[^)]+)\):\s*(?P<type>[A-Za-z0-9_-]+)\s+",
    flags=re.I,
)
_IOC_TITLE_RE = re.compile(r"^IOC watchlist hit\s*\((?P<source>[^)]+)\)", flags=re.I)

COUNT_KEYS = (
    "kev_new",
    "stack_matches",
    "watchlist",
    "ioc_hits",
    "critical_high_new",
    "ops_issues",
)

LIST_DROP_ORDER = ("ops", "ioc", "watchlist", "stack", "kev", "advisories", "headlines")
EMBED_DROP_ORDER = ("ioc", "watchlist", "stack", "kev", "advisories", "headlines")
DISCORD_EMBED_COLOR = 0xE85533
TELEGRAM_HTML_TARGET = 3500
_HEADLINE_LIMIT = 3
_ADVISORY_LIMIT = 2
_TITLE_SLICE = 120
_SNAPSHOT_CACHE_KEY = "incident_feed:snapshot"
_SNAPSHOT_MAX_AGE_HOURS = 14 * 24
_COVERAGE_BLURB = (
    "Unmapped means NVD has not given these CVEs a product (CPE) yet. "
    "BRIEFR does not guess from the description. KEV and other prioritized "
    "CVEs are often named within about one business day. Most others can stay "
    "Unmapped for days, weeks, or never. This briefing is a snapshot; later "
    "CPE does not rewrite this message."
)
_JOB_DISPLAY = {
    "nvd_incremental_sync": "NVD Incremental Sync",
    "kev_metadata_sync": "KEV Metadata Sync",
    "cpe_catalog_sync": "NVD CPE Software Catalog Sync",
    "epss_score_sync": "EPSS Score Sync",
    "weekly_mitre_refresh": "Weekly MITRE ATT&CK + ATLAS Refresh",
    "incident_feed_refresh": "Incident Feed Snapshot Refresh",
    "publication_source_sync": "Publication Source Sync",
    "nightly_correlation": "BRIEFR Nightly Correlation Engine",
    "llm_product_extraction": "LLM Product Extraction",
    "api_key_health_check": "API Key Health Check",
    "watchlist_monitor": "Watchlist Monitor Alerts",
    "daily_brief_eod": "End-of-Day Daily Brief Webhook",
    "daily_brief_standup": "Morning Standup Daily Brief Webhook",
}

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
    market: dict = field(default_factory=lambda: cluster_published([]))
    headlines: list[dict[str, str]] = field(default_factory=list)
    advisories: list[dict[str, str]] = field(default_factory=list)


def _fmt_local(dt: datetime, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")


def _date_local(dt: datetime, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    return dt.astimezone(tz).strftime("%Y-%m-%d")


def _bound_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _kev_date_predicate(start_date: str, end_date: str, p1: str, p2: str) -> str:
    # Same-day windows would otherwise become `> D AND <= D` and match nothing.
    lower_op = ">=" if start_date == end_date else ">"
    return f"k.date_added {lower_op} {p1} AND k.date_added <= {p2}"


def slot_title(slot: DailyBriefSlot) -> str:
    return "End of day" if slot == "eod" else "Morning briefing"


def _job_display_name(job_id: str) -> str:
    ident = (job_id or "").strip()
    if ident in _JOB_DISPLAY:
        return _JOB_DISPLAY[ident]
    cleaned = ident.replace("_", " ").strip()
    return cleaned or ident or "job"


def _ops_headline_phrase(brief: DailyBrief) -> str:
    n = int(brief.counts.get("ops_issues") or 0)
    if n <= 0:
        return ""
    classes = {(row.get("error_class") or "").strip() for row in (brief.ops or [])}
    classes.discard("")
    if classes == {"job_error"}:
        noun = "scheduler problem" if n == 1 else "scheduler problems"
        return f"{n} {noun}."
    noun = "instance problem" if n == 1 else "instance problems"
    return f"{n} {noun}."


def format_ops_lines(row: dict[str, str]) -> list[str]:
    error_class = (row.get("error_class") or "").strip()
    ident = (row.get("id") or "").strip() or "ops"
    reason = (row.get("reason") or "").strip()
    if error_class == "job_error":
        name = _job_display_name(ident)
        lines = [f"Scheduler job failed: {name}"]
        if ident == "kev_metadata_sync":
            lines.append("CISA KEV list may be stale until this job succeeds.")
        if reason:
            lines.append(f"Detail: {reason}")
        return lines
    if error_class == "api_key_unhealthy":
        lines = [f"API key unhealthy: {_job_display_name(ident)}"]
        if reason:
            lines.append(f"Detail: {reason}")
        return lines
    if error_class == "webhook_failure":
        lines = [f"Webhook delivery failed: {ident}"]
        if reason:
            lines.append(f"Detail: {reason}")
        return lines
    if reason:
        return [f"{ident} — {reason}"]
    return [ident]


def coverage_lines(market: dict) -> list[str]:
    cov = unmapped_coverage(market)
    return [
        f"Named products {cov['named']} of {cov['published']} · Unmapped {cov['unmapped']}",
        _COVERAGE_BLURB,
    ]


def template_headline(brief: DailyBrief) -> str:
    c = brief.counts
    published = int(brief.market.get("published", 0))
    if published == 0 and all(c[k] == 0 for k in COUNT_KEYS):
        return "Quiet window."
    parts = []
    if published:
        parts.append(f"{published} published.")
        products = brief.market.get("products") or []
        analyzed_leader = next(
            (
                product
                for product in products
                if not is_unmapped_product(product)
                and product.get("label") != UNANALYZED_LABEL
            ),
            None,
        )
        if analyzed_leader:
            parts.append(f"{analyzed_leader['label']} led volume.")
        cov = unmapped_coverage(brief.market)
        if cov["published"] and cov["unmapped"] / cov["published"] >= 0.5:
            parts.append(
                f"{cov['unmapped']} of {cov['published']} published CVEs have "
                "no product mapped yet (Unmapped)."
            )
    if c["kev_new"]:
        parts.append(f"{c['kev_new']} new KEV.")
    if c["stack_matches"]:
        stack_noun = "stack match" if c["stack_matches"] == 1 else "stack matches"
        parts.append(f"{c['stack_matches']} {stack_noun}.")
    if c["watchlist"]:
        parts.append(f"Watchlist: {c['watchlist']}.")
    if c["ioc_hits"]:
        parts.append(f"{c['ioc_hits']} IOC hit(s).")
    if c["critical_high_new"] and not c["kev_new"]:
        parts.append(f"{c['critical_high_new']} new Critical/High.")
    ops_phrase = _ops_headline_phrase(brief)
    if ops_phrase:
        parts.append(ops_phrase)
    return " ".join(parts) or "Quiet window."


async def apply_headline(brief: DailyBrief, *, llm_enabled: bool) -> DailyBrief:
    templated = replace(brief, headline=template_headline(brief), lede_source="template")
    if not llm_enabled or not any_llm_provider_configured():
        return templated
    allowed = {row["cve_id"] for row in brief.kev + brief.stack + brief.watchlist}
    llm_ops = [
        {
            "id": row["id"],
            "reason": row.get("error_class") or "ops_issue",
        }
        for row in brief.ops
    ]
    llm_brief = replace(templated, ops=llm_ops)
    fact_block = format_daily_brief_text(llm_brief, limit=1500)
    try:
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
    except Exception:
        logger.warning("Daily brief LLM headline failed; using template")
        return templated
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
        "headlines": len(brief.headlines or []),
        "advisories": len(brief.advisories or []),
    }


def _link_line(row: dict[str, str]) -> str:
    source = (row.get("source") or "").strip()
    title = (row.get("title") or "").strip()
    if source and title:
        return f"• {source} — {title}"
    return f"• {title or source}"


def format_daily_brief_text(brief: DailyBrief, *, limit: int) -> str:
    footer_line = (
        f"BRIEFR — generated {brief.generated_local} {brief.tz_name} | "
        f"slot={brief.slot} | facts=local | lede={brief.lede_source}"
    )

    def build_sections(headline_text: str) -> dict[str, list[str]]:
        ops_body: list[str] = []
        for row in brief.ops[:5]:
            ops_body.extend(f"• {line}" if i == 0 else f"  {line}" for i, line in enumerate(format_ops_lines(row)))
        sections: dict[str, list[str]] = {
            "masthead": [
                f"BRIEFR {slot_title(brief.slot)}",
                f"{brief.window_start_local} → {brief.window_end_local} ({brief.tz_name})",
            ],
            "headline": ["Summary", headline_text or "Quiet window."],
            "counts": ["At a glance"]
            + [
                f"New on CISA KEV: {brief.counts['kev_new']}",
                f"Matches My Stack: {brief.counts['stack_matches']}",
                f"Pinned-CVE alerts: {brief.counts['watchlist']}",
                f"IOC watch hits: {brief.counts['ioc_hits']}",
                f"New Critical or High: {brief.counts['critical_high_new']}",
                f"Instance problems: {brief.counts['ops_issues']}",
            ],
            "market": format_market_section(brief.market),
            "headlines": ["Headlines"] + [_link_line(r) for r in brief.headlines[:_HEADLINE_LIMIT]],
            "advisories": ["Advisories"] + [_link_line(r) for r in brief.advisories[:_ADVISORY_LIMIT]],
            "kev": ["CISA KEV"] + [_line_cve(r) for r in brief.kev[:8]],
            "stack": ["My Stack"] + [_line_cve(r) for r in brief.stack[:8]],
            "watchlist": ["Pinned CVEs"] + [_line_cve(r) for r in brief.watchlist[:8]],
            "ioc": ["IOC watch"]
            + [
                f"• {r.get('type', '')} {r.get('value', '')} — {r.get('reason', '')}".strip()
                for r in brief.ioc[:5]
            ],
            "ops": ["Instance problems"] + ops_body,
            "footer": [footer_line],
        }
        for key in ("kev", "stack", "watchlist", "ioc", "ops", "headlines", "advisories"):
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
            "market",
            "headlines",
            "advisories",
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
        for name in ("kev", "stack", "watchlist", "ioc", "ops", "advisories", "headlines")
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


def _parse_aware_utc(raw: str | None) -> datetime | None:
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _slice_title(title: str) -> str:
    cleaned = " ".join((title or "").split())
    if len(cleaned) <= _TITLE_SLICE:
        return cleaned
    return cleaned[: _TITLE_SLICE - 1].rstrip() + "…"


def _normalize_url(url: str) -> str:
    return (url or "").strip().rstrip("/").lower()


async def _fetch_headlines(
    db: DbConnection,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> list[dict[str, str]]:
    snapshot = await get_feed_cache(db, _SNAPSHOT_CACHE_KEY, _SNAPSHOT_MAX_AGE_HOURS)
    if not snapshot:
        return []
    cards = snapshot.get("cards") if isinstance(snapshot, dict) else None
    if not isinstance(cards, list):
        return []
    scored: list[tuple[datetime, dict[str, str]]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        if str(card.get("kind") or "").strip().lower() == "atlas":
            continue
        published = _parse_aware_utc(card.get("publishedAt") or card.get("published_at"))
        if published is None:
            continue
        if published < window_start_utc or published >= window_end_utc:
            continue
        title = _slice_title(str(card.get("title") or ""))
        url = str(card.get("url") or "").strip()
        source = str(card.get("source") or card.get("sourceId") or "").strip()
        if not title:
            continue
        scored.append(
            (
                published,
                {"source": source or "News", "title": title, "url": url},
            )
        )
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:_HEADLINE_LIMIT]]


async def _fetch_advisories(
    db: DbConnection,
    start_bound: str,
    end_bound: str,
) -> list[dict[str, str]]:
    pg = _is_postgres_connection(db)
    p1, p2 = _placeholder(pg, 1), _placeholder(pg, 2)
    published_norm = "REPLACE(SUBSTR(published_at, 1, 19), 'T', ' ')"
    rows = await db.execute_fetchall(
        f"""
        SELECT title, canonical_url, source_key, published_at
        FROM publications
        WHERE {published_norm} >= {p1}
          AND {published_norm} < {p2}
        ORDER BY published_at DESC
        LIMIT 20
        """,
        (start_bound, end_bound),
    )
    items = [dict(row) for row in rows]
    preferred = [row for row in items if (row.get("source_key") or "") == "cisa-news"]
    chosen = (preferred or items)[:_ADVISORY_LIMIT]
    out: list[dict[str, str]] = []
    for row in chosen:
        source_key = (row.get("source_key") or "").strip()
        source = "CISA" if source_key in {"cisa-news", "cisa"} else (source_key or "Advisory")
        out.append(
            {
                "source": source,
                "title": _slice_title(str(row.get("title") or "")),
                "url": str(row.get("canonical_url") or "").strip(),
            }
        )
    return [row for row in out if row["title"]]


def _dedupe_headlines(
    headlines: list[dict[str, str]],
    advisories: list[dict[str, str]],
) -> list[dict[str, str]]:
    advisory_urls = {_normalize_url(row.get("url") or "") for row in advisories}
    advisory_urls.discard("")
    kept: list[dict[str, str]] = []
    for row in headlines:
        url = _normalize_url(row.get("url") or "")
        if url and url in advisory_urls:
            continue
        kept.append(row)
    return kept[:_HEADLINE_LIMIT]


def _field(name: str, value: str, *, inline: bool = False) -> dict[str, Any]:
    clipped = value if len(value) <= 1024 else value[:1023] + "…"
    return {"name": name[:256], "value": clipped or "—", "inline": inline}


def _products_for_display(market: dict, *, limit: int | None = None) -> list[dict]:
    products = list(market.get("products") or [])
    unmapped = [p for p in products if is_unmapped_product(p)]
    rest = [p for p in products if not is_unmapped_product(p)]
    ordered = unmapped + rest
    if limit is None:
        return ordered
    return ordered[:limit]


def _product_line(product: dict) -> str:
    return (
        f"{product['label']}  {product['total']}  "
        f"(Critical {product['critical']} · High {product['high']} · "
        f"Medium {product['medium']} · Low {product['low']})"
    )


def _window_end_iso(brief: DailyBrief) -> str | None:
    try:
        naive = datetime.strptime(brief.window_end_local, "%Y-%m-%d %H:%M")
        tz = ZoneInfo(brief.tz_name)
        return naive.replace(tzinfo=tz).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except Exception:
        return None


def _embed_char_count(embed: dict[str, Any]) -> int:
    total = len(embed.get("title") or "") + len(embed.get("description") or "")
    author = embed.get("author") or {}
    total += len(author.get("name") or "")
    footer = embed.get("footer") or {}
    total += len(footer.get("text") or "")
    for item in embed.get("fields") or []:
        total += len(item.get("name") or "") + len(item.get("value") or "")
    return total


def _glance_text(brief: DailyBrief) -> str:
    return "\n".join(
        [
            f"New on CISA KEV: {brief.counts['kev_new']}",
            f"Matches My Stack: {brief.counts['stack_matches']}",
            f"Pinned-CVE alerts: {brief.counts['watchlist']}",
            f"IOC watch hits: {brief.counts['ioc_hits']}",
            f"New Critical or High: {brief.counts['critical_high_new']}",
            f"Instance problems: {brief.counts['ops_issues']}",
        ]
    )


def format_daily_brief_embed(brief: DailyBrief) -> list[dict[str, Any]]:
    summary = brief.headline or "Quiet window."
    description = (
        f"{brief.window_start_local} → {brief.window_end_local} ({brief.tz_name})\n\n"
        f"{summary}"
    )
    if len(description) > 4096:
        description = description[:4095] + "…"

    published = int(brief.market.get("published") or 0)
    fields: list[dict[str, Any]] = []
    field_ids: list[str] = []

    def add(fid: str, field: dict[str, Any]) -> None:
        fields.append(field)
        field_ids.append(fid)

    if published > 0:
        add("critical", _field("Critical", str(brief.market.get("critical") or 0), inline=True))
        add("high", _field("High", str(brief.market.get("high") or 0), inline=True))
        add("medium", _field("Medium", str(brief.market.get("medium") or 0), inline=True))
        add("low", _field("Low", str(brief.market.get("low") or 0), inline=True))
        add("coverage", _field("Coverage", "\n".join(coverage_lines(brief.market))))
    add("glance", _field("At a glance", _glance_text(brief)))
    if published > 0:
        product_lines = [_product_line(p) for p in _products_for_display(brief.market)]
        add("products", _field("Published by product", "\n".join(product_lines)))
    if brief.headlines:
        add("headlines", _field("Headlines", "\n".join(_link_line(r) for r in brief.headlines)))
    if brief.advisories:
        add("advisories", _field("Advisories", "\n".join(_link_line(r) for r in brief.advisories)))
    if brief.kev:
        add("kev", _field("CISA KEV", "\n".join(_line_cve(r) for r in brief.kev[:8])))
    if brief.stack:
        add("stack", _field("My Stack", "\n".join(_line_cve(r) for r in brief.stack[:8])))
    if brief.watchlist:
        add("watchlist", _field("Pinned CVEs", "\n".join(_line_cve(r) for r in brief.watchlist[:8])))
    if brief.ioc:
        add(
            "ioc",
            _field(
                "IOC watch",
                "\n".join(
                    f"• {r.get('type', '')} {r.get('value', '')} — {r.get('reason', '')}".strip()
                    for r in brief.ioc[:5]
                ),
            ),
        )
    if brief.ops:
        ops_lines: list[str] = []
        for row in brief.ops[:5]:
            ops_lines.extend(format_ops_lines(row))
        add("ops", _field("Instance problems", "\n".join(ops_lines)))

    embed: dict[str, Any] = {
        "author": {"name": "BRIEFR"},
        "title": slot_title(brief.slot),
        "color": DISCORD_EMBED_COLOR,
        "description": description,
        "fields": fields,
        "footer": {
            "text": (
                f"Generated {brief.generated_local} {brief.tz_name} · "
                f"local facts · {brief.lede_source}"
            )
        },
    }
    stamp = _window_end_iso(brief)
    if stamp:
        embed["timestamp"] = stamp

    def over_limit() -> bool:
        return len(embed["fields"]) > 25 or _embed_char_count(embed) > 6000

    for drop_id in EMBED_DROP_ORDER:
        if not over_limit():
            break
        kept_fields = []
        kept_ids = []
        for fid, embed_field in zip(field_ids, embed["fields"], strict=True):
            if fid == drop_id:
                continue
            kept_fields.append(embed_field)
            kept_ids.append(fid)
        embed["fields"] = kept_fields
        field_ids = kept_ids

    if over_limit() and "products" in field_ids:
        trimmed = [_product_line(p) for p in _products_for_display(brief.market, limit=5)]
        idx = field_ids.index("products")
        embed["fields"][idx] = _field("Published by product", "\n".join(trimmed))

    return [embed]


def format_daily_brief_html(brief: DailyBrief) -> str:
    def esc(value: str) -> str:
        return html.escape(value or "", quote=False)

    chunks: list[str] = [
        "<b>BRIEFR</b>",
        f"<b>{esc(slot_title(brief.slot))}</b>",
        esc(f"{brief.window_start_local} → {brief.window_end_local} ({brief.tz_name})"),
        "",
        "<b>Summary</b>",
        esc(brief.headline or "Quiet window."),
        "",
        "<b>At a glance</b>",
        esc(_glance_text(brief)),
    ]
    if int(brief.market.get("published") or 0) > 0:
        chunks.extend(
            [
                "",
                "<b>Coverage</b>",
                esc("\n".join(coverage_lines(brief.market))),
                "",
                "<b>Severity mix</b>",
                esc(
                    f"Critical {brief.market.get('critical') or 0} · "
                    f"High {brief.market.get('high') or 0} · "
                    f"Medium {brief.market.get('medium') or 0} · "
                    f"Low {brief.market.get('low') or 0}"
                ),
                "",
                "<b>Published by product</b>",
                esc("\n".join(_product_line(p) for p in _products_for_display(brief.market))),
            ]
        )
    if brief.headlines:
        chunks.extend(["", "<b>Headlines</b>", esc("\n".join(_link_line(r) for r in brief.headlines))])
    if brief.advisories:
        chunks.extend(["", "<b>Advisories</b>", esc("\n".join(_link_line(r) for r in brief.advisories))])
    if brief.kev:
        chunks.extend(["", "<b>CISA KEV</b>", esc("\n".join(_line_cve(r) for r in brief.kev[:8]))])
    if brief.stack:
        chunks.extend(["", "<b>My Stack</b>", esc("\n".join(_line_cve(r) for r in brief.stack[:8]))])
    if brief.watchlist:
        chunks.extend(["", "<b>Pinned CVEs</b>", esc("\n".join(_line_cve(r) for r in brief.watchlist[:8]))])
    if brief.ioc:
        chunks.extend(
            [
                "",
                "<b>IOC watch</b>",
                esc(
                    "\n".join(
                        f"• {r.get('type', '')} {r.get('value', '')} — {r.get('reason', '')}".strip()
                        for r in brief.ioc[:5]
                    )
                ),
            ]
        )
    if brief.ops:
        ops_lines: list[str] = []
        for row in brief.ops[:5]:
            ops_lines.extend(format_ops_lines(row))
        chunks.extend(["", "<b>Instance problems</b>", esc("\n".join(ops_lines))])
    chunks.extend(
        [
            "",
            esc(
                f"Generated {brief.generated_local} {brief.tz_name} · "
                f"local facts · {brief.lede_source}"
            ),
        ]
    )
    body = "\n".join(chunks)
    if len(body) > TELEGRAM_HTML_TARGET:
        body = body[: TELEGRAM_HTML_TARGET - 1] + "…"
    if len(body) > TELEGRAM_MAX_TEXT:
        body = body[: TELEGRAM_MAX_TEXT - 1] + "…"
    return body


def daily_brief_channel_payloads(brief: DailyBrief) -> dict[str, Any]:
    return {
        "text": format_daily_brief_text(brief, limit=DISCORD_MAX_CONTENT),
        "html": format_daily_brief_html(brief),
        "discord_embeds": format_daily_brief_embed(brief),
    }


async def _fetch_kev(
    db: DbConnection,
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, str]], int]:
    pg = _is_postgres_connection(db)
    p1, p2 = _placeholder(pg, 1), _placeholder(pg, 2)
    predicate = _kev_date_predicate(start_date, end_date, p1, p2)
    rows = await db.execute_fetchall(
        f"""
        SELECT k.cve_id, c.severity, k.short_description
        FROM kev_deadlines k
        LEFT JOIN cves c ON c.cve_id = k.cve_id
        WHERE {predicate}
        ORDER BY k.date_added DESC, k.cve_id
        LIMIT {_LIST_QUERY_LIMIT}
        """,
        (start_date, end_date),
    )
    count_rows = await db.execute_fetchall(
        f"SELECT COUNT(*) AS cnt FROM kev_deadlines k WHERE {predicate}",
        (start_date, end_date),
    )
    items = [
        {
            "cve_id": row["cve_id"],
            "reason": (row["short_description"] or "").strip() or "added to KEV",
            "severity": (row["severity"] or "").strip(),
        }
        for row in rows
    ]
    total = int(count_rows[0]["cnt"]) if count_rows else 0
    return items, total


async def _fetch_critical_high(
    db: DbConnection,
    start_bound: str,
    end_bound: str,
) -> tuple[list[dict[str, str]], int]:
    pg = _is_postgres_connection(db)
    p1, p2 = _placeholder(pg, 1), _placeholder(pg, 2)
    predicate = f"""
        REPLACE(SUBSTR(published, 1, 19), 'T', ' ') >= {p1}
        AND REPLACE(SUBSTR(published, 1, 19), 'T', ' ') < {p2}
        AND UPPER(severity) IN ('CRITICAL', 'HIGH')
    """
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, severity
        FROM cves
        WHERE {predicate}
        ORDER BY published DESC, cve_id
        LIMIT {_LIST_QUERY_LIMIT}
        """,
        (start_bound, end_bound),
    )
    count_rows = await db.execute_fetchall(
        f"SELECT COUNT(*) AS cnt FROM cves WHERE {predicate}",
        (start_bound, end_bound),
    )
    items = [
        {
            "cve_id": row["cve_id"],
            "reason": "new Critical/High",
            "severity": (row["severity"] or "").strip(),
        }
        for row in rows
    ]
    total = int(count_rows[0]["cnt"]) if count_rows else 0
    return items, total


async def _fetch_published_market_rows(
    db: DbConnection,
    start_bound: str,
    end_bound: str,
) -> list[dict[str, Any]]:
    pg = _is_postgres_connection(db)
    p1, p2 = _placeholder(pg, 1), _placeholder(pg, 2)
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, severity, cpe_matches, affected_products
        FROM cves
        WHERE REPLACE(SUBSTR(published, 1, 19), 'T', ' ') >= {p1}
          AND REPLACE(SUBSTR(published, 1, 19), 'T', ' ') < {p2}
        ORDER BY published DESC, cve_id
        LIMIT {_MARKET_QUERY_LIMIT}
        """,
        (start_bound, end_bound),
    )
    return [dict(row) for row in rows]


async def _fetch_published_market_totals(
    db: DbConnection,
    start_bound: str,
    end_bound: str,
) -> dict[str, int]:
    pg = _is_postgres_connection(db)
    p1, p2 = _placeholder(pg, 1), _placeholder(pg, 2)
    severity_group = """
        CASE UPPER(COALESCE(severity, ''))
            WHEN 'CRITICAL' THEN 'critical'
            WHEN 'HIGH' THEN 'high'
            WHEN 'LOW' THEN 'low'
            ELSE 'medium'
        END
    """
    rows = await db.execute_fetchall(
        f"""
        SELECT {severity_group} AS severity_group, COUNT(*) AS cnt
        FROM cves
        WHERE REPLACE(SUBSTR(published, 1, 19), 'T', ' ') >= {p1}
          AND REPLACE(SUBSTR(published, 1, 19), 'T', ' ') < {p2}
        GROUP BY {severity_group}
        """,
        (start_bound, end_bound),
    )
    totals = {"published": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}
    for row in rows:
        severity = str(row["severity_group"])
        count = int(row["cnt"])
        totals[severity] = count
        totals["published"] += count
    return totals


async def _fetch_notifications(
    db: DbConnection,
    *,
    category: str | None,
    categories: tuple[str, ...] | None,
    start_bound: str,
    end_bound: str,
) -> tuple[list[dict[str, Any]], int]:
    pg = _is_postgres_connection(db)
    p_start = _placeholder(pg, 1)
    p_end = _placeholder(pg, 2)
    if category is not None:
        p_cat = _placeholder(pg, 3)
        category_predicate = f"category = {p_cat}"
        params: tuple[Any, ...] = (start_bound, end_bound, category)
    else:
        cats = categories or ()
        if not cats:
            return [], 0
        placeholders = ", ".join(_placeholder(pg, i + 3) for i in range(len(cats)))
        category_predicate = f"category IN ({placeholders})"
        params = (start_bound, end_bound, *cats)
    predicate = (
        f"created_at >= {p_start} AND created_at < {p_end} "
        f"AND {category_predicate}"
    )
    rows = await db.execute_fetchall(
        f"""
        WITH matching AS (
            SELECT category, title, body, entity_type, entity_id,
                   dedupe_key, created_at,
                   ROW_NUMBER() OVER (PARTITION BY dedupe_key ORDER BY id) AS event_row
            FROM user_notifications
            WHERE {predicate}
        )
        SELECT category, title, body, entity_type, entity_id, dedupe_key, created_at
        FROM matching
        WHERE event_row = 1
        ORDER BY created_at DESC
        LIMIT {_LIST_QUERY_LIMIT}
        """,
        params,
    )
    count_rows = await db.execute_fetchall(
        f"""
        SELECT COUNT(DISTINCT dedupe_key) AS cnt
        FROM user_notifications
        WHERE {predicate}
        """,
        params,
    )
    total = int(count_rows[0]["cnt"]) if count_rows else 0
    return [dict(row) for row in rows], total


def _map_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        cve_id = (row["entity_id"] or "").strip() or "unknown"
        title = (row["title"] or "").strip()
        prefix = f"{cve_id} — "
        if title.casefold().startswith(prefix.casefold()):
            title = title[len(prefix) :].strip()
        reason = title or (row["body"] or "").strip() or "watchlist alert"
        out.append(
            {
                "cve_id": cve_id,
                "reason": reason,
                "severity": "",
            }
        )
    return out


def _map_ioc(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        body = (row["body"] or "").strip()
        title = (row["title"] or "").strip()
        summary_match = _IOC_SUMMARY_RE.match(body)
        title_match = _IOC_TITLE_RE.match(title)
        stored_type = (row["entity_type"] or "").strip()
        ioc_type = (
            summary_match.group("type")
            if summary_match
            else (stored_type if stored_type.lower() != "ioc" else "unknown")
        )
        source = (
            summary_match.group("source")
            if summary_match
            else (title_match.group("source") if title_match else "unknown")
        )
        out.append(
            {
                "type": ioc_type.upper(),
                "value": (row["entity_id"] or "").strip(),
                "reason": source.upper(),
            }
        )
    return out


def _map_ops(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        ident = (row["entity_id"] or row["title"] or "").strip() or "ops"
        reason = (row["body"] or row["title"] or "").strip() or "ops issue"
        reason = mask_webhook_delivery_error(reason) or "ops issue"
        if len(reason) > _OPS_REASON_LIMIT:
            reason = reason[: _OPS_REASON_LIMIT - 1].rstrip() + "…"
        error_class = (row.get("category") or "ops_issue").strip() or "ops_issue"
        out.append({"id": ident, "reason": reason, "error_class": error_class})
    return out


async def _fetch_stack_candidate_page(
    db: DbConnection,
    *,
    kev_start_date: str,
    kev_end_date: str,
    start_bound: str,
    end_bound: str,
    offset: int,
) -> list[dict[str, str]]:
    pg = _is_postgres_connection(db)
    p1 = _placeholder(pg, 1)
    p2 = _placeholder(pg, 2)
    p3 = _placeholder(pg, 3)
    p4 = _placeholder(pg, 4)
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, severity, reason, source_order, sort_value
        FROM (
            SELECT k.cve_id,
                   COALESCE(c.severity, '') AS severity,
                   COALESCE(NULLIF(k.short_description, ''), 'added to KEV') AS reason,
                   0 AS source_order,
                   k.date_added AS sort_value
            FROM kev_deadlines k
            LEFT JOIN cves c ON c.cve_id = k.cve_id
            WHERE {_kev_date_predicate(kev_start_date, kev_end_date, p1, p2)}

            UNION ALL

            SELECT cve_id,
                   COALESCE(severity, '') AS severity,
                   'new Critical/High' AS reason,
                   1 AS source_order,
                   REPLACE(SUBSTR(published, 1, 19), 'T', ' ') AS sort_value
            FROM cves
            WHERE REPLACE(SUBSTR(published, 1, 19), 'T', ' ') >= {p3}
              AND REPLACE(SUBSTR(published, 1, 19), 'T', ' ') < {p4}
              AND UPPER(severity) IN ('CRITICAL', 'HIGH')
        ) candidates
        ORDER BY source_order, sort_value DESC, cve_id
        LIMIT {_LIST_QUERY_LIMIT} OFFSET {max(0, int(offset))}
        """,
        (kev_start_date, kev_end_date, start_bound, end_bound),
    )
    return [dict(row) for row in rows]


async def _collect_stack(
    db: DbConnection,
    *,
    assets: list[dict[str, str]],
    kev_start_date: str,
    kev_end_date: str,
    start_bound: str,
    end_bound: str,
) -> tuple[list[dict[str, str]], int]:
    if not assets:
        return [], 0
    stack: list[dict[str, str]] = []
    matched_total = 0
    seen_candidates: set[str] = set()
    offset = 0
    while True:
        page = await _fetch_stack_candidate_page(
            db,
            kev_start_date=kev_start_date,
            kev_end_date=kev_end_date,
            start_bound=start_bound,
            end_bound=end_bound,
            offset=offset,
        )
        candidates = [
            row
            for row in page
            if row["cve_id"] and row["cve_id"] not in seen_candidates
        ]
        for row in candidates:
            seen_candidates.add(row["cve_id"])
        matched = await filter_cves_matching_assets(
            db,
            [row["cve_id"] for row in candidates],
            assets,
        )
        matched_ids = {row["cve_id"] for row in matched}
        for row in candidates:
            if row["cve_id"] not in matched_ids:
                continue
            matched_total += 1
            if len(stack) < _LIST_QUERY_LIMIT:
                stack.append(
                    {
                        "cve_id": row["cve_id"],
                        "reason": row["reason"],
                        "severity": row["severity"],
                    }
                )
        if len(page) < _LIST_QUERY_LIMIT:
            break
        offset += len(page)
    return stack, matched_total


async def collect_daily_brief(
    db: DbConnection,
    *,
    slot: DailyBriefSlot,
    window_start_utc: datetime,
    window_end_utc: datetime,
    tz_name: str,
) -> DailyBrief:
    start_bound = _bound_utc(window_start_utc)
    end_bound = _bound_utc(window_end_utc)
    kev_start_date = _date_local(window_start_utc, tz_name)
    kev_end_date = _date_local(window_end_utc, tz_name)
    generated_local = _fmt_local(datetime.now(timezone.utc), tz_name)

    kev_rows, kev_total = await _fetch_kev(db, kev_start_date, kev_end_date)
    crit_rows, crit_total = await _fetch_critical_high(db, start_bound, end_bound)
    market_rows = await _fetch_published_market_rows(db, start_bound, end_bound)
    market_totals = await _fetch_published_market_totals(db, start_bound, end_bound)
    watch_rows, watch_total = await _fetch_notifications(
        db,
        category="watchlist",
        categories=None,
        start_bound=start_bound,
        end_bound=end_bound,
    )
    ioc_rows, ioc_total = await _fetch_notifications(
        db,
        category="ioc_watchlist",
        categories=None,
        start_bound=start_bound,
        end_bound=end_bound,
    )
    ops_rows, ops_total = await _fetch_notifications(
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
    stack, stack_total = await _collect_stack(
        db,
        assets=assets,
        kev_start_date=kev_start_date,
        kev_end_date=kev_end_date,
        start_bound=start_bound,
        end_bound=end_bound,
    )

    counts = {
        "kev_new": kev_total,
        "stack_matches": stack_total,
        "watchlist": watch_total,
        "ioc_hits": ioc_total,
        "critical_high_new": crit_total,
        "ops_issues": ops_total,
    }
    market = cluster_published(market_rows)
    market.update(market_totals)
    headlines = await _fetch_headlines(db, window_start_utc, window_end_utc)
    advisories = await _fetch_advisories(db, start_bound, end_bound)
    headlines = _dedupe_headlines(headlines, advisories)

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
        market=market,
        headlines=headlines,
        advisories=advisories,
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
        "market": brief.market,
        "headlines": brief.headlines,
        "advisories": brief.advisories,
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
    fallback_start = window_end_utc - timedelta(hours=12)
    if not _env_flag_on("DAILY_BRIEF_EOD_ENABLED", "0"):
        return fallback_start, window_end_utc
    watermark = _parse_watermark_utc(
        await get_sync_state_value(db, _DAILY_BRIEF_WATERMARK_KEY)
    )
    if watermark is None:
        return fallback_start, window_end_utc
    window_start_utc = max(watermark, window_end_utc - timedelta(hours=24))
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
        channels = daily_brief_channel_payloads(brief)
        return channels["text"], brief
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
        channels = daily_brief_channel_payloads(brief)
        extra = {"brief": brief_to_payload(brief), "discord_embeds": channels["discord_embeds"]}
        local_date = brief.window_end_local[:10]
        result = await dispatch_event(
            EVENT_DAILY_BRIEF,
            channels["html"],
            dedupe_key=f"{slot}:{local_date}",
            payload_extra=extra,
            discord_embeds=channels["discord_embeds"],
            telegram_parse_mode="HTML",
            discord_fallback=channels["text"],
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
