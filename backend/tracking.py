import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from database import get_db

logger = logging.getLogger(__name__)

API_LIMITS: dict[str, dict] = {
    "nvd": {
        "name": "NVD (NIST)",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "50 req/30s with key · 5 req/30s anonymous",
        "notes": "No daily/monthly quota. Rate window resets every 30 seconds.",
        "docs_url": "https://nvd.nist.gov/developers/vulnerabilities",
    },
    "kev": {
        "name": "CISA KEV",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Unrestricted",
        "notes": "Static JSON endpoint. No rate limit or quota.",
        "docs_url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
    },
    "epss": {
        "name": "FIRST EPSS",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Unrestricted",
        "notes": "No published quota or rate limit.",
        "docs_url": "https://www.first.org/epss/api",
    },
    "osv": {
        "name": "OSV.dev",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Unrestricted",
        "notes": "No published quota or rate limit.",
        "docs_url": "https://google.github.io/osv.dev/api/",
    },
    "virustotal": {
        "name": "VirusTotal",
        "daily_limit": 500,
        "monthly_limit": 15500,
        "rate_limit": "4 req/min (public API)",
        "notes": "Public API free tier. Daily/monthly quotas reset 00:00 UTC.",
        "docs_url": "https://docs.virustotal.com/reference/public-vs-premium-api",
        "cache_hours": 6,
    },
    "abuseipdb": {
        "name": "AbuseIPDB",
        "daily_limit": 1000,
        "monthly_limit": None,
        "rate_limit": "1,000 check/day (free)",
        "notes": "Webmaster-verified domains: 3,000 check/day. Resets midnight UTC.",
        "docs_url": "https://docs.abuseipdb.com/",
        "cache_hours": 6,
    },
    "greynoise": {
        "name": "GreyNoise Community",
        "daily_limit": None,
        "weekly_limit": 50,
        "monthly_limit": None,
        "rate_limit": "50 lookups / week (free key)",
        "notes": "Shared with GreyNoise Visualizer. BRIEFR caches IP lookups 1h.",
        "docs_url": "https://docs.greynoise.io/docs/using-the-greynoise-community-api",
        "cache_hours": 1,
    },
    "malwarebazaar": {
        "name": "MalwareBazaar",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Fair use · Auth-Key required",
        "notes": "One POST per hash lookup. Same ABUSECH_AUTH_KEY as URLhaus. IOC cache 6h.",
        "docs_url": "https://bazaar.abuse.ch/api/",
        "cache_hours": 6,
    },
    "urlhaus": {
        "name": "URLhaus",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Fair use · Auth-Key required",
        "notes": "One POST per domain/URL lookup. Same ABUSECH_AUTH_KEY as MalwareBazaar. IOC cache 6h.",
        "docs_url": "https://urlhaus.abuse.ch/api/",
        "cache_hours": 6,
    },
    "sploitus": {
        "name": "Sploitus",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Unpublished",
        "notes": "CVE exploit search (not IOC Lookup).",
        "docs_url": "https://sploitus.com/",
    },
    "circl": {
        "name": "CIRCL CVE-Search",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Unrestricted",
        "notes": "CVE enrichment (not IOC Lookup).",
        "docs_url": "https://cve.circl.lu/",
    },
    "otx": {
        "name": "AlienVault OTX",
        "daily_limit": None,
        "monthly_limit": 10000,
        "rate_limit": "10,000 req/month (free tier)",
        "notes": "Campaign correlation via community pulses. BRIEFR caches 6h per CVE/pulse/IOC.",
        "docs_url": "https://otx.alienvault.com/api",
        "cache_hours": 6,
    },
}

# IOC Lookup tab: display order and optional aggregate of usage counters
IOC_QUOTA_SERVICES: list[tuple[str, list[str] | None]] = [
    ("virustotal", None),
    ("abuseipdb", None),
    ("greynoise", None),
    ("otx", None),
    ("malwarebazaar", None),
    ("urlhaus", None),
]

