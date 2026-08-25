# Ops telemetry pack — design spec

**Date:** 2026-08-25  
**Status:** Approved for planning (operator asked for a typed export of utilization history for humans and AI RCA, not a vague “resource utilization export”).  
**Plan:** `docs/superpowers/plans/2026-08-25-ops-telemetry-pack-plan.md`

Related: `backend/db/resource_metrics.py`, `backend/db/api_metering.py`, `backend/diagnostics/support_pack.py`, `frontend/src/pages/admin/OverviewPage.jsx`, `frontend/src/pages/admin/ResourcesPage.jsx`.

---

## 1. Name

**Product name: Ops telemetry pack**

Do not ship UI or filenames that say “resource utilization export”.

Pairing:

| Pack | Question it answers | Shape |
|------|---------------------|--------|
| **Support pack** (already shipped) | What is broken *right now*? | Point-in-time health, ~200 redacted logs, scheduler locks |
| **Ops telemetry pack** (this spec) | What was the box doing *over the last N days*? | Versioned JSON: host/DB samples, outbound API digest, job last-runs, honesty notes |

Rejected names: resource utilization export, capacity report (implies billing), diagnostics bundle (collides with support pack).

Download filename: `briefr-ops-telemetry-{window}-{stamp}.json`  
Example: `briefr-ops-telemetry-7d-20260825T121000Z.json`

## 2. Problem

Admin → Resources already charts `resource_metrics` (60s samples, 7–90 day retention, default 30). The chart series is **downsampled to ≤500 points**. There is no download of the **raw** window.

`GET /api/admin/diagnostics/support-pack` has no time series.

`api_call_events` is retained 30 days and has a CSV audit trail, but it is a separate click and is capped at 168h in `query_api_call_events`.

The 20s “Server may be overloaded” banner is a **client timeout** (`frontend/src/api.js` `REQUEST_TIMEOUT_MS = 20000`), not a CPU meter. RCA needs samples + outbound calls + job last-runs in one typed file.

## 3. Approaches considered

| Approach | Pros | Cons |
|----------|------|------|
| **A. New diagnostics JSON attachment** | Matches support pack UX; versioned schema; admin-gated | Another button |
| B. CSV of `resource_metrics` only | Simple | No API digest, no limitations block, useless for AI RCA |
| C. Extend support pack with 30d series | One download | Mixes “now” with “history”; huge support tickets |

**Chosen: A.** Keep support pack small. Add a sibling export.

## 4. Product contract

### Actor

Admin only (same gate as support pack).

### Entry points

1. Admin → System health → **Export ops telemetry pack** (window default `1d`).
2. Admin → Resources → **Export ops telemetry pack** (uses the selected chart window `1d|3d|7d|30d`).

No `briefr-doctor.sh` flag in v1 (YAGNI).

### HTTP

`GET /api/admin/diagnostics/ops-telemetry-pack?window=1d|3d|7d|30d`

- Default `window=1d`.
- Invalid window → 422.
- Response: `application/json` attachment (same pattern as support pack).
- Audit: `diagnostics.ops_telemetry_pack` with target equal to the window.

### JSON schema (version 1)

Top-level keys, all required:

```json
{
  "ops_telemetry_pack_version": 1,
  "generated_at": "ISO-8601 UTC",
  "window": "7d",
  "window_hours": 168,
  "retention_days": 30,
  "sample_interval_seconds": 60,
  "postgres_backend": true,
  "limitations": ["..."],
  "degraded": { "code": "ok|empty|sqlite|remote_pg", "message": "" },
  "resource_metrics": {
    "sample_count": 0,
    "truncated": false,
    "summary": {},
    "samples": []
  },
  "outbound_http": {
    "hours": 168,
    "total": 0,
    "by_source": [],
    "by_actor": [],
    "recent_limit": 200,
    "recent": []
  },
  "scheduler": {
    "locked_jobs": [],
    "last_runs": []
  },
  "efficiency": {}
}
```

`limitations` is a fixed list of strings (not free-form). v1 must include at least:

1. Samples have **no `job_id`**; a CPU peak cannot name the scheduler job.
2. History starts when `resource_metrics_sample` first wrote rows; the pack cannot invent earlier load.
3. Remote/container Postgres often nulls process CPU/RSS; SQL stats may still be present.
4. Chart `GET /api/admin/resources` downsamples to 500 points; this pack’s `samples` array is **raw** (not bucket-averaged), capped at `OPS_TELEMETRY_MAX_SAMPLES = 50000` with `truncated: true` if exceeded (newest retained).
5. `outbound_http.recent` is the newest 200 events in the window; `by_source` / `by_actor` cover the full window (hours may be 720 for `30d`, unlike the 168h clamp on the metering list API).

`resource_metrics.summary` reuses `summarize_metric` over **raw** rows (same as Resources page peaks).

`resource_metrics.samples` columns = `_RESOURCE_METRICS_COLUMNS` only. No secrets.

`outbound_http.recent` rows use the same public fields as `query_api_call_events` (`ts`, `source`, `method`, `host`, `path_template`, `status`, `latency_ms`, `actor_type`, `actor_id`, `job_id`, `run_id`, `request_id`). No request bodies, no API keys.

`scheduler.last_runs` = existing `sync_state` keys `scheduler.last_run.*` (same payload as `GET /api/admin/scheduler/history`).

`efficiency` = `build_efficiency_report` output (already redacted/config-oriented). If the report fails, set `efficiency` to `{"error": "unavailable"}` and still return 200.

### Honesty — do not claim

- Job-level CPU attribution (would need a new collector column — **not v1**).
- Samples from before the collector ran.
- That a 20s UI timeout equals host overload.

### Out of scope

- Ponytail / auto-tuning.
- Changing `RESOURCE_METRICS_RETENTION_DAYS`.
- Merging into the support pack.
- ZIP, protobuf, or CSV of the full pack.
- Adding `job_id` to `resource_metrics` rows.

## 5. Acceptance examples

- Unauthenticated GET → 401.
- `window=2d` → 422.
- After inserting two `resource_metrics` rows in-window, pack `resource_metrics.sample_count >= 2`, `samples` length matches (unless truncated), and `ops_telemetry_pack_version === 1`.
- `Content-Disposition` contains `briefr-ops-telemetry-` and `.json`.
- `limitations` is a non-empty list of strings.
- Router split inventory includes the new GET.

## 6. Risks

- 30d raw JSON can be several MB; keep indent=2 like support pack; do not gzip in v1.
- `metering_summary` currently clamps to 168h — do **not** reuse that clamp for `30d`. Add a window helper that allows up to 720h.
