import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from db.errors import DatabaseLockedError
from database import get_db
from source_rate_limits import get_openrouter_daily_limit, get_otx_hourly_limit

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
        "hourly_limit": 10000,
        "monthly_limit": None,
        "rate_limit": "10,000 req/hour (API key) · BRIEFR paces 2 req/sec",
        "notes": "Campaign correlation via community pulses. Hourly quota with API key. BRIEFR caches 6h per CVE/pulse/IOC.",
        "docs_url": "https://otx.alienvault.com/api",
        "cache_hours": 6,
    },
    "openrouter": {
        "name": "OpenRouter",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "20 RPM · 50 req/day free (no credits)",
        "notes": "LLM failover provider. Daily cap override via OPENROUTER_DAILY_LIMIT (default 50).",
        "docs_url": "https://openrouter.ai/docs/api-reference/limits",
    },
    "threatfox": {
        "name": "ThreatFox",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Fair use · Auth-Key required",
        "notes": "Scheduled IOC catalog sync (not IOC Lookup tab).",
        "docs_url": "https://threatfox.abuse.ch/api/",
    },
    "vulncheck": {
        "name": "VulnCheck",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "~1,000 req/min (community)",
        "notes": "KEV enrichment index sync when VULNCHECK_API_KEY is set.",
        "docs_url": "https://docs.vulncheck.com/",
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
        count = api_usage.count + excluded.count,
        month_utc = excluded.month_utc
"""


def _hourly_tracked_services() -> set[str]:
  return {
      service
      for service, limits in API_LIMITS.items()
      if limits.get("hourly_limit") is not None
  }


def _usage_bucket_key(service: str, now: datetime | None = None) -> str:
    """Date or hour bucket for api_usage.date_utc depending on service limits."""
    ts = now or datetime.now(timezone.utc)
    if service in _hourly_tracked_services():
        return ts.strftime("%Y-%m-%dT%H")
    return ts.strftime("%Y-%m-%d")


def _effective_hourly_limit(service: str) -> int | None:
    limits = API_LIMITS.get(service, {})
    hourly = limits.get("hourly_limit")
    if hourly is None:
        return None
    if service == "otx":
        return get_otx_hourly_limit()
    return int(hourly)


def _effective_daily_limit(service: str) -> int | None:
    if service == "openrouter":
        return get_openrouter_daily_limit()
    limits = API_LIMITS.get(service, {})
    daily = limits.get("daily_limit")
    return int(daily) if daily is not None else None


def _week_start_utc(now: datetime | None = None) -> str:
    ts = now or datetime.now(timezone.utc)
    return (ts - timedelta(days=ts.weekday())).strftime("%Y-%m-%d")


def _usage_bucket(used: int, limit: int | None, *, period: str = "daily") -> dict:
    remaining = (limit - used) if limit is not None else None
    pct = round(used / limit * 100, 1) if limit else None
    warning = None
    if limit is not None and remaining is not None:
        if remaining <= 0:
            warning = f"{period}_quota_exceeded"
        elif pct is not None and pct >= 80:
            warning = f"{period}_quota_near_limit"
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
    hour_map: dict[str, int] | None = None,
) -> dict:
    sources = source_services or [service]
    daily_used = sum(today_map.get(s, 0) for s in sources)
    monthly_used = sum(month_map.get(s, 0) for s in sources)
    weekly_used = sum((week_map or {}).get(s, 0) for s in sources)
    daily_limit = limits.get("daily_limit")
    weekly_limit = limits.get("weekly_limit")
    monthly_limit = limits.get("monthly_limit")
    hourly_limit = _effective_hourly_limit(service)

    daily_bucket = _usage_bucket(daily_used, daily_limit, period="daily")
    weekly_bucket = _usage_bucket(weekly_used, weekly_limit, period="weekly")
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
    if hourly_limit is not None:
        hour_used = sum((hour_map or {}).get(s, 0) for s in sources)
        hour_bucket = _usage_bucket(hour_used, hourly_limit, period="hourly")
        hour_warning = hour_bucket.pop("warning")
        if not warning and hour_warning:
            warning = hour_warning
        stat["this_hour"] = {
            "used": hour_bucket["used"],
            "limit": hour_bucket["limit"],
            "remaining": hour_bucket["remaining"],
            "percent_used": hour_bucket["percent_used"],
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
        except DatabaseLockedError as exc:
            logger.warning("API usage batch deferred (database is locked): %s", exc)
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
    week_start = _week_start_utc(now)

    today_map: dict[str, int] = {}
    month_map: dict[str, int] = {}
    week_map: dict[str, int] = {}
    hour_map: dict[str, int] = {}
    hour_bucket = _usage_bucket_key("otx")

    try:
        db = await get_db()
        try:
            today_rows = await db.execute_fetchall(
                """
                SELECT service, SUM(count) as total FROM api_usage
                WHERE date_utc = ? OR date_utc LIKE ?
                GROUP BY service
                """,
                (today, f"{today}%"),
            )
            today_map = {r["service"]: r["total"] for r in today_rows}
            hour_rows = await db.execute_fetchall(
                """
                SELECT service, SUM(count) as total FROM api_usage
                WHERE date_utc = ?
                GROUP BY service
                """,
                (hour_bucket,),
            )
            hour_map = {r["service"]: r["total"] for r in hour_rows}
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
                service, limits, today_map, month_map, week_map, aggregate, hour_map
            )
        )

    return results


async def record_api_call(service: str, count: int = 1) -> None:
    if count <= 0:
        return
    now = datetime.now(timezone.utc)
    bucket = _usage_bucket_key(service, now)
    month = now.strftime("%Y-%m")
    key = (service, bucket, month)

    global _api_usage_flush_task
    async with _API_USAGE_LOCK:
        _api_usage_pending[key] = _api_usage_pending.get(key, 0) + count
        pending_total = _api_usage_pending[key]
        if _api_usage_flush_task is None or _api_usage_flush_task.done():
            _api_usage_flush_task = asyncio.create_task(_schedule_api_usage_flush())

    hourly_limit = _effective_hourly_limit(service)
    if hourly_limit:
        committed = await _committed_usage_bucket(service, bucket)
        used = committed + pending_total
        if used >= hourly_limit:
            logger.warning(
                "%s hourly quota exhausted (%d/%d calls this hour)", service, used, hourly_limit
            )
        elif used >= hourly_limit * 0.8:
            logger.warning(
                "%s hourly quota near limit (%d/%d calls this hour)", service, used, hourly_limit
            )
        return

    limit = _effective_daily_limit(service)
    if limit:
        committed = await _committed_usage_bucket(service, bucket)
        used = committed + pending_total
        if used >= limit:
            logger.warning("%s daily quota exhausted (%d/%d calls today)", service, used, limit)
        elif used >= limit * 0.8:
            logger.warning("%s daily quota near limit (%d/%d calls today)", service, used, limit)

    weekly_limit = API_LIMITS.get(service, {}).get("weekly_limit")
    if weekly_limit:
        used = await get_week_usage(service)
        if used >= weekly_limit:
            logger.warning(
                "%s weekly quota exhausted (%d/%d calls this week)", service, used, weekly_limit
            )
        elif used >= weekly_limit * 0.8:
            logger.warning(
                "%s weekly quota near limit (%d/%d calls this week)", service, used, weekly_limit
            )

    monthly_limit = API_LIMITS.get(service, {}).get("monthly_limit")
    if monthly_limit:
        used = await get_month_usage(service)
        if used >= monthly_limit:
            logger.warning(
                "%s monthly quota exhausted (%d/%d calls this month)", service, used, monthly_limit
            )
        elif used >= monthly_limit * 0.8:
            logger.warning(
                "%s monthly quota near limit (%d/%d calls this month)", service, used, monthly_limit
            )


_COMMITTED_USAGE_CACHE_TTL_SECONDS = 2.0
_committed_usage_cache: dict[tuple[str, str], tuple[float, int]] = {}
_committed_week_usage_cache: dict[tuple[str, str], tuple[float, int]] = {}
_committed_month_usage_cache: dict[tuple[str, str], tuple[float, int]] = {}


async def _committed_usage_bucket(service: str, bucket: str) -> int:
    """Flushed count for service in the given date/hour bucket."""
    cache_key = (service, bucket)
    now = time.monotonic()
    cached = _committed_usage_cache.get(cache_key)
    if cached is not None and now - cached[0] < _COMMITTED_USAGE_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        db = await get_db()
        try:
            row = await db.execute_fetchall(
                "SELECT SUM(count) as total FROM api_usage WHERE service = ? AND date_utc = ?",
                (service, bucket),
            )
            value = row[0]["total"] if row and row[0]["total"] else 0
        finally:
            await db.close()
    except Exception as exc:
        logger.error("Failed to read committed usage for %s: %s", service, exc)
        return cached[1] if cached is not None else 0

    _committed_usage_cache[cache_key] = (now, value)
    return value


async def get_hour_usage(service: str) -> int:
    """Current UTC hour usage, including the unflushed buffer."""
    bucket = _usage_bucket_key(service)
    committed = await _committed_usage_bucket(service, bucket)
    async with _API_USAGE_LOCK:
        pending = sum(
            count for (svc, bkt, _month), count in _api_usage_pending.items()
            if svc == service and bkt == bucket
        )
    return committed + pending


async def get_today_usage(service: str) -> int:
    """Today's usage for service, combining committed rows and the unflushed buffer."""
    if service in _hourly_tracked_services():
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            db = await get_db()
            try:
                rows = await db.execute_fetchall(
                    """
                    SELECT SUM(count) as total FROM api_usage
                    WHERE service = ? AND date_utc LIKE ?
                    """,
                    (service, f"{today}%"),
                )
                committed = rows[0]["total"] if rows and rows[0]["total"] else 0
            finally:
                await db.close()
        except Exception:
            committed = 0
        async with _API_USAGE_LOCK:
            pending = sum(
                count for (svc, bkt, _month), count in _api_usage_pending.items()
                if svc == service and bkt.startswith(today)
            )
        return committed + pending

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    committed = await _committed_usage_bucket(service, today)
    async with _API_USAGE_LOCK:
        pending = sum(
            count for (svc, day, _month), count in _api_usage_pending.items()
            if svc == service and day == today
        )
    return committed + pending


async def _committed_week_usage(service: str) -> int:
    week_start = _week_start_utc()
    cache_key = (service, week_start)
    now = time.monotonic()
    cached = _committed_week_usage_cache.get(cache_key)
    if cached is not None and now - cached[0] < _COMMITTED_USAGE_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                """
                SELECT SUM(count) as total FROM api_usage
                WHERE service = ? AND date_utc >= ?
                """,
                (service, week_start),
            )
            value = rows[0]["total"] if rows and rows[0]["total"] else 0
        finally:
            await db.close()
    except Exception as exc:
        logger.error("Failed to read weekly usage for %s: %s", service, exc)
        return cached[1] if cached is not None else 0

    _committed_week_usage_cache[cache_key] = (now, value)
    return value


