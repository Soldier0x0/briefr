# Ops wording + DB command-timeout class fix — Implementation Plan

> **For agentic workers:** Execute task-by-task. Checkbox tracking. Docs+code in one PR.

**Goal:** (1) Replace user-visible jargon (circuit open, drain, LOCKED-as-word, watermark, token-bucket, RSS memory, etc.) with plain security-operator language everywhere in the product UI. (2) Fix the **class** of Postgres `command_timeout` failures on bulk `cves` writers (VulnCheck + CISA KEV + EPSS), not only one job.

**Architecture:** Shared `commit_every` cadence on bulk enrichment writers (same idea as `apply_additive_cve_enrichments`). UI copy centralized in `circuitLabels.js` / `catalog.js` / page strings. Internal API fields may stay `circuit_open`; UI never shows that phrase.

**Tech Stack:** Python FastAPI/asyncpg enrichment + React admin JSX; pytest + node tests; `./scripts/verify-local.sh` when feasible.

## Global Constraints

- Branch: `cursor/ops-wording-db-timeout-91c2` off `main`
- Do **not** “fix” timeouts by only raising `DATABASE_POOL_COMMAND_TIMEOUT_SECONDS`
- Do **not** rename study-guide chapter titles away from teaching “circuit breaker”; product UI uses plain words
- Distinguish **job paused by operator** vs **source paused (waiting to retry)**
- Minimum diff; match existing style
- User asked to merge after Gemini disposition

## File map

| Path | Role |
|------|------|
| `backend/db/enrichment.py` | Chunked commits in `sync_vulncheck_exploited_flags`, `mark_cves_as_kev`, `update_epss_scores`; safer `snapshot_epss_scores` if needed |
| `backend/scheduler.py` | Progress strings for VulnCheck DB phase; pass commit cadence if needed |
| `backend/tests/test_db_enrichment.py` | Regression tests for chunked commit behavior |
| `frontend/src/pages/admin/circuitLabels.js` | Plain labels: paused / waiting to retry |
| `frontend/src/pages/admin/catalog.js` | Open circuits → Sources paused; status labels |
| `frontend/.../OperatorSystemActions.jsx`, `StatusBar.jsx` | Finish jobs, then restart |
| `frontend/.../SchedulerPage.jsx`, `StatusLegend.jsx`, `JobTable` filters help | RUNNING not LOCKED in user text |
| `frontend/.../FeedHealthPage.jsx`, `AiOperationsPage.jsx`, `RateLimitPage.jsx`, `ResourcesPage.jsx`, `StoragePage.jsx`, `OverviewPage.jsx` | Copy sweep |
| `docs/HANDOVER.md` | Short note |

---

### Task 1: Failing tests for bulk commit cadence

**Files:** Modify `backend/tests/test_db_enrichment.py`

- [x] Add test that `sync_vulncheck_exploited_flags` accepts/uses intermediate commits when `commit_every` set (monkeypatch `db.commit` call count ≥ 2 for large synthetic catalog)
- [x] Extend/adjust `mark_cves_as_kev` / `update_epss_scores` tests similarly if signatures gain `commit_every`
- [x] Run: `cd backend && pytest tests/test_db_enrichment.py -q` → RED then GREEN after Task 2

### Task 2: Enrichment bulk writers — structural fix

**Files:** `backend/db/enrichment.py`, `backend/scheduler.py`

- [x] `sync_vulncheck_exploited_flags(..., *, commit_every: int | None = 50)` — commit after every N chunk UPDATEs; update progress via optional callback or scheduler progress keys
- [x] `mark_cves_as_kev(..., *, commit_every: int | None = 50)` — same
- [x] `update_epss_scores` — chunk `executemany` + commit_every
- [x] `snapshot_epss_scores` — if single `INSERT…SELECT` whole table: batch by CVE id chunks into history inserts (avoid one 60s+ statement)
- [x] Scheduler VulnCheck: set progress to “Updating … flags” before DB; call with commit_every
- [x] Commit

### Task 3: UI wording sweep

**Files:** listed in file map

- [x] circuitLabels: no user-facing “circuit”; prefer “Paused (waiting to retry)”, “Sources paused”, “Resume retries”
- [x] Drain → “Finish jobs, then restart” + confirm body
- [x] Glossary Open circuits → Sources paused
- [x] HelpTips: Feed Health, AI Ops, Rate limit, Storage watermark → sync checkpoint, Resources RSS → Process memory
- [x] Scheduler HelpTip: say RUNNING/busy not LOCKED; filter keys can stay LOCKED internally if statusLabel shows RUNNING
- [x] Tier A banner → clearer “historical backfill” if in scope of agreed list
- [x] Commit

### Task 4: Verify + PR

- [x] `pytest tests/test_db_enrichment.py tests/test_resilient_client.py -q` (and any admin label tests)
- [x] `cd frontend && npm run build`
- [x] HANDOVER note
- [ ] Push PR; wait Gemini; fix; merge when green

## Done when

- No user-visible “circuit open” / “Drain then restart” / misleading LOCKED-as-only-word on changed surfaces
- VulnCheck/KEV/EPSS bulk paths commit in chunks
- Tests + build pass; Gemini addressed; PR merged
