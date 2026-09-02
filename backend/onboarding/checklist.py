"""First-hour operator onboarding checklist (Wave 4).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import os
import time
from typing import Any

from database import get_nvd_sync_watermark
from db.integrity import run_integrity_check
from matching.stack_assets import assets_to_terms
from preferences.repo import get_alert_stack_assets, get_effective_stack_terms
from resilient_client import get_feed_health
from settings import production_posture_warnings, settings

ONBOARDING_DISMISS_KEY = "onboarding.dismissed_at"


async def _backup_recent_enough() -> tuple[bool, str]:
    backup_enabled = os.environ.get("BACKUP_ENABLED", "1").strip() == "1"
    if not backup_enabled:
        return False, "BACKUP_ENABLED=0"

    backup_dir = os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups")
    if not backup_dir:
        return False, "BACKUP_DIR not set"

    try:
        from pathlib import Path

        bdir = Path(backup_dir)
        if not bdir.is_dir():
            return False, f"backup dir missing ({backup_dir})"
        archives = sorted(
            [
                f
                for f in bdir.iterdir()
                if f.name.endswith(".tar.gz") or f.name.endswith(".tar.gz.age")
            ],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not archives:
            return False, "no backup archives yet"
        age_hours = (time.time() - archives[0].stat().st_mtime) / 3600
        interval = int(os.environ.get("BACKUP_INTERVAL_HOURS", "6"))
        ok = age_hours <= max(interval * 2, 12)
        return ok, f"last backup {age_hours:.1f}h ago"
    except Exception as exc:
        return False, str(exc)[:120]


async def build_onboarding_checklist(db: Any) -> dict[str, Any]:
    """Return checklist items with live done/pending state."""
    cve_row = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM cves")
    cve_count = int(cve_row[0]["cnt"]) if cve_row else 0
    watermark = await get_nvd_sync_watermark(db)
    stack_effective = (await get_effective_stack_terms(db)).strip()
    stack_assets = await get_alert_stack_assets(db)
    stack_asset_terms = ",".join(assets_to_terms(stack_assets))
    stack_configured = bool(stack_effective or stack_assets)

    feed_health = get_feed_health()
    open_circuits = sum(1 for v in feed_health.values() if v.get("circuit_open"))
    result = await run_integrity_check(db)
    integrity_ok = result.ok

    backup_ok, backup_detail = await _backup_recent_enough()
    posture = production_posture_warnings()
    posture_ok = len(posture) == 0

    sigmahq_ok = False
    sigmahq_status: dict[str, Any] = {}
    try:
        from detection.sigmahq_index import get_sigmahq_index_status

        sigmahq_status = await get_sigmahq_index_status(db)
        sigmahq_ok = int(sigmahq_status.get("rules_active") or 0) > 0
    except Exception:
        sigmahq_ok = False

    ingest_ok = cve_count >= 10 or bool(watermark)
    feeds_ok = open_circuits == 0 or cve_count > 0

    items = [
        {
            "id": "cve_ingest",
            "title": "CVE data ingested",
            "detail": f"{cve_count} CVEs in database"
            + (f"; NVD watermark {watermark}" if watermark else ""),
            "done": ingest_ok,
            "hint": "Wait for bootstrap ingest or check Admin → Scheduler / Feed health.",
        },
        {
            "id": "stack_terms",
            "title": "Stack terms configured",
            "detail": stack_effective or stack_asset_terms or "No stack terms yet",
            "done": stack_configured,
            "hint": "Save My Stack from the header. Legacy BRIEFR_STACK_TERMS is copied once into empty admin My Stack, then ignored.",
        },
        {
            "id": "backup_ready",
            "title": "Backups enabled",
            "detail": backup_detail,
            "done": backup_ok,
            "hint": "Enable BACKUP_ENABLED and run a manual backup from Admin → Backups.",
        },
        {
            "id": "feeds_healthy",
            "title": "Feed sources healthy",
            "detail": f"{open_circuits} open circuit(s)" if open_circuits else "All sources OK",
            "done": feeds_ok and integrity_ok,
            "hint": "Review Admin → Feed health; reset circuits after upstream outages.",
        },
        {
            "id": "production_posture",
            "title": "Production posture clean",
            "detail": "No unsafe flags"
            if posture_ok
            else f"{len(posture)} warning(s): {posture[0]['flag']}",
            "done": posture_ok or settings.briefr_env != "production",
            "hint": "Resolve warnings in Admin → Security before exposing production.",
        },
        {
            "id": "sigmahq_index",
            "title": "SigmaHQ detection index synced",
            "detail": (
                f"{sigmahq_status.get('rules_active', 0)} active rules"
                if sigmahq_ok
                else "Index empty — run Admin → Scheduler → Sync SigmaHQ index"
            ),
            "done": sigmahq_ok,
            "hint": "Enable SIGMAHQ_INDEX_SYNC_ENABLED and run Sync SigmaHQ index (or Force re-sync on Feed health).",
        },
    ]

    done_count = sum(1 for item in items if item["done"])
    return {
        "items": items,
        "done_count": done_count,
        "total_count": len(items),
        "complete": done_count == len(items),
    }