_API_USAGE_FLUSH_DELAY_SECONDS = 0.5
_API_USAGE_LOCK = asyncio.Lock()
_API_USAGE_WRITE_LOCK = asyncio.Lock()
_api_usage_pending: dict[tuple[str, str, str], int] = {}
_api_usage_flush_task: asyncio.Task | None = None

_API_USAGE_UPSERT_SQL = """
    INSERT INTO api_usage (service, date_utc, month_utc, count)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(service, date_utc) DO UPDATE SET
        count = count + excluded.count,
        month_utc = excluded.month_utc
"""


def _usage_bucket(used: int, limit: int | None) -> dict:
    remaining = (limit - used) if limit is not None else None
    pct = round(used / limit * 100, 1) if limit else None
    warning = None
    if limit is not None and remaining is not None:
        if remaining <= 0:
            warning = "daily_quota_exceeded"
        elif pct is not None and pct >= 80:
            warning = "daily_quota_near_limit"
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "percent_used": pct,
        "warning": warning,
    }


def _build_service_stat(
    service: str,
    limits: dict,
    today_map: dict[str, int],
    month_map: dict[str, int],
    week_map: dict[str, int] | None = None,
    source_services: list[str] | None = None,
) -> dict:
    sources = source_services or [service]
    daily_used = sum(today_map.get(s, 0) for s in sources)
    monthly_used = sum(month_map.get(s, 0) for s in sources)
    weekly_used = sum((week_map or {}).get(s, 0) for s in sources)
    daily_limit = limits.get("daily_limit")
    weekly_limit = limits.get("weekly_limit")
    monthly_limit = limits.get("monthly_limit")

    daily_bucket = _usage_bucket(daily_used, daily_limit)
    weekly_bucket = _usage_bucket(weekly_used, weekly_limit)
    monthly_remaining = (monthly_limit - monthly_used) if monthly_limit is not None else None
    monthly_pct = round(monthly_used / monthly_limit * 100, 1) if monthly_limit else None

    warning = daily_bucket.pop("warning")
    if not warning and weekly_limit is not None:
        warning = weekly_bucket.get("warning")
    if not warning and monthly_limit and monthly_remaining is not None:
        if monthly_remaining <= 0:
            warning = "monthly_quota_exceeded"
        elif monthly_pct is not None and monthly_pct >= 80:
            warning = "monthly_quota_near_limit"

    stat = {
        "service": service,
        "name": limits["name"],
        "rate_limit": limits["rate_limit"],
        "notes": limits["notes"],
        "docs_url": limits["docs_url"],
        "cache_hours": limits.get("cache_hours"),
        "source_services": sources,
        "today": {
            "used": daily_bucket["used"],
            "limit": daily_bucket["limit"],
            "remaining": daily_bucket["remaining"],
            "percent_used": daily_bucket["percent_used"],
        },
        "this_month": {
            "used": monthly_used,
            "limit": monthly_limit,
            "remaining": monthly_remaining,
            "percent_used": monthly_pct,
        },
        "warning": warning,
    }
    if weekly_limit is not None:
        stat["this_week"] = {
            "used": weekly_bucket["used"],
            "limit": weekly_bucket["limit"],
            "remaining": weekly_bucket["remaining"],
            "percent_used": weekly_bucket["percent_used"],
        }
    return stat


async def _schedule_api_usage_flush() -> None:
    await asyncio.sleep(_API_USAGE_FLUSH_DELAY_SECONDS)
    await flush_api_usage_pending()


