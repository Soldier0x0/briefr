# Ops telemetry pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an admin-gated **Ops telemetry pack** JSON download (raw host/DB samples + outbound HTTP digest + job last-runs) named as a sibling of the support pack — never “resource utilization export”.

**Architecture:** New builder `diagnostics/ops_telemetry_pack.py` assembled like `support_pack.py`. Reuse `resource_metrics` raw rows (no 500-point downsample), a 720h-capable API digest, existing scheduler last-run `sync_state`, and `build_efficiency_report`. One GET next to support-pack.

**Tech Stack:** FastAPI, existing `db/resource_metrics.py` / `db/api_metering.py`, React Admin Overview + Resources, pytest + `test_router_split.py`.

**Spec:** `docs/superpowers/specs/2026-08-25-ops-telemetry-pack-design.md`

## Global Constraints

- Product name in UI, filename, audit action, and docs: **ops telemetry pack**. Forbidden: “resource utilization export”.
- Samples stay secret-free (`_RESOURCE_METRICS_COLUMNS` only). Outbound rows use the same public fields as the metering list API.
- Do not add `job_id` to `resource_metrics`. Do not fold this into the support pack. Do not change retention defaults.
- `limitations` must be present and honest (no job attribution; no invented pre-collector history; charts downsample, this pack does not).
- Merge gate: `./scripts/verify-local.sh`. Docs in the same PR: `PRODUCT_STATUS.md`, `API_REFERENCE.md`.

## File map

| File | Responsibility |
|------|----------------|
| Modify: `backend/db/resource_metrics.py` | `fetch_resource_metrics_rows(db, window)` used by chart + pack |
| Modify: `backend/db/api_metering.py` | `window_api_call_digest(db, *, hours, recent_limit=200)` max 720h |
| Create: `backend/diagnostics/ops_telemetry_pack.py` | `OPS_TELEMETRY_PACK_VERSION`, `build_ops_telemetry_pack` |
| Modify: `backend/routers/admin/diagnostics.py` | GET `/diagnostics/ops-telemetry-pack` |
| Modify: `backend/tests/test_router_split.py` | Insert route after support-pack |
| Create: `backend/tests/test_ops_telemetry_pack.py` | Auth, window, schema, filename |
| Modify: `frontend/src/pages/admin/OverviewPage.jsx` | Export button (window `1d`) |
| Modify: `frontend/src/pages/admin/ResourcesPage.jsx` | Export button (selected window) |
| Modify: `docs/API_REFERENCE.md`, `docs/PRODUCT_STATUS.md` | Shipped truth |

---

### Task 1: Raw `resource_metrics` window fetch

**Files:**
- Modify: `backend/db/resource_metrics.py`
- Modify: `backend/tests/test_resource_metrics.py`