async def get_week_usage(service: str) -> int:
    """UTC week (Mon–Sun) usage, including the unflushed buffer."""
    week_start = _week_start_utc()
    committed = await _committed_week_usage(service)
    async with _API_USAGE_LOCK:
        pending = sum(
            count
            for (svc, day, _month), count in _api_usage_pending.items()
            if svc == service and day >= week_start
        )
    return committed + pending


async def _committed_month_usage(service: str) -> int:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    cache_key = (service, month)
    now = time.monotonic()
    cached = _committed_month_usage_cache.get(cache_key)
    if cached is not None and now - cached[0] < _COMMITTED_USAGE_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT SUM(count) as total FROM api_usage WHERE service = ? AND month_utc = ?",
                (service, month),
            )
            value = rows[0]["total"] if rows and rows[0]["total"] else 0
        finally:
            await db.close()
    except Exception as exc:
        logger.error("Failed to read monthly usage for %s: %s", service, exc)
        return cached[1] if cached is not None else 0

    _committed_month_usage_cache[cache_key] = (now, value)
    return value


async def get_month_usage(service: str) -> int:
    """Current UTC month usage, including the unflushed buffer."""
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    committed = await _committed_month_usage(service)
    async with _API_USAGE_LOCK:
        pending = sum(
            count
            for (svc, _day, pending_month), count in _api_usage_pending.items()
            if svc == service and pending_month == month
        )
    return committed + pending


