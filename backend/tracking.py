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
}


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