async def flush_api_usage_pending() -> None:
    """Persist buffered api_usage counters in one transaction (test hook).

    Any failure to write — locked DB or otherwise — requeues the batch rather
    than dropping it, since a silently undercounted total would let the
    pre-flight quota gate in enrichment/ioc.py keep calling past a provider's
    real daily limit.
    """
    global _api_usage_flush_task

    async with _API_USAGE_WRITE_LOCK:
        async with _API_USAGE_LOCK:
            batch = dict(_api_usage_pending)
            _api_usage_pending.clear()
            _api_usage_flush_task = None

        if not batch:
            return

        try:
            db = await get_db()
            try:
                for (service, today, month), count in batch.items():
                    await db.execute(
                        _API_USAGE_UPSERT_SQL,
                        (service, today, month, count),
                    )
                await db.commit()
            finally:
                await db.close()
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                logger.warning("API usage batch deferred (database is locked)")
            else:
                logger.error("API usage batch deferred (write error): %s", exc)
            async with _API_USAGE_LOCK:
                for key, count in batch.items():
                    _api_usage_pending[key] = _api_usage_pending.get(key, 0) + count
                if _api_usage_flush_task is None or _api_usage_flush_task.done():
                    _api_usage_flush_task = asyncio.create_task(
                        _schedule_api_usage_flush()
                    )
        except Exception as exc:
            logger.error("API usage batch deferred (unexpected error): %s", exc)
            async with _API_USAGE_LOCK:
                for key, count in batch.items():
                    _api_usage_pending[key] = _api_usage_pending.get(key, 0) + count
                if _api_usage_flush_task is None or _api_usage_flush_task.done():
                    _api_usage_flush_task = asyncio.create_task(
                        _schedule_api_usage_flush()
                    )


async def get_ioc_usage_stats() -> list[dict]:
    """Usage stats for APIs used by IOC Lookup (counts BRIEFR outbound calls on this server)."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

    today_map: dict[str, int] = {}
    month_map: dict[str, int] = {}
    week_map: dict[str, int] = {}

    try:
        db = await get_db()
        try:
            today_rows = await db.execute_fetchall(
                "SELECT service, SUM(count) as total FROM api_usage WHERE date_utc = ? GROUP BY service",
                (today,),
            )
            today_map = {r["service"]: r["total"] for r in today_rows}
            month_rows = await db.execute_fetchall(
                "SELECT service, SUM(count) as total FROM api_usage WHERE month_utc = ? GROUP BY service",
                (month,),
            )
            month_map = {r["service"]: r["total"] for r in month_rows}
            week_rows = await db.execute_fetchall(
                """
                SELECT service, SUM(count) as total FROM api_usage
                WHERE date_utc >= ?
                GROUP BY service
                """,
                (week_start,),
            )
            week_map = {r["service"]: r["total"] for r in week_rows}
        finally:
            await db.close()
    except Exception as exc:
        logger.error("Failed to read IOC API usage: %s", exc)

    results: list[dict] = []
    for service, aggregate in IOC_QUOTA_SERVICES:
        limits = API_LIMITS.get(service)
        if not limits:
            continue
        results.append(
            _build_service_stat(
                service, limits, today_map, month_map, week_map, aggregate
            )
        )

    return results


async def record_api_call(service: str, count: int = 1) -> None:
    if count <= 0:
        return
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    key = (service, today, month)

    global _api_usage_flush_task
    async with _API_USAGE_LOCK:
        _api_usage_pending[key] = _api_usage_pending.get(key, 0) + count
        pending_total = _api_usage_pending[key]
        if _api_usage_flush_task is None or _api_usage_flush_task.done():
            _api_usage_flush_task = asyncio.create_task(_schedule_api_usage_flush())

    limit = API_LIMITS.get(service, {}).get("daily_limit")
    if limit:
        committed = await _committed_usage(service, today)
        used = committed + pending_total
        if used >= limit:
            logger.warning("%s daily quota exhausted (%d/%d calls today)", service, used, limit)
        elif used >= limit * 0.8:
            logger.warning("%s daily quota near limit (%d/%d calls today)", service, used, limit)


_COMMITTED_USAGE_CACHE_TTL_SECONDS = 2.0
_committed_usage_cache: dict[tuple[str, str], tuple[float, int]] = {}


async def _committed_usage(service: str, today: str) -> int:
    """Today's already-flushed count for service, excluding the in-memory buffer.

    Cached for a couple seconds — bulk IOC lookups call has_quota/record_api_call
    once per item, and without this a 100-item lookup means 100+ DB round-trips
    on a server that already sees SQLite lock contention.
    """
    cache_key = (service, today)
    now = time.monotonic()
    cached = _committed_usage_cache.get(cache_key)
    if cached is not None and now - cached[0] < _COMMITTED_USAGE_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        db = await get_db()
        try:
            row = await db.execute_fetchall(
                "SELECT SUM(count) as total FROM api_usage WHERE service = ? AND date_utc = ?",
                (service, today),
            )
            value = row[0]["total"] if row and row[0]["total"] else 0
        finally:
            await db.close()
    except Exception as exc:
        logger.error("Failed to read committed usage for %s: %s", service, exc)
        return cached[1] if cached is not None else 0

    _committed_usage_cache[cache_key] = (now, value)
    return value


async def get_today_usage(service: str) -> int:
    """Today's usage for service, combining committed rows and the unflushed buffer."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    committed = await _committed_usage(service, today)
    async with _API_USAGE_LOCK:
        pending = sum(
            count for (svc, day, _month), count in _api_usage_pending.items()
            if svc == service and day == today
        )
    return committed + pending