async def has_quota(service: str) -> bool:
    """True if service has remaining quota across hourly/daily/weekly/monthly caps."""
    hourly_limit = _effective_hourly_limit(service)
    if hourly_limit is not None and await get_hour_usage(service) >= hourly_limit:
        return False

    daily_limit = _effective_daily_limit(service)
    if daily_limit is not None and await get_today_usage(service) >= daily_limit:
        return False

    weekly_limit = API_LIMITS.get(service, {}).get("weekly_limit")
    if weekly_limit is not None and await get_week_usage(service) >= weekly_limit:
        return False

    monthly_limit = API_LIMITS.get(service, {}).get("monthly_limit")
    if monthly_limit is not None and await get_month_usage(service) >= monthly_limit:
        return False

    return True


async def get_usage_stats() -> list[dict]:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    hour_bucket = _usage_bucket_key("otx", now)

    today_map: dict[str, int] = {}
    month_map: dict[str, int] = {}
    hour_map: dict[str, int] = {}

    try:
        db = await get_db()
        try:
            today_rows = await db.execute_fetchall(
                """
                SELECT service, SUM(count) as total FROM api_usage
                WHERE date_utc = ? OR date_utc LIKE ?
                GROUP BY service
                """,
                (today, f"{today}%"),
            )
            today_map = {r["service"]: r["total"] for r in today_rows}

            month_rows = await db.execute_fetchall(
                "SELECT service, SUM(count) as total FROM api_usage WHERE month_utc = ? GROUP BY service",
                (month,),
            )
            month_map = {r["service"]: r["total"] for r in month_rows}

            hour_rows = await db.execute_fetchall(
                """
                SELECT service, SUM(count) as total FROM api_usage
                WHERE date_utc = ?
                GROUP BY service
                """,
                (hour_bucket,),
            )
            hour_map = {r["service"]: r["total"] for r in hour_rows}
        finally:
            await db.close()
    except Exception as exc:
        logger.error("Failed to read API usage stats: %s", exc)

    results = []
    for service, limits in API_LIMITS.items():
        results.append(
            _build_service_stat(
                service, limits, today_map, month_map, hour_map=hour_map
            )
        )

    return results