**Interfaces:**
- Consumes: existing `_FETCH_WINDOW_*`, `_row_to_dict`, `VALID_RESOURCE_WINDOWS`
- Produces: `async def fetch_resource_metrics_rows(db: DbConnection, window: str) -> list[dict[str, Any]]`; `fetch_resources_response` must call it then downsample

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_resource_metrics.py`:

```python
def test_fetch_resource_metrics_rows_is_not_downsampled(tmp_path, monkeypatch):
    from db.config import is_postgres
    from db.resource_metrics import fetch_resource_metrics_rows

    if is_postgres():
        return
    db_path = tmp_path / "resource_raw.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO resource_metrics (ts, briefr_rss_bytes, req_count) VALUES (?, ?, ?)",
                (now, 111, 2),
            )
            await db.commit()
            rows = await fetch_resource_metrics_rows(db, "1d")
            assert len(rows) == 1
            assert rows[0]["briefr_rss_bytes"] == 111
            assert rows[0]["req_count"] == 2
        finally:
            await db.close()

    run_db_test(_run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_resource_metrics.py::test_fetch_resource_metrics_rows_is_not_downsampled -q`

Expected: FAIL (`fetch_resource_metrics_rows` not defined).

- [ ] **Step 3: Implement**

In `backend/db/resource_metrics.py`, extract the window query from `fetch_resources_response`:

```python
async def fetch_resource_metrics_rows(db: DbConnection, window: str) -> list[dict[str, Any]]:
    if window not in VALID_RESOURCE_WINDOWS:
        raise ValueError(f"Invalid window {window!r}")
    hours = _WINDOW_HOURS[window]
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    sql = _FETCH_WINDOW_PG if _is_postgres_connection(db) else _FETCH_WINDOW_SQLITE
    raw_rows = await db.execute_fetchall(sql, (cutoff,))
    return [_row_to_dict(r) for r in raw_rows]
```

Change `fetch_resources_response` to:

```python
    rows = await fetch_resource_metrics_rows(db, window)
    series = downsample_series(rows)
```

(remove the duplicated cutoff/sql/fetch).

- [ ] **Step 4: Re-run tests**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_resource_metrics.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/db/resource_metrics.py backend/tests/test_resource_metrics.py
git commit -m "refactor(resources): expose raw resource_metrics window rows"
```

---

### Task 2: 720h outbound HTTP digest

**Files:**
- Modify: `backend/db/api_metering.py`
- Create or modify: `backend/tests/test_api_metering.py` (use existing file if present)

**Interfaces:**
- Consumes: `_EVENT_SELECT_COLUMNS`, `_row_to_event_dict`, `_build_events_filters`
- Produces: `OPS_TELEMETRY_MAX_HTTP_HOURS = 720`; `async def window_api_call_digest(db, *, hours: int, recent_limit: int = 200) -> dict` with keys `hours`, `total`, `by_source`, `by_actor`, `recent_limit`, `recent`

- [ ] **Step 1: Write the failing test**

If `backend/tests/test_api_metering.py` exists, add; otherwise create a focused test in `backend/tests/test_ops_telemetry_pack.py` later — prefer adding now in `tests/test_efficiency_optimizations.py` only if metering tests live there. Preferred: `backend/tests/test_api_metering.py` (create if missing):

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db, init_db
from db.api_metering import window_api_call_digest
from tests.conftest import run_db_test


def test_window_api_call_digest_allows_720_hours(tmp_path, monkeypatch):
    from db.config import is_postgres

    if is_postgres():
        return
    db_path = tmp_path / "metering_digest.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            digest = await window_api_call_digest(db, hours=720, recent_limit=10)
            assert digest["hours"] == 720
            assert digest["total"] == 0
            assert digest["recent"] == []
            assert digest["by_source"] == []
        finally:
            await db.close()

    run_db_test(_run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_api_metering.py::test_window_api_call_digest_allows_720_hours -q`

Expected: FAIL (import error).

- [ ] **Step 3: Implement**

`metering_summary` and `query_api_call_events` must keep clamping to 168h. Only the new digest may request 720h.

In `backend/db/api_metering.py` change `_clamp_hours` and `_build_events_filters`:

```python
def _clamp_hours(hours: int, *, max_hours: int = 168) -> int:
    return max(1, min(int(hours), int(max_hours)))


def _build_events_filters(
    *,
    hours: int,
    source: str | None,
    actor_type: str | None,
    max_hours: int = 168,
) -> tuple[str, list[Any]]:
    """Return WHERE clause (without leading WHERE) and bind params."""
    hours = _clamp_hours(hours, max_hours=max_hours)
```

(leave the rest of `_build_events_filters` unchanged.)

Add:

```python
OPS_TELEMETRY_MAX_HTTP_HOURS = 720
OPS_TELEMETRY_RECENT_EVENTS = 200


async def window_api_call_digest(
    db: DbConnection,
    *,
    hours: int,
    recent_limit: int = OPS_TELEMETRY_RECENT_EVENTS,
) -> dict[str, Any]:
    hours = _clamp_hours(hours, max_hours=OPS_TELEMETRY_MAX_HTTP_HOURS)
    recent_limit = max(1, min(int(recent_limit), 500))
    where_sql, params = _build_events_filters(
        hours=hours,
        source=None,
        actor_type=None,
        max_hours=OPS_TELEMETRY_MAX_HTTP_HOURS,
    )
    if is_postgres():
        count_sql = f"SELECT COUNT(*)::int AS total FROM api_call_events WHERE {where_sql}"
        source_sql = (
            "SELECT source, COUNT(*)::int AS calls, "
            "COUNT(*) FILTER (WHERE ok)::int AS ok_calls, MAX(ts) AS last_called_at "
            f"FROM api_call_events WHERE {where_sql} GROUP BY source ORDER BY calls DESC LIMIT 50"
        )
        actor_sql = (
            "SELECT COALESCE(actor_type, 'unknown') AS actor_type, COUNT(*)::int AS calls "
            f"FROM api_call_events WHERE {where_sql} GROUP BY 1 ORDER BY calls DESC"
        )
        list_sql = (
            f"SELECT {_EVENT_SELECT_COLUMNS} FROM api_call_events "
            f"WHERE {where_sql} ORDER BY ts DESC LIMIT ${len(params) + 1}"
        )
        list_params = [*params, recent_limit]
    else:
        count_sql = f"SELECT COUNT(*) AS total FROM api_call_events WHERE {where_sql}"
        source_sql = (
            "SELECT source, COUNT(*) AS calls, "
            "SUM(CASE WHEN ok THEN 1 ELSE 0 END) AS ok_calls, MAX(ts) AS last_called_at "
            f"FROM api_call_events WHERE {where_sql} GROUP BY source ORDER BY calls DESC LIMIT 50"
        )
        actor_sql = (
            "SELECT COALESCE(actor_type, 'unknown') AS actor_type, COUNT(*) AS calls "
            f"FROM api_call_events WHERE {where_sql} GROUP BY 1 ORDER BY calls DESC"
        )
        list_sql = (
            f"SELECT {_EVENT_SELECT_COLUMNS} FROM api_call_events "
            f"WHERE {where_sql} ORDER BY ts DESC LIMIT ?"
        )
        list_params = [*params, recent_limit]

    count_rows = await db.execute_fetchall(count_sql, tuple(params))
    total = int((count_rows[0]["total"] if count_rows else 0) or 0)
    source_rows = await db.execute_fetchall(source_sql, tuple(params))
    actor_rows = await db.execute_fetchall(actor_sql, tuple(params))
    recent_rows = await db.execute_fetchall(list_sql, tuple(list_params))
    by_source = []
    for row in source_rows or []:
        item = dict(row)
        by_source.append({
            "source": item.get("source"),
            "calls": int(item.get("calls") or 0),
            "ok_calls": int(item.get("ok_calls") or 0),
            "last_called_at": item.get("last_called_at"),
        })
    by_actor = []
    for row in actor_rows or []:
        item = dict(row)
        by_actor.append({
            "actor_type": item.get("actor_type"),
            "calls": int(item.get("calls") or 0),
        })
    return {
        "hours": hours,
        "total": total,
        "by_source": by_source,
        "by_actor": by_actor,
        "recent_limit": recent_limit,
        "recent": [_row_to_event_dict(row) for row in (recent_rows or [])],
    }
```

Place `window_api_call_digest` **after** `_EVENT_SELECT_COLUMNS` and `_row_to_event_dict` are defined (bottom of the file is safest).

- [ ] **Step 4: Re-run test**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_api_metering.py tests/test_efficiency_optimizations.py -q`

Expected: PASS; existing metering list API still clamps to 168h.

- [ ] **Step 5: Commit**

```bash
git add backend/db/api_metering.py backend/tests/test_api_metering.py
git commit -m "feat(metering): window digest up to 720h for ops telemetry"
```

---

### Task 3: Pack builder + HTTP endpoint

**Files:**
- Create: `backend/diagnostics/ops_telemetry_pack.py`
- Modify: `backend/routers/admin/diagnostics.py`
- Modify: `backend/tests/test_router_split.py`
- Create: `backend/tests/test_ops_telemetry_pack.py`

**Interfaces:**
- Consumes: `fetch_resource_metrics_rows`, `summarize_metric`, `_SUMMARY_METRICS`, `_degraded_state`, `window_api_call_digest`, `build_efficiency_report`, `locked_jobs`, `get_resource_metrics_retention_days`, `VALID_RESOURCE_WINDOWS`, `_WINDOW_HOURS`
- Produces: `OPS_TELEMETRY_PACK_VERSION = 1`; `OPS_TELEMETRY_MAX_SAMPLES = 50000`; `LIMITATIONS: tuple[str, ...]`; `async def build_ops_telemetry_pack(*, window: str = "1d") -> dict[str, Any]`; GET `/api/admin/diagnostics/ops-telemetry-pack`

- [ ] **Step 1: Write failing HTTP tests**

Create `backend/tests/test_ops_telemetry_pack.py` using the same `admin_client` fixture pattern as `backend/tests/test_support_pack.py` (copy the fixture; do not import it if it is not shared):

```python
"""Tests for GET /api/admin/diagnostics/ops-telemetry-pack."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "ops_telemetry.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


def test_ops_telemetry_pack_requires_admin(tmp_path, monkeypatch):
    db_path = tmp_path / "ops_telemetry_auth.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/admin/diagnostics/ops-telemetry-pack")
    assert resp.status_code == 401


def test_ops_telemetry_pack_rejects_bad_window(admin_client):
    resp = admin_client.get("/api/admin/diagnostics/ops-telemetry-pack?window=2d")
    assert resp.status_code == 422


def test_ops_telemetry_pack_schema_and_filename(admin_client):
    resp = admin_client.get("/api/admin/diagnostics/ops-telemetry-pack?window=1d")
    assert resp.status_code == 200
    disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert "briefr-ops-telemetry-1d-" in disposition
    assert disposition.endswith('.json"') or ".json" in disposition
    data = json.loads(resp.text)
    assert data["ops_telemetry_pack_version"] == 1
    assert data["window"] == "1d"
    assert data["window_hours"] == 24
    assert isinstance(data["limitations"], list) and len(data["limitations"]) >= 4
    assert "resource_metrics" in data
    assert "samples" in data["resource_metrics"]
    assert "outbound_http" in data
    assert "scheduler" in data
    assert "efficiency" in data
    joined = " ".join(data["limitations"]).lower()
    assert "job" in joined
    assert "downsample" in joined or "500" in joined
```

In `backend/tests/test_router_split.py`, insert immediately after `("GET", "/api/admin/diagnostics/support-pack")`:

```python
    ("GET", "/api/admin/diagnostics/ops-telemetry-pack"),
```

(Keep list order identical to FastAPI registration order.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_ops_telemetry_pack.py tests/test_router_split.py -q`

Expected: FAIL (404 / route snapshot mismatch).

- [ ] **Step 3: Implement builder**

Create `backend/diagnostics/ops_telemetry_pack.py`:

```python
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
```

If `_SUMMARY_METRICS` / `_degraded_state` / `_WINDOW_HOURS` are private, either export them (no leading underscore) or keep importing with the existing names — this file already uses them from `resource_metrics.py`. Prefer not renaming unless a lint forbids importing `_` names; if so, add public aliases `SUMMARY_METRICS = _SUMMARY_METRICS` in `resource_metrics.py`.

Add route in `backend/routers/admin/diagnostics.py` immediately after `export_support_pack`:

```python
@router.get("/diagnostics/ops-telemetry-pack")
async def export_ops_telemetry_pack(
    request: Request,
    window: str = Query("1d"),
):
    from db.resource_metrics import VALID_RESOURCE_WINDOWS
    from diagnostics.ops_telemetry_pack import build_ops_telemetry_pack

    if window not in VALID_RESOURCE_WINDOWS:
        raise HTTPException(status_code=422, detail="window must be 1d, 3d, 7d, or 30d")
    payload = await build_ops_telemetry_pack(window=window)
    await audit(request, "diagnostics.ops_telemetry_pack", window)
    stamp = payload.get("generated_at", "unknown").replace(":", "").replace("-", "")
    filename = f"briefr-ops-telemetry-{window}-{stamp}.json"
    body = json.dumps(payload, indent=2, default=str, ensure_ascii=False)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

Ensure `HTTPException`, `Query`, `Response`, `json`, `audit` are already imported in that module (they are, for support-pack).

- [ ] **Step 4: Re-run tests**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_ops_telemetry_pack.py tests/test_support_pack.py tests/test_router_split.py tests/test_resource_metrics.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/diagnostics/ops_telemetry_pack.py backend/routers/admin/diagnostics.py backend/tests/test_ops_telemetry_pack.py backend/tests/test_router_split.py backend/db/resource_metrics.py
git commit -m "feat(admin): export ops telemetry pack JSON"
```

---

### Task 4: Admin UI buttons

**Files:**
- Modify: `frontend/src/pages/admin/OverviewPage.jsx`
- Modify: `frontend/src/pages/admin/ResourcesPage.jsx`

**Interfaces:**
- Consumes: `GET /api/admin/diagnostics/ops-telemetry-pack?window=`
- Produces: buttons labeled **Export ops telemetry pack**; filenames `briefr-ops-telemetry-...json`; toasts `Ops telemetry pack downloaded`

- [ ] **Step 1: Add Overview download (mirror support pack)**

In `OverviewPage.jsx` next to `exportSupportPack`:

```javascript
  async function exportOpsTelemetryPack() {
    setRunning(r => ({ ...r, opsTelemetry: true }))
    try {
      const res = await adminApi.get('/diagnostics/ops-telemetry-pack?window=1d')
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        toast(data.detail || `Export failed (${res.status})`, false)
        return
      }
      const blob = await res.blob()
      const stamp = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15)
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `briefr-ops-telemetry-1d-${stamp}.json`
      a.click()
      URL.revokeObjectURL(a.href)
      toast('Ops telemetry pack downloaded', true)
    } catch (e) { toast(String(e.message), false) }
    setRunning(r => ({ ...r, opsTelemetry: false }))
  }
```

Button after Export support pack:

```jsx
          <button
            className="admin-btn admin-btn-ghost"
            style={{ fontSize: '0.75rem' }}
            onClick={exportOpsTelemetryPack}
            disabled={running.opsTelemetry}
            title="Download host/DB samples, outbound HTTP digest, and job last-runs (no secrets)"
          >
            {running.opsTelemetry ? <><span className="admin-spinner" /> Exporting…</> : 'Export ops telemetry pack'}
          </button>
```

- [ ] **Step 2: Add Resources download using `windowKey`**

In `ResourcesPage.jsx`, add a sibling function that calls `/diagnostics/ops-telemetry-pack?window=${windowKey}` and names the file with `windowKey`. Place the button in `admin-resources-window-row` after the window toggles.

Do not use the string `resource utilization`.

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/admin/OverviewPage.jsx frontend/src/pages/admin/ResourcesPage.jsx
git commit -m "feat(admin): download ops telemetry pack from Overview and Resources"
```

---

### Task 5: Docs

**Files:**
- Modify: `docs/API_REFERENCE.md` (after support-pack)
- Modify: `docs/PRODUCT_STATUS.md` (Admin / Support pack sentence)

- [ ] **Step 1: API_REFERENCE**

Insert after `GET /api/admin/diagnostics/support-pack`:

```
### GET /api/admin/diagnostics/ops-telemetry-pack
Admin-gated JSON attachment of host/DB time series plus outbound HTTP digest for RCA.
Query `window` = `1d` | `3d` | `7d` | `30d` (default `1d`).
Filename `briefr-ops-telemetry-{window}-{stamp}.json`.
Body includes `ops_telemetry_pack_version`, `limitations`, raw `resource_metrics.samples` (not the 500-point chart downsample), `outbound_http`, `scheduler`, `efficiency`.
Audit: `diagnostics.ops_telemetry_pack`.
Does not attribute CPU peaks to a job. Does not invent samples from before the collector ran.
```

- [ ] **Step 2: PRODUCT_STATUS**

Add next to the Support pack sentence: **Ops telemetry pack** download on System health (1d) and Resources (selected window). Bump last-updated.

- [ ] **Step 3: verify-local**

Run: `./scripts/verify-local.sh`

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add docs/API_REFERENCE.md docs/PRODUCT_STATUS.md
git commit -m "docs: ops telemetry pack API and product status"
```
