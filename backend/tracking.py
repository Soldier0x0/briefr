import logging
from datetime import datetime, timezone

import aiosqlite

from database import DB_PATH

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
        "rate_limit": "4 req/min",
        "notes": "Free public API tier. Quota resets at midnight UTC daily.",
        "docs_url": "https://developers.virustotal.com/reference/overview",
    },
    "abuseipdb": {
        "name": "AbuseIPDB",
        "daily_limit": 1000,
        "monthly_limit": 30000,
        "rate_limit": "Within daily quota",
        "notes": "Free tier. Daily quota resets at midnight UTC.",
        "docs_url": "https://www.abuseipdb.com/account/plans",
    },
    "greynoise": {
        "name": "GreyNoise Community",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Fair use with API key",
        "notes": "No published daily cap; avoid burst traffic.",
        "docs_url": "https://docs.greynoise.io/docs/community-api",
    },
    "malwarebazaar": {
        "name": "MalwareBazaar",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Fair use (abuse.ch Auth-Key)",
        "notes": "Shares ABUSECH_AUTH_KEY with URLhaus.",
        "docs_url": "https://bazaar.abuse.ch/api/",
    },
    "urlhaus": {
        "name": "URLhaus",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Fair use (abuse.ch Auth-Key)",
        "notes": "Shares ABUSECH_AUTH_KEY with MalwareBazaar.",
        "docs_url": "https://urlhaus.abuse.ch/api/",
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
}

# IOC Lookup tab: display order and optional aggregate of usage counters
IOC_QUOTA_SERVICES: list[tuple[str, list[str] | None]] = [
    ("virustotal", None),
    ("abuseipdb", None),
    ("greynoise", None),
    ("abusech", ["malwarebazaar", "urlhaus"]),
]


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
    source_services: list[str] | None = None,
) -> dict:
    sources = source_services or [service]
    daily_used = sum(today_map.get(s, 0) for s in sources)
    monthly_used = sum(month_map.get(s, 0) for s in sources)
    daily_limit = limits["daily_limit"]
    monthly_limit = limits["monthly_limit"]

    daily_bucket = _usage_bucket(daily_used, daily_limit)
    monthly_remaining = (monthly_limit - monthly_used) if monthly_limit is not None else None
    monthly_pct = round(monthly_used / monthly_limit * 100, 1) if monthly_limit else None

    warning = daily_bucket.pop("warning")
    if not warning and monthly_limit and monthly_remaining is not None:
        if monthly_remaining <= 0:
            warning = "monthly_quota_exceeded"
        elif monthly_pct is not None and monthly_pct >= 80:
            warning = "monthly_quota_near_limit"

    return {
        "service": service,
        "name": limits["name"],
        "rate_limit": limits["rate_limit"],
        "notes": limits["notes"],
        "docs_url": limits["docs_url"],
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


async def get_ioc_usage_stats() -> list[dict]:
    """Usage stats for APIs used by IOC Lookup (abuse.ch combined)."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    today_map: dict[str, int] = {}
    month_map: dict[str, int] = {}

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
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
    except Exception as exc:
        logger.error("Failed to read IOC API usage: %s", exc)

    abusech_limits = {
        "name": "abuse.ch (MalwareBazaar + URLhaus)",
        "daily_limit": None,
        "monthly_limit": None,
        "rate_limit": "Fair use · one Auth-Key",
        "notes": "Same ABUSECH_AUTH_KEY for MalwareBazaar and URLhaus (auth.abuse.ch).",
        "docs_url": "https://auth.abuse.ch/",
    }

    results: list[dict] = []
    for service, aggregate in IOC_QUOTA_SERVICES:
        if service == "abusech":
            results.append(
                _build_service_stat(
                    "abusech",
                    abusech_limits,
                    today_map,
                    month_map,
                    source_services=["malwarebazaar", "urlhaus"],
                )
            )
            continue
        limits = API_LIMITS.get(service)
        if not limits:
            continue
        results.append(_build_service_stat(service, limits, today_map, month_map, aggregate))

    return results


async def record_api_call(service: str, count: int = 1) -> None:
    if count <= 0:
        return
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO api_usage (service, date_utc, month_utc, count)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(service, date_utc) DO UPDATE SET
                    count = count + excluded.count,
                    month_utc = excluded.month_utc
                """,
                (service, today, month, count),
            )
            await db.commit()
    except Exception as exc:
        logger.error("Failed to record API usage for %s: %s", service, exc)


async def get_usage_stats() -> list[dict]:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    today_map: dict[str, int] = {}
    month_map: dict[str, int] = {}

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

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