async def has_quota(service: str) -> bool:
    """True if service has remaining daily quota (no limit == unrestricted)."""
    limit = API_LIMITS.get(service, {}).get("daily_limit")
    if not limit:
        return True
    used = await get_today_usage(service)
    return used < limit


async def get_usage_stats() -> list[dict]:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    today_map: dict[str, int] = {}
    month_map: dict[str, int] = {}

    try:
        db = await get_db()
        try:
            today_rows = await db.execute_fetchall(
                "SELECT service, SUM(count) as total FROM api_usage WHERE date_utc = ? GROUP BY service",
                (today,),
            )
            today_map = {r["service"]: r["total"] for r in today_rows}

            month_rows = await db.execute_fetchall(
                "SELECT service, SUM(count) as total FROM api_usage WHERE month_utc = ? GROUP BY service",
                (month,),
            )
            month_map = {r["service"]: r["total"] for r in month_rows}
        finally:
            await db.close()
    except Exception as exc:
        logger.error("Failed to read API usage stats: %s", exc)

    results = []
    for service, limits in API_LIMITS.items():
        daily_used = today_map.get(service, 0)
        monthly_used = month_map.get(service, 0)
        daily_limit = limits["daily_limit"]
        monthly_limit = limits["monthly_limit"]

        daily_remaining = (daily_limit - daily_used) if daily_limit is not None else None
        monthly_remaining = (monthly_limit - monthly_used) if monthly_limit is not None else None

        daily_pct = round(daily_used / daily_limit * 100, 1) if daily_limit else None
        monthly_pct = round(monthly_used / monthly_limit * 100, 1) if monthly_limit else None

        warning = None
        if daily_limit and daily_remaining is not None:
            if daily_remaining <= 0:
                warning = "daily_quota_exceeded"
            elif daily_pct and daily_pct >= 80:
                warning = "daily_quota_near_limit"
        if not warning and monthly_limit and monthly_remaining is not None:
            if monthly_remaining <= 0:
                warning = "monthly_quota_exceeded"
            elif monthly_pct and monthly_pct >= 80:
                warning = "monthly_quota_near_limit"

        results.append(
            {
                "service": service,
                "name": limits["name"],
                "rate_limit": limits["rate_limit"],
                "notes": limits["notes"],
                "docs_url": limits["docs_url"],
                "today": {
                    "used": daily_used,
                    "limit": daily_limit,
                    "remaining": daily_remaining,
                    "percent_used": daily_pct,
                },
                "this_month": {
                    "used": monthly_used,
                    "limit": monthly_limit,
                    "remaining": monthly_remaining,
                    "percent_used": monthly_pct,
                },
                "warning": warning,
            }
        )

    return results
