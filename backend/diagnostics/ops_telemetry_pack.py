"""Versioned ops telemetry pack — time-series RCA JSON (no secrets)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from database import get_db
from db.api_metering import window_api_call_digest
from db.config import is_postgres
from db.resource_metrics import (
    RESOURCE_METRICS_MAX_SERIES_POINTS,
    VALID_RESOURCE_WINDOWS,
    _SUMMARY_METRICS,
    _WINDOW_HOURS,
    _degraded_state,
    fetch_resource_metrics_rows,
    get_resource_metrics_retention_days,
    summarize_metric,
)
from efficiency_audit import build_efficiency_report
from scheduler_locks import locked_jobs

OPS_TELEMETRY_PACK_VERSION = 1
OPS_TELEMETRY_MAX_SAMPLES = 50_000
LIMITATIONS = (
    "resource_metrics rows have no scheduler job_id; a CPU peak cannot name the job.",
    "History starts when resource_metrics_sample first wrote rows; earlier load is not invented.",
    "Remote or container Postgres often nulls process CPU/RSS; SQL stats may still be present.",
    f"Admin Resources charts downsample to {RESOURCE_METRICS_MAX_SERIES_POINTS} points; this pack includes raw samples (capped at {OPS_TELEMETRY_MAX_SAMPLES}, newest kept).",
    "outbound_http.recent is the newest 200 events in the window; by_source/by_actor cover the full window (up to 720h).",
)


async def _scheduler_last_runs(db) -> list[dict[str, Any]]:
    rows = await db.execute_fetchall(
        "SELECT key, value FROM sync_state WHERE key LIKE 'scheduler.last_run.%'"
    )
    result = []
    for row in rows:
        job_id = str(row["key"]).replace("scheduler.last_run.", "")
        try:
            raw = json.loads(row["value"])
            if isinstance(raw, list):
                history = raw
            elif isinstance(raw, dict):
                history = [raw]
            else:
                history = []
        except Exception:
            history = []
        latest = history[0] if history else {}
        result.append({
            "job_id": job_id,
            "last_run_utc": latest.get("last_run_utc") or latest.get("started_at"),
            "duration_seconds": latest.get("duration_seconds"),
            "had_error": latest.get("had_error"),
            "error_message": latest.get("error_message", ""),
        })
    result.sort(key=lambda item: item.get("last_run_utc") or "", reverse=True)
    return result


async def build_ops_telemetry_pack(*, window: str = "1d") -> dict[str, Any]:
    if window not in VALID_RESOURCE_WINDOWS:
        raise ValueError(f"Invalid window {window!r}")
    now = datetime.now(timezone.utc)
    hours = _WINDOW_HOURS[window]
    db = await get_db()
    try:
        rows = await fetch_resource_metrics_rows(db, window)
        truncated = len(rows) > OPS_TELEMETRY_MAX_SAMPLES
        samples = rows[-OPS_TELEMETRY_MAX_SAMPLES:] if truncated else rows
        summary = {metric: summarize_metric(rows, metric) for metric in _SUMMARY_METRICS}
        degraded = _degraded_state(rows, postgres_backend=is_postgres())
        outbound = await window_api_call_digest(db, hours=hours, recent_limit=200)
        last_runs = await _scheduler_last_runs(db)
        try:
            efficiency = await build_efficiency_report(db, db_path="postgresql")
        except Exception:
            efficiency = {"error": "unavailable"}
    finally:
        await db.close()

    return {
        "ops_telemetry_pack_version": OPS_TELEMETRY_PACK_VERSION,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": window,
        "window_hours": hours,
        "retention_days": get_resource_metrics_retention_days(),
        "sample_interval_seconds": 60,
        "postgres_backend": is_postgres(),
        "limitations": list(LIMITATIONS),
        "degraded": degraded,
        "resource_metrics": {
            "sample_count": len(rows),
            "truncated": truncated,
            "summary": summary,
            "samples": samples,
        },
        "outbound_http": outbound,
        "scheduler": {
            "locked_jobs": locked_jobs(),
            "last_runs": last_runs,
        },
        "efficiency": efficiency,
    }
