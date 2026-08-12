#!/usr/bin/env python3
"""
Seed a local BRIEFR database with realistic CVE rows and warm incident feeds.

Used before README screenshot capture so tabs show live-shaped data instead of
empty placeholders. Safe to re-run: skips CVE seeding when 10+ rows exist.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from database import get_cve_count, get_db, init_db  # noqa: E402
from feeds.incident_news import (  # noqa: E402
    fetch_all_incident_news_parallel,
    rss_cache_key,
)
from database import set_feed_cache  # noqa: E402


def _days_ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _days_from_now(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _recent_timestamp(hours_ago: int = 6) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


CVE_ROWS = [
    {
        "cve_id": "CVE-2025-24813",
        "description": "Apache Tomcat path equivalence remote code execution via partial PUT.",
        "cvss_score": 9.8,
        "severity": "CRITICAL",
        "published": _days_ago(2),
        "affected_products": ["apache:tomcat"],
        "is_kev": 1,
        "epss_score": 0.72,
        "has_poc": 1,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2024-3400",
        "description": "Palo Alto PAN-OS command injection in GlobalProtect gateway.",
        "cvss_score": 10.0,
        "severity": "CRITICAL",
        "published": _days_ago(5),
        "affected_products": ["paloaltonetworks:pan-os"],
        "is_kev": 1,
        "epss_score": 0.91,
        "has_poc": 1,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2024-21762",
        "description": "Fortinet FortiOS out-of-bounds write in SSL VPN.",
        "cvss_score": 9.6,
        "severity": "CRITICAL",
        "published": _days_ago(8),
        "affected_products": ["fortinet:fortios"],
        "is_kev": 1,
        "epss_score": 0.88,
        "has_poc": 0,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2024-6387",
        "description": "OpenSSH regreSSHion signal handler race condition (glibc).",
        "cvss_score": 8.1,
        "severity": "HIGH",
        "published": _days_ago(12),
        "affected_products": ["openbsd:openssh"],
        "is_kev": 0,
        "epss_score": 0.34,
        "has_poc": 1,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2025-21333",
        "description": "Windows Hyper-V elevation of privilege used in targeted intrusions.",
        "cvss_score": 8.8,
        "severity": "HIGH",
        "published": _days_ago(15),
        "affected_products": ["microsoft:windows"],
        "is_kev": 1,
        "epss_score": 0.41,
        "has_poc": 0,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2024-38112",
        "description": "Microsoft Windows MSHTML spoofing vulnerability actively exploited.",
        "cvss_score": 7.5,
        "severity": "HIGH",
        "published": _days_ago(20),
        "affected_products": ["microsoft:windows"],
        "is_kev": 1,
        "epss_score": 0.29,
        "has_poc": 0,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2024-4577",
        "description": "PHP CGI argument injection on Windows enables remote code execution.",
        "cvss_score": 9.8,
        "severity": "CRITICAL",
        "published": _days_ago(25),
        "affected_products": ["php:php"],
        "is_kev": 1,
        "epss_score": 0.67,
        "has_poc": 1,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2025-22252",
        "description": "VMware vCenter Server heap overflow in DCERPC protocol implementation.",
        "cvss_score": 9.1,
        "severity": "CRITICAL",
        "published": _days_ago(30),
        "affected_products": ["vmware:vcenter_server"],
        "is_kev": 0,
        "epss_score": 0.18,
        "has_poc": 0,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2024-20353",
        "description": "Cisco ASA and FTD denial-of-service via crafted HTTP requests.",
        "cvss_score": 7.5,
        "severity": "HIGH",
        "published": _days_ago(35),
        "affected_products": ["cisco:adaptive_security_appliance"],
        "is_kev": 0,
        "epss_score": 0.12,
        "has_poc": 0,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2024-21413",
        "description": "Microsoft Outlook monikers remote code execution (NTLM leak chain).",
        "cvss_score": 9.8,
        "severity": "CRITICAL",
        "published": _days_ago(40),
        "affected_products": ["microsoft:office"],
        "is_kev": 1,
        "epss_score": 0.55,
        "has_poc": 1,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2024-1086",
        "description": "Linux kernel netfilter use-after-free in nf_tables.",
        "cvss_score": 7.8,
        "severity": "HIGH",
        "published": _days_ago(45),
        "affected_products": ["linux:linux_kernel"],
        "is_kev": 0,
        "epss_score": 0.22,
        "has_poc": 1,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2025-0282",
        "description": "Ivanti Connect Secure stack-based buffer overflow in IF-T protocol.",
        "cvss_score": 9.0,
        "severity": "CRITICAL",
        "published": _days_ago(50),
        "affected_products": ["ivanti:connect_secure"],
        "is_kev": 1,
        "epss_score": 0.76,
        "has_poc": 0,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2024-27198",
        "description": "JetBrains TeamCity authentication bypass leading to RCE chains.",
        "cvss_score": 9.8,
        "severity": "CRITICAL",
        "published": _days_ago(60),
        "affected_products": ["jetbrains:teamcity"],
        "is_kev": 1,
        "epss_score": 0.48,
        "has_poc": 1,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2024-21893",
        "description": "Ivanti Connect Secure server-side request forgery in SAML component.",
        "cvss_score": 8.2,
        "severity": "HIGH",
        "published": _days_ago(70),
        "affected_products": ["ivanti:connect_secure"],
        "is_kev": 1,
        "epss_score": 0.31,
        "has_poc": 0,
        "patch_available": 1,
    },
    {
        "cve_id": "CVE-2024-21410",
        "description": "Microsoft NTLM privilege escalation via NTLMv2 reflection.",
        "cvss_score": 6.5,
        "severity": "MEDIUM",
        "published": _days_ago(80),
        "affected_products": ["microsoft:windows"],
        "is_kev": 0,
        "epss_score": 0.08,
        "has_poc": 0,
        "patch_available": 1,
    },
]

# (cve_id, product, short_description, required_action, due_date, date_added)
KEV_ROWS = [
    (
        "CVE-2025-24813",
        "Apache Tomcat",
        "RCE in partial PUT handling",
        "Apply vendor patch",
        _days_from_now(5),
        date.today().isoformat(),
    ),
    (
        "CVE-2024-3400",
        "Palo Alto PAN-OS",
        "Command injection in GlobalProtect",
        "Apply vendor patch",
        _days_from_now(10),
        _days_ago(30),
    ),
    (
        "CVE-2024-21762",
        "Fortinet FortiOS",
        "Out-of-bounds write in SSL VPN",
        "Apply vendor patch",
        _days_ago(90),
        _days_ago(90),
    ),
    (
        "CVE-2025-21333",
        "Microsoft Windows",
        "Hyper-V EoP",
        "Apply vendor patch",
        _days_from_now(3),
        date.today().isoformat(),
    ),
]

# EPSS mover for morning-brief section (detected_at within default 24h window).
BRIEF_EPSS_CHANGES = [
    ("CVE-2024-6387", "0.20", "0.34", _recent_timestamp(6)),
]


async def _seed_cves(db) -> int:
    inserted = 0
    for row in CVE_ROWS:
        await db.execute(
            """
            INSERT INTO cves (
                cve_id, description, cvss_score, severity, published,
                affected_products, is_kev, epss_score, has_poc, patch_available
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cve_id) DO NOTHING
            """,
            (
                row["cve_id"],
                row["description"],
                row["cvss_score"],
                row["severity"],
                row["published"],
                json.dumps(row["affected_products"]),
                row["is_kev"],
                row["epss_score"],
                row["has_poc"],
                row["patch_available"],
            ),
        )
        inserted += 1

    for cve_id, product, desc, action, due, added in KEV_ROWS:
        await db.execute(
            """
            INSERT INTO kev_deadlines (
                cve_id, product, short_description, required_action, due_date, date_added
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(cve_id) DO NOTHING
            """,
            (cve_id, product, desc, action, due, added),
        )

    for cve_id, old_val, new_val, detected_at in BRIEF_EPSS_CHANGES:
        await db.execute(
            """
            INSERT INTO cve_change_history (
                cve_id, field_name, old_value, new_value, detected_at
            ) VALUES (?, 'epss_score', ?, ?, ?)
            """,
            (cve_id, old_val, new_val, detected_at),
        )
    return inserted


async def _warm_incident_feeds(db) -> tuple[int, list[dict]]:
    """Warm feeds without letting an unavailable RSS provider block smoke tests."""
    if os.environ.get("CI") == "true" or os.environ.get("PLAYWRIGHT_SMOKE") == "1":
        cards = []
        errors = [{"source": "RSS feeds", "message": "network warm-up skipped in CI"}]
    else:
        try:
            cards, errors = await asyncio.wait_for(
                fetch_all_incident_news_parallel(db), timeout=45
            )
        except asyncio.TimeoutError:
            cards = []
            errors = [{"source": "RSS feeds", "message": "warm-up timed out"}]

    if not cards:
        # The smoke test needs one deterministic card, even when CI has no
        # outbound RSS access. Keep it in the normal per-source cache shape.
        cards = [{
            "title": "BRIEFR smoke-test incident",
            "url": "https://github.com/Soldier0x0/briefr",
            "publishedAt": datetime.now(timezone.utc).isoformat(),
            "description": "Synthetic incident used for isolated UI smoke tests.",
            "source": "BRIEFR test fixture",
            "techniques": [],
            "tags": ["BRIEFR"],
            "cve_ids": [],
            "kind": "news",
        }]
        await set_feed_cache(db, rss_cache_key("hackernews"), {"items": cards})
    await db.commit()
    return len(cards), errors


async def main() -> None:
    await init_db()
    db = await get_db()
    try:
        count = await get_cve_count(db)
        if count < 10:
            seeded = await _seed_cves(db)
            await db.commit()
            print(f"Seeded {seeded} sample CVE rows (had {count}, now {await get_cve_count(db)})")
        else:
            print(f"CVE table already has {count} rows — skipping CVE seed")

        feed_count, feed_errors = await _warm_incident_feeds(db)
        locked = [e for e in feed_errors if "locked" in e.get("message", "").lower()]
        if locked:
            raise RuntimeError(f"Incident feed warm-up hit database lock: {locked}")
        if feed_errors:
            print(f"Incident feed warm-up: {feed_count} cards, {len(feed_errors)} source warnings")
            for err in feed_errors:
                print(f"  - {err['source']}: {err['message']}")
        else:
            print(f"Incident feed warm-up: {feed_count} cards, all sources OK")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
