# BRIEFR Codebase Refactor — Execution Reference

> **Purpose**: Refactoring across backend and frontend for structure, performance, security, and operability.  
> **Status**: PLAN ONLY — not started  
> **Scope**: Track A (Phases 1–5) is structural with zero behavior changes. Tracks B–D (Phases 6–10) are targeted hardening with small, isolated behavior changes, each independently revertable.  

---

## Current State Assessment (2026-07-02)

Verified against `main` at `705c733`:

- **Structural**: `backend/database.py` 3,197 lines, `backend/routers/admin.py` 1,907, `backend/scheduler.py` 1,603, `backend/routers/cves.py` 1,360, `frontend/src/components/DetailDrawer.jsx` 1,942. None of Phases 1–5 below have been executed (the 11 inline CVE-ID checks, flat `DetailDrawer.jsx`, and per-variable scheduler locks are all still present).
- **Security**: good baseline — `secrets.compare_digest` for admin/wallboard keys, JWT auth with short-lived access tokens, login rate limiting, production startup fails without `jwt_secret`, nginx security-header snippets in `deploy/`. Gap: `allow_legacy_admin_key` defaults to `True` (`settings.py:54`), leaving the pre-JWT header-key path enabled unless operators opt out.
- **Performance**: backend feeds share `resilient_client`; CVE list endpoints are paginated with bounded limits; 63 `CREATE INDEX` statements in the schema. Gaps: the frontend has no code-splitting at all — `jspdf`, `exceljs`, `html2canvas`, and `chart.js` ship in the single main bundle; embedding similarity is a brute-force cosine scan (acceptable at current scale, revisit only if measured slow).
- **Operability**: backend CI runs pytest (87 test files), Postgres pool integration tests, pip/npm dependency audits, and a Playwright smoke. Gaps: no linter or formatter is configured for either side (no ruff, no ESLint), and the frontend has zero unit tests.
- **Functionality**: new features are owned by `docs/ROADMAP.md` and its versioned release docs — this plan deliberately adds none. "Functionality" here means behavior preservation, enforced by the verify steps in every phase.

---

## ⚠️ PRE-FLIGHT (Do This Before ANY Code Change)

```bash
# 1. Make sure you are on main and it is clean
git checkout main
git pull origin main
git status   # must be clean

# 2. Create the refactor branch
git checkout -b refactor/structural-cleanup

# 3. Verify you are on the right branch before touching any file
git branch --show-current   # must print: refactor/structural-cleanup
```

**Do not edit any file until step 3 confirms the branch.**

---

## Overview

| Phase | Track | What | Risk | Est. Lines Touched |
|-------|-------|------|------|-------------------|
| 1 | A: Structure | CVE ID validator helper | Very Low | ~25 |
| 2 | A: Structure | Scheduler lock consolidation | Low | ~60 |
| 3 | A: Structure | Split `database.py` into `db/` package | Medium | ~3200 moved |
| 4 | A: Structure | Split `DetailDrawer.jsx` into folder | Low | ~1967 moved |
| 5 | A: Structure | Export util consolidation (frontend) | Low | ~400 moved |
| 6 | B: Security | Retire legacy admin key path by default | Low | ~10 |
| 7 | C: Performance | Frontend code-splitting (routes + export libs) | Low | ~60 |
| 8 | D: Operability | Backend lint/format (ruff) in CI | Low | config + CI |
| 9 | D: Operability | Frontend lint (ESLint) + unit tests (Vitest) in CI | Low | config + tests |
| 10 | C: Performance | DB hot-path index audit | Low | ~1 migration |

**Execute phases in order within a track. Track A first (Phases 1–5) — it creates the small, testable units that Phases 8–9 lint and test. Phase 6 is independent and can run at any point. Run tests after each phase before continuing.**

---

## Phase 1 — CVE ID Validator Helper

### Problem
`routers/cves.py` has this pattern 11 times:
```python
if not cve_id.upper().startswith("CVE-"):
    raise HTTPException(status_code=400, detail="Invalid CVE ID format")
```

### Fix
**Create** `backend/routers/_validators.py`:
```python
from fastapi import HTTPException

def require_cve_id(cve_id: str) -> str:
    """Normalize and validate CVE ID, raise 400 if invalid."""
    cve_id = cve_id.strip().upper()
    if not cve_id.startswith("CVE-"):
        raise HTTPException(status_code=400, detail="Invalid CVE ID format")
    return cve_id
```

**Edit** `backend/routers/cves.py`:
- Add `from routers._validators import require_cve_id` at top
- Replace all 11 occurrences of the inline check with `cve_id = require_cve_id(cve_id)`
- Occurrences are near lines: 690, 763, 790, 834, 957, 1043, 1100, 1125, 1213, 1243, 1278

### Verify
```bash
# Search confirms zero occurrences of the old pattern remain
grep -n "Invalid CVE ID format" backend/routers/cves.py  # should show 0 lines
grep -c "require_cve_id" backend/routers/cves.py        # should show 11
pytest backend/tests/ -k "cve" -x
```

---

## Phase 2 — Scheduler Lock Consolidation

### Problem
`scheduler.py` lines 70–84: 15 module-level locks as individual vars.  
`routers/admin.py` lines 72–87: string-keyed dict that maps job IDs to those var names.  
These are duplicated, fragile to sync.

### Fix
**Create** `backend/scheduler_locks.py`:
```python
import asyncio

_LOCKS: dict[str, asyncio.Lock] = {}

def _make_locks() -> dict[str, asyncio.Lock]:
    # Keys must match the `id=` strings passed to scheduler.add_job() exactly
    return {
        "nvd_incremental_sync": asyncio.Lock(),
        "kev_metadata_sync": asyncio.Lock(),
        "epss_score_sync": asyncio.Lock(),          # NOT epss_score_update
        "weekly_mitre_refresh": asyncio.Lock(),     # NOT mitre_atlas_refresh
        "atlas_version_check": asyncio.Lock(),
        "otx_nightly_correlation": asyncio.Lock(),
        "nightly_correlation": asyncio.Lock(),
        "incident_feed_refresh": asyncio.Lock(),
        "exploit_sources_sync": asyncio.Lock(),     # NOT exploit_sync
        "embeddings_backfill": asyncio.Lock(),      # NOT embedding_generation
        "llm_product_extraction": asyncio.Lock(),
        "vulnrichment_snapshot_sync": asyncio.Lock(),
        "cvelistv5_incremental_sync": asyncio.Lock(),
        "scheduled_backup": asyncio.Lock(),
        "backup_deadman_check": asyncio.Lock(),
        # _epss_backfill_lock has no corresponding job ID — keep as private var in scheduler.py
    }

_LOCKS = _make_locks()

def get_lock(job_id: str) -> asyncio.Lock | None:
    return _LOCKS.get(job_id)

def any_locked() -> bool:
    return any(l.locked() for l in _LOCKS.values())

def locked_jobs() -> list[str]:
    return [job_id for job_id, l in _LOCKS.items() if l.locked()]
```

**Edit** `backend/scheduler.py`:
- Remove 14 job-keyed `_*_lock` declarations (lines 70–83); keep `_epss_backfill_lock` as a private var since it has no APScheduler job ID
- Add `from scheduler_locks import get_lock` at top
- Replace all `async with _nvd_lock:` → `async with get_lock("nvd_incremental_sync"):` etc.
- Grep for all usages: `grep -n "_lock" backend/scheduler.py` to find every occurrence

**Edit** `backend/routers/admin.py`:
- Remove the `_JOB_LOCK_MAP` dict (lines 72–87)
- Add `from scheduler_locks import get_lock, any_locked, locked_jobs` at top
- Replace all lock lookups with `get_lock(job_id)`

### Verify
```bash
grep -n "_lock\b" backend/scheduler.py    # should be 0 module-level lock vars
grep -n "_JOB_LOCK_MAP" backend/routers/admin.py  # should be 0
pytest backend/tests/ -x
```

---

## Phase 3 — Split `database.py` into `db/` Package

### Context
`backend/database.py` is ~3197 lines. The `backend/db/` directory already exists with `connection.py`, `config.py`, `dialect.py`. We add domain modules to it and make `database.py` a thin re-export shim.

> **Note on line numbers**: The function table below reflects the line numbers at plan-writing time. Recent commits (ON CONFLICT `excluded.*` fixes) shifted some numbers by a few lines. Use the line numbers as a starting search point, not an exact address — `grep -n "^async def function_name"` is authoritative.

### New File Structure
```
backend/db/
├── __init__.py          # (already exists or create empty)
├── config.py            # (already exists — do not touch)
├── connection.py        # (already exists — do not touch)
├── dialect.py           # (already exists — do not touch)
├── init.py              # NEW: get_db, init_db, run_postgres_migrations, _init_postgres_schema
├── cve.py               # NEW: CVE CRUD + embeddings + related + LLM extraction
├── enrichment.py        # NEW: enrichment, backfill, KEV, change history, EPSS
├── cache.py             # NEW: ioc_cache, feed_cache, exploits
├── correlation.py       # NEW: OTX pulses/IOCs, suppressions, prioritization
├── watchlist.py         # NEW: watchlist CRUD
├── metadata.py          # NEW: MITRE, Atlas, AI/ML context, analytics
├── sync_state.py        # NEW: sync_state, NVD watermark, EPSS backfill key
└── webhooks.py          # NEW: webhook alerts, delivery, destinations
```

### Function → Module Mapping

#### `db/init.py`
| Line | Function |
|------|----------|
| 25 | `get_db` |
| 30 | `run_postgres_migrations` |
| 87 | `_init_postgres_schema` |
| 96 | `init_db` |

Also copy module-level constants and schema SQL strings needed by these functions.

#### `db/cve.py`
| Line | Function |
|------|----------|
| 737 | `cve_exists` |
| 952 | `upsert_cves` |
| 975 | `upsert_cve` |
| 979 | `get_cves_needing_intel_enrichment` |
| 1002 | `apply_additive_cve_enrichments` |
| 1069 | `delete_cves_by_ids` |
| 1084 | `purge_legacy_rejected_cves` |
| 1196 | `get_related_cves` |
| 1272 | `upsert_cve_embedding` |
| 1291 | `get_cve_embedding` |
| 1301 | `get_all_cve_embeddings` |
| 1318 | `count_cve_embeddings` |
| 1325 | `get_cves_missing_embeddings` |
| 1346 | `get_cve_summaries_by_ids` |
| 1377 | `get_cves_for_llm_product_extraction` |
| 1405 | `set_llm_affected_products` |

#### `db/enrichment.py`
| Line | Function |
|------|----------|
| 644 | `write_audit_log` |
| 748 | `_change_value_str` |
| 761 | `_values_differ` |
| 771 | `_normalize_epss_score` |
| 784 | `_epss_display_percent` |
| 791 | `_epss_scores_differ` |
| 868 | `_append_upsert_change_rows` |
| 902 | `_insert_cve_changes_batch` |
| 917 | `_load_cve_change_snapshots` |
| 1095 | `mark_cves_as_kev` |
| 1120 | `snapshot_epss_scores` |
| 1137 | `update_epss_scores` |
| 1180 | `get_epss_history` |
| 1426 | `backfill_display_fields` |
| 1463 | `strip_auto_generated_summaries` |
| 1491 | `backfill_has_poc` |
| 1519 | `get_recent_cve_changes` |
| 1549 | `enrich_kev_summaries` |
| 1574 | `upsert_kev` |
| 2869 | `filter_cves_matching_stack` |
| 2894 | `insert_epss_history_rows` |

Also includes `_clean_iso_date` (line 18) helper used by `upsert_kev`.

#### `db/cache.py`
| Line | Function |
|------|----------|
| 1618 | `get_ioc_cache` |
| 1631 | `get_ioc_cache_batch` |
| 1649 | `set_ioc_cache` |
| 1662 | `delete_feed_cache_prefix` |
| 1671 | `get_feed_cache` |
| 1687 | `set_feed_cache` |
| 1700 | `get_cached_cve_exploits` |
| 1709 | `store_cve_exploits` |
| 1721 | `read_cve_exploits_from_db` |
| 1748 | `update_cve_source_urls` |
| 1761 | `get_cve_ids_missing_circl_capec` |
| 1780 | `replace_cve_exploits` |
| 1807 | `_sqlite_changes` |
| 1813 | `merge_cve_exploits` |
| 1847 | `replace_cve_exploits_by_source` |
| 1887 | `mark_has_poc_additive` |

#### `db/correlation.py`
| Line | Function |
|------|----------|
| 1929 | `upsert_otx_pulses` |
| 1971 | `replace_otx_cve_pulses` |
| 2006 | `store_otx_cve_pulses` |
| 2014 | `read_otx_cve_pulses` |
| 2050 | `_pulse_ioc_lock` |
| 2055 | `replace_otx_pulse_iocs` |
| 2112 | `store_otx_pulse_iocs` |
| 2120 | `read_otx_pulse_iocs` |
| 2144 | `list_correlation_suppressions` |
| 2159 | `insert_correlation_suppression` |
| 2195 | `delete_correlation_suppression` |
| 2208 | `get_recent_cve_ids_for_otx` |
| 2227 | `get_cves_missing_otx_pulses` |
| 2260 | `get_embedding_boosted_cve_ids_for_otx` |
| 2318 | `get_prioritized_cve_ids_for_otx` |
| 3176 | `match_cves_for_assets` |

#### `db/watchlist.py`
| Line | Function |
|------|----------|
| 666 | `list_watchlist_entries` |
| 681 | `get_watchlist_entry` |
| 696 | `upsert_watchlist_entry` |
| 722 | `delete_watchlist_entry` |
| 731 | `delete_all_snooze_entries` |

#### `db/sync_state.py`
| Line | Constant/Function |
|------|----------|
| 2687 | `NVD_SYNC_WATERMARK_KEY` (constant) |
| 2688 | `EPSS_BACKFILL_DONE_KEY` (constant) |
| 2689 | `ATLAS_UPSTREAM_VERSION_KEY` (constant) |
| 2692 | `get_sync_state_value` |
| 2701 | `set_sync_state_value` |
| 2715 | `get_stack_terms` |
| 2919 | `get_nvd_sync_watermark` |
| 2927 | `set_nvd_sync_watermark` |
| 2940 | `seed_nvd_watermark_from_cves` |
| 2955 | `resolve_nvd_watermark` |

#### `db/metadata.py`
| Line | Function |
|------|----------|
| 2400 | `get_cve_count` |
| 2405 | `get_timeline_activity_summary` |
| 2428 | `get_last_updated` |
| 2435 | `get_all_cve_ids` |
| 2440 | `get_all_cve_ids_set` |
| 2445 | `replace_mitre_techniques` |
| 2470 | `clear_cve_technique_map` |
| 2474 | `upsert_cve_technique_pairs` |
| 2489 | `get_techniques_for_cve` |
| 2513 | `get_top_techniques` |
| 2538 | `get_mitre_technique_count` |
| 2543 | `replace_atlas_techniques` |
| 2586 | `replace_atlas_case_studies` |
| 2614 | `get_atlas_technique_count` |
| 2619 | `get_atlas_techniques_grouped` |
| 2649 | `_parse_json_list` |
| 2659 | `get_atlas_case_studies` |
| 2964 | `clear_cve_atlas_map` |
| 2968 | `upsert_cve_atlas_pairs` |
| 2983 | `replace_cve_atlas_map_for_cve` |
| 2994 | `get_atlas_techniques_for_cve` |
| 3020 | `get_atlas_case_studies_for_cve` |
| 3047 | `count_ai_ml_profile_alerts` |
| 3074 | `refresh_all_cve_ai_context` |
| 3126 | `replace_mitre_groups` |
| 3158 | `upsert_group_technique_pairs` |
| 3171 | `get_mitre_group_count` |

#### `db/webhooks.py`
| Line | Constant/Function |
|------|----------|
| 2720 | `_WEBHOOK_ALERT_ALIASES` (constant) |
| 2728 | `_webhook_alert_types` |
| 2732 | `was_webhook_alert_sent` |
| 2747 | `record_webhook_alert` |
| 2759 | `clear_webhook_alert` |
| 2770 | `record_webhook_delivery` |
| 2789 | `list_webhook_destinations` |
| 2800 | `update_webhook_destination` |
| 2831 | `list_webhook_delivery_log` |

### The Backward-Compat Shim

After moving all functions, replace `database.py` content with:
```python
"""Backward-compatibility shim — import from db.* submodules directly for new code."""
from db.init import get_db, init_db, run_postgres_migrations
from db.cve import *
from db.enrichment import *
from db.cache import *
from db.correlation import *
from db.watchlist import *
from db.sync_state import *
from db.metadata import *
from db.webhooks import *

# Re-export constants
from db.sync_state import NVD_SYNC_WATERMARK_KEY, EPSS_BACKFILL_DONE_KEY, ATLAS_UPSTREAM_VERSION_KEY
```

This means **zero changes needed** in any of the 35+ files that `from database import ...`.

### All Callers (do NOT need to change, but verify imports still resolve)
```
backend/main.py
backend/dependencies.py
backend/feeds/poc_github.py
backend/feeds/otx_continuous.py
backend/feeds/otx.py
backend/webhooks/engine.py
backend/scripts/create_user.py
backend/feeds/nuclei_index.py
backend/feeds/mitre.py
backend/webhooks/alerts.py
backend/feeds/metasploit_modules.py
backend/feeds/incident_news.py
backend/wallboard/service.py
backend/feeds/extended.py
backend/tracking.py
backend/feeds/exploit_sync.py
backend/feeds/exploitdb.py
backend/scheduler.py
backend/feeds/case_study_feed.py
backend/feeds/atlas.py
backend/ml/product_extraction.py
backend/ml/embeddings.py
backend/correlation/campaigns.py
backend/correlation/confirm.py
backend/correlation/engine.py
backend/routers/watchlist.py
backend/routers/brief.py
backend/routers/auth.py
backend/routers/atlas.py
backend/routers/ioc.py
backend/routers/admin.py
backend/routers/health.py
backend/routers/cves.py
backend/routers/forge.py
backend/detection/rule_sources.py
backend/correlation/suppressions.py
```

### Verify Phase 3
```bash
python -c "import database; print('shim ok')"
python -c "from database import get_db, upsert_cves, get_feed_cache, set_sync_state_value; print('imports ok')"
pytest backend/tests/ -x
```

---

## Phase 4 — Split `DetailDrawer.jsx`

### Problem
`frontend/src/components/DetailDrawer.jsx` is 1967 lines: 4 tab sections + 8 inline helpers.

### New Structure
```
frontend/src/components/DetailDrawer/
├── index.jsx        # shell component: tab bar, state, open/close — keep default export
├── OverviewTab.jsx  # severity, CVSS, KEV badges, published/modified dates
├── IntelTab.jsx     # OTX pulses, actor correlation, campaigns
├── DetectTab.jsx    # Sigma rules, hunt packs, MITRE technique mapping
├── RelatedTab.jsx   # linked CVEs, related techniques
└── helpers.js       # severityColor, drawerEpssBarColor, exploitTypeLabel,
                     # truncateText, techniqueLink (all currently inline)
```

**All existing import sites** use:
```js
import DetailDrawer from './components/DetailDrawer'
// or
import DetailDrawer from '../components/DetailDrawer'
```

Because `index.jsx` is the default export in a folder, these imports keep working with no changes.

### Steps
1. Create folder `frontend/src/components/DetailDrawer/`
2. Copy the full current file to `index.jsx` first (ensures nothing is lost)
3. **Fix relative import paths inside `index.jsx`**: moving from `components/DetailDrawer.jsx` to `components/DetailDrawer/index.jsx` adds one level of nesting. Any `../utils/foo` imports become `../../utils/foo`, any `../hooks/bar` become `../../hooks/bar`, etc. Run `grep -n "^\s*import.*'\.\." index.jsx` to find all that need updating.
4. Extract each tab's JSX into its own file, import in `index.jsx`
5. Extract the helper functions into `helpers.js`, import in files that use them
6. Delete `DetailDrawer.jsx` (original flat file) once build passes

### Verify
```bash
npm run build          # must succeed with 0 errors
# Then open the app in browser and verify:
# - DetailDrawer opens on CVE click
# - All 4 tabs (Overview, Intel, Detect, Related) render correctly
# - Closing/opening works
```

---

## Phase 5 — Frontend Export Utility Consolidation

### Problem
Three export files duplicate header generation, date formatting, and cell styling:
- `frontend/src/utils/pdfReport.js` (526 lines)
- `frontend/src/utils/investigationPdf.js` (315 lines)
- `frontend/src/utils/exportXlsx.js` (306 lines)

### Fix
**Create** `frontend/src/utils/exportCommon.js` with shared pure functions.  
**Edit** the three files to import from it, removing local duplicates.

Before starting this phase, read all three files side-by-side to catalog the exact duplicate logic. Common candidates:
- Date formatting helpers
- Table header/border styles
- Severity color mapping
- File save boilerplate

Only extract what is truly duplicated (identical or near-identical logic). Leave file-format-specific code in its original file.

### Verify
```bash
npm run build
# Manually trigger PDF export from a CVE detail view
# Manually trigger XLSX export
# Verify files download and are valid
```

---

## Phase 6 — Retire Legacy Admin Key Path by Default

### Problem
`backend/settings.py:54` sets `allow_legacy_admin_key: bool = True`. `backend/dependencies.py:74–78` therefore accepts the pre-JWT `X-BRIEFR-Admin-Key`-style header on admin routes in every deployment unless the operator explicitly disables it. JWT auth is the intended gate; the legacy path should be opt-in, not opt-out.

### Fix
- **Edit** `backend/settings.py`: change the default to `allow_legacy_admin_key: bool = False`.
- **Edit** docs that describe admin auth (`grep -rn "allow_legacy_admin_key" docs/ README.md` to find them): state that existing deployments relying on the admin key must set `ALLOW_LEGACY_ADMIN_KEY=true` or migrate to a user login.
- **Add** a test in `backend/tests/` asserting that with default settings the legacy key is rejected, and that setting the flag re-enables it.

This is a deliberate behavior change — call it out in the PR description as a breaking change for key-only deployments.

### Verify
```bash
pytest backend/tests/ -k "admin or auth" -x
grep -n "allow_legacy_admin_key" backend/settings.py   # default False
```

---

## Phase 7 — Frontend Code-Splitting

### Problem
`frontend/src/App.jsx` imports every page and component statically, and `frontend/vite.config.js` has no `build` configuration. `jspdf` (~350 kB), `exceljs` (~940 kB), `html2canvas` (~200 kB), and `chart.js` all land in the single entry bundle, paid on first load by every user — including ones who never export a report.

### Fix
1. **Export libs on demand** — in `frontend/src/utils/pdfReport.js`, `investigationPdf.js`, and `exportXlsx.js`, replace top-level `import { jsPDF } from 'jspdf'` / `import ExcelJS from 'exceljs'` / `html2canvas` imports with `const { jsPDF } = await import('jspdf')` (for named exports) and `const { default: ExcelJS } = await import('exceljs')` (for default exports) inside the export functions. The export functions are already async or can become async; their callers are click handlers.
2. **Lazy routes** — in `App.jsx`, wrap the non-landing routes (admin pages, Wallboard, Forge, IOC lookup) in `lazyWithReload(() => import(...))` (using the project's existing utility from `./utils/lazyWithReload.js`) with a `<Suspense>` fallback. Do this *after* Phase 4 so `DetailDrawer` is already a folder.
3. **Chart chunk (optional)** — if `chart.js` still dominates the main chunk after steps 1–2, add `build.rollupOptions.output.manualChunks` in `vite.config.js` to split it.

### Verify
```bash
cd frontend && npm run build   # record chunk sizes BEFORE starting, compare after
# Main bundle should shrink by roughly the size of jspdf+exceljs+html2canvas.
# Manually: load app, open a CVE, trigger PDF and XLSX export — both must still work
# (network tab shows the chunks loading on demand).
```

---

## Phase 8 — Backend Lint/Format (ruff) in CI

### Problem
No linter or formatter is configured for the backend. Style drift and dead imports accumulate unchecked; the CI in `.github/workflows/backend-tests.yml` runs tests and audits but no static checks.

### Fix
- **Create** `backend/ruff.toml`: `target-version = "py312"`, start with the default rule set plus `I` (import sorting). Do **not** enable formatting rules that would rewrite the whole tree in one diff.
- Run `ruff check backend/` once; fix trivial findings (unused imports, obvious bugs) and add narrowly-scoped `per-file-ignores` for anything noisy, so the initial diff stays reviewable.
- **Edit** `.github/workflows/backend-tests.yml`: add a `ruff check` step (or job) before pytest.

### Verify
```bash
cd backend && ruff check .        # exits 0
pytest tests/ -q                  # unchanged behavior
```

---

## Phase 9 — Frontend Lint (ESLint) + Unit Tests (Vitest) in CI

### Problem
The frontend has no ESLint config and zero unit tests; the only coverage is the backend-driven Playwright smoke. The pure helpers extracted in Phases 4–5 (`DetailDrawer/helpers.js`, `utils/exportCommon.js`) are exactly the code unit tests are cheap for.

### Fix
- **Create** `frontend/eslint.config.js` (flat config) with `@eslint/js` recommended, `eslint-plugin-react` (recommended), and `eslint-plugin-react-hooks`. Fix or locally disable existing findings — keep the initial diff mechanical.
- **Add** Vitest as a dev dependency with a `test` script; write unit tests for the pure helpers from Phases 4–5 (severity/color mapping, date formatting, truncation).
- **Edit** the CI workflow: add `npm run lint` and `npm test` steps to the existing frontend job.

### Verify
```bash
cd frontend && npx eslint src/ && npm test && npm run build
```

---

## Phase 10 — DB Hot-Path Index Audit

### Problem
The schema defines 63 indexes, but they were added incrementally; nobody has verified they cover the filter/sort combinations the paginated CVE list endpoints (`backend/routers/cves.py`, `CVE_SELECT` + `CVE_ORDER_BY` + dynamic `WHERE`) actually issue.

### Fix
1. Catalog the WHERE/ORDER BY combinations produced by the list endpoints and the scheduler's batch queries (`get_cves_missing_embeddings`, `get_prioritized_cve_ids_for_otx`, etc. — post-Phase-3 these live in `backend/db/`).
2. Run `EXPLAIN QUERY PLAN` (SQLite) / `EXPLAIN ANALYZE` (Postgres) on each against a realistically-sized DB.
3. Add only the composite indexes that measurements justify, as one Alembic migration plus the SQLite schema-parity equivalent (follow the pattern in `backend/alembic/versions/004_sqlite_schema_parity.py`).
4. The embeddings brute-force cosine scan (`get_all_cve_embeddings`) is explicitly **out of scope** unless step 2 measures it as a problem — pgvector is a Beta V2.0 (Postgres-era) decision, per `docs/ROADMAP.md`.

### Verify
```bash
pytest backend/tests/ -x
python scripts/verify_db_parity.py     # SQLite/Postgres schema parity holds
# EXPLAIN output for each cataloged query shows index usage, no full scans on cves
```

---

## Final Verification (After All Phases)

```bash
# Backend
cd backend && ruff check . && pytest tests/ -x --tb=short
python -c "from database import get_db, upsert_cves, get_sync_state_value; print('all ok')"

# Frontend
cd ../frontend && npx eslint src/ && npm test && npm run build
# Compare final chunk sizes against the pre-Phase-7 baseline.
# Run app locally and smoke test:
# - CVE list loads
# - DetailDrawer opens
# - All tabs work
# - PDF/XLSX export downloads correctly (chunks load on demand)
# - Admin scheduler page works (lock status)
# - Admin routes reject the legacy key with default settings

# Git
git diff main --stat   # review what changed
git log --oneline      # confirm all phases committed separately
```

---

## Commit Strategy

Make **one commit per phase** so each is independently revertable:
```
refactor: extract CVE ID validator helper (phase 1)
refactor: consolidate scheduler lock management (phase 2)
refactor: split database.py into db/ package (phase 3)
refactor: split DetailDrawer into tab components (phase 4)
refactor: consolidate PDF/XLSX export utilities (phase 5)
security: disable legacy admin key path by default (phase 6)
perf: code-split export libs and lazy-load routes (phase 7)
ci: add ruff lint for backend (phase 8)
ci: add ESLint and Vitest for frontend (phase 9)
perf: add composite indexes for CVE list hot paths (phase 10)
```

Ship Track A (Phases 1–5) as one PR from `refactor/structural-cleanup` → `main`. Phases 6–10 are each small enough to be their own PR — Phase 6 in particular should be a standalone PR so the breaking-change note is visible in its own right.

---

# Addendum — Architecture Review (2026-07-04)

> **Status**: REVIEW + PLAN ONLY — no code changes. Verified against the
> working tree at `1362df2`. This addendum records the system-level findings
> an independent architecture pass surfaced *beyond* Phases 1–10 above, and
> adds Track E (Phases 11–15). Phases 1–10 remain valid and unchanged; every
> line-count and duplication claim in the 2026-07-02 assessment was re-verified
> and still holds.

## A. Architecture as-built (reverse-engineered data flow)

```
            ┌────────────────────────── single uvicorn worker (--workers 1) ──────────────────────────┐
            │                                                                                          │
 External   │  APScheduler (in-process, scheduler.py, 15 asyncio.Lock guards)                          │
 sources ──▶│    feeds/*  (NVD, KEV, EPSS, CVEList v5, vulnrichment, OTX, ExploitDB, Metasploit,       │
 (HTTPS)    │              Nuclei, PoC-GitHub, MITRE ATT&CK/ATLAS, incident news)                      │
            │       │  all outbound HTTP → resilient_client.py (shared httpx, retries, breakers)       │
            │       │                       → api_queue.py (per-source pacing, in-memory state)        │
            │       ▼                                                                                  │
            │  ml/ (fastembed ONNX embeddings), ai/ (LLM product extraction)  ← scheduler-side only    │
            │       │                                                                                  │
            │       ▼                                                                                  │
            │  database.py (3,197 lines, ~120 fns) ── db/dialect.py (regex SQLite→PG translation)      │
            │       │                                 db/connection.py (asyncpg pool | aiosqlite)      │
            │       ▼                                                                                  │
            │  PostgreSQL (prod) / SQLite (dev+tests)                                                  │
            │       ▲                                                                                  │
            │  routers/* (thin-ish handlers; reads + cached lookups only, per danger-zone 6)           │
            │  correlation/ (campaigns, confidence, suppressions)   webhooks/ (alert dedupe, delivery) │
            └──────────────────────────────────────────────────────────────────────────────────────────┘
                     ▲ /api (nginx proxy)
 React 19 SPA: App.jsx (~21 useState, prop-drilled) → components fetch via api.js (hand-rolled,
 401-refresh single-flight) — no data-fetching layer, no code-splitting except BriefCharts.
```

Write path: scheduler job → feed fetch (queued/paced) → `upsert_*`/`replace_*`
in `database.py` → change rows (`cve_changes`) → webhook engine.
Read path: router → `get_db()` (new connection/pool-acquire per call) →
SQLite-dialect SQL → runtime translation → response; frontend surfaces
`detail` + `X-Request-ID`.

## B. Findings beyond Phases 1–10

### E1. The runtime SQL translation layer is the largest structural risk
`db/dialect.py` rewrites SQLite SQL to PostgreSQL with regexes at query time,
while tests run mostly SQLite and production is Postgres-only. This inverts
the test pyramid: the dialect the tests exercise is the one production never
runs. CLAUDE.md danger-zone 1 documents the hazard instead of removing it.
Direction (post-Phase-3, incremental): run the backend test suite against
PostgreSQL in CI as a first-class matrix leg (testcontainers or the existing
pool-integration harness), then migrate hot query paths to native Postgres SQL
module-by-module inside the new `db/` package, shrinking `dialect.py` until it
guards only the SQLite dev path — or is deleted when SQLite dev support is
formally dropped.

### E2. One process runs the API, the scheduler, and ML inference
`deploy/briefr-backend.service` pins `--workers 1`, and the codebase requires
it: APScheduler jobs, 15 module-level `asyncio.Lock`s, in-memory token buckets
(`rate_limit.py` says so explicitly), and `api_queue.py` state are all
process-local. Consequences: (a) zero horizontal scaling; (b) CPU-bound work
(fastembed ONNX batches, large ingest parses) shares the event-loop process
with request handling, so p99 latency degrades during syncs — danger-zone 6
keeps heavy work off the *request path* but not off the *request process*.
Phase 14 below is the unlock; it is deliberately optional/env-gated so
single-box deployments keep today's behavior.

### E3. Connection-per-call with manual lifecycle at 153 call sites
`await get_db()` + `try/finally: close()` is repeated ~153 times (20× in
`routers/cves.py`, 24× in `routers/admin.py` alone). No request-scoped
dependency exists; a missed `finally` leaks a pool slot until timeout. On the
SQLite path each call is a fresh file open + 3 PRAGMAs. Phase 12 replaces the
boilerplate with one FastAPI dependency.

### E4. Every Postgres read opens an explicit transaction
`PostgresConnection._ensure_transaction()` starts a transaction on the first
`execute`/`execute_fetchall`, so read-only endpoints hold an open transaction
for the connection's lifetime — inflating pool hold time and vacuum horizon
under load. Read-only statements could run without an explicit transaction
(asyncpg autocommits single statements). Small, isolated, measurable — folded
into Phase 12.

### E5. `executemany` re-translates SQL once per row
`PostgresConnection.executemany` calls `prepare_query(sql, p)` for every
params row; `_postgres_translate_sql` (a multi-regex pass) has no cache (only
`_colon_to_dollar` is `lru_cache`d). A 5,000-row CVE upsert runs the full
regex pipeline 5,001 times. Fix: translate once, then adapt params per row —
or add `@lru_cache` to `_postgres_translate_sql`. ~10 lines, pure win.

### E6. Fifteen copy-pasted scheduler job wrappers
Every `run_*` in `scheduler.py` repeats the same shape: check lock → log skip
→ acquire lock → call `_run_*` → record `job_last_run`. Phase 2 consolidates
the *locks*; Phase 11 consolidates the *wrapper* with a registry decorator,
which also gives `routers/admin.py` one introspection surface.

### E7. Frontend has no data layer; App.jsx is the state container
`App.jsx` (727 lines) holds ~21 `useState`s and prop-drills filters, drawer
state, watchlist, health, and timezone into the tree; 22 components fetch
independently through 53 hand-written functions in `api.js`. There is no
caching, request dedupe, or revalidation, and cross-cutting state changes
force wide re-renders. Phase 15 extracts per-domain hooks *without* adopting a
new library, keeping the diff mechanical.

### E8. Batch/duplicate DB write variants
`replace_cve_exploits`, `replace_cve_exploits_by_source`, and
`merge_cve_exploits` are near-identical delete+insert shapes, as are the
`store_/read_/replace_` OTX triplets. Not urgent — but Phase 3's `db/cache.py`
and `db/correlation.py` moves are the moment to collapse them behind one
parameterized helper each, while the functions are being touched anyway.

### E9. Documented drift is institutionalized
Four root-level snapshot docs (`CODEBASE_CONTEXT.md`, `FOLDER_STRUCTURE_GUIDE.md`,
`APPLICATION_EXECUTION_MAP.MD`, `TECHNICAL_INVENTORY.md`) are declared "may lag
the code" by CLAUDE.md. Stale-by-design docs cost every reader a verification
pass. Recommendation (docs-only, no phase): fold what is still accurate into
`docs/` equivalents and reduce each root snapshot to a pointer, per
`DOCUMENTATION_PLAN.md`.

## C. Target architecture (end-state after Tracks A–E)

```
backend/
  routers/        thin HTTP: validation (deps), status codes, no SQL
  services/       (emerges naturally: brief/, correlation/, detection/, scoring/ already are this)
  db/             repositories per domain (Phase 3) + connection/dialect infra
  feeds/          pull adapters — fetch/parse only, persist via db/ repos
  scheduler/      job registry (Phase 11) + runner; extractable to its own process (Phase 14)
  infra           resilient_client, api_queue, rate_limit, structured_logging
frontend/src/
  api/            request core + per-domain modules (split of api.js)
  hooks/          data hooks owning fetch/cache/error state (Phase 15)
  components/     presentational; DetailDrawer/ as folder (Phase 4)
```

Rule of the layering: routers never touch SQL; feeds never touch HTTP response
shaping; only `db/` speaks SQL; only `infra` speaks sockets.

## D. Track E — additional phases (all behavior-preserving unless noted)

### Phase 11 — Scheduler job registry (after Phase 2)
**Create** `backend/scheduler_jobs.py`. **Move** `_write_job_last_run` out of
`scheduler.py` into this module verbatim (it depends only on `database` /
sync-state helpers, not on scheduler state) — moving it, rather than importing
it back from `scheduler.py`, is what keeps `scheduler.py → scheduler_jobs.py`
a one-way dependency with no import cycle:
```python
import asyncio, logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

# _write_job_last_run(job_id, start: datetime, records=0, had_error=False,
# error_message="") lives here now — moved unchanged from scheduler.py.

@dataclass
class Job:
    job_id: str
    fn: Callable[[], Awaitable[int | None]]
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

_REGISTRY: dict[str, Job] = {}

def scheduled_job(job_id: str):
    """Register a job body; the wrapper owns skip-if-running, locking,
    and job_last_run bookkeeping that today is copy-pasted 15 times.
    The body may return an int (records upserted) or None."""
    def decorate(fn: Callable[[], Awaitable[int | None]]):
        job = Job(job_id=job_id, fn=fn)
        _REGISTRY[job_id] = job

        async def run() -> bool:
            if job.lock.locked():
                logger.info("%s already running — skipped", job_id)
                return False
            async with job.lock:
                started = datetime.now(timezone.utc)
                records, error = 0, ""
                try:
                    records = await fn() or 0
                except Exception as exc:          # noqa: BLE001 — job boundary
                    error = str(exc)
                    logger.exception("%s failed", job_id)
                finally:
                    await _write_job_last_run(
                        job_id,
                        started,
                        records=records,
                        had_error=bool(error),
                        error_message=error,
                    )
                return not error
        run.job = job
        return run
    return decorate

def get_job(job_id: str) -> Job | None: return _REGISTRY.get(job_id)
def locked_jobs() -> list[str]:
    return [j.job_id for j in _REGISTRY.values() if j.lock.locked()]
```
Then each `run_*` collapses to its `_run_*` body under
`@scheduled_job("nvd_incremental_sync")`, and `routers/admin.py` introspects
`_REGISTRY` instead of a parallel map. Supersedes the lock-map sync hazard
permanently. *Verify*: `pytest tests/ -k scheduler -x`; admin scheduler page
shows identical job list/lock states.

### Phase 12 — Request-scoped DB dependency (after Phase 3)
**Add** to `backend/dependencies.py`:
```python
from collections.abc import AsyncIterator
from database import get_db

async def db_conn() -> AsyncIterator:
    """Yield a connection bound to the request; always released, one place."""
    db = await get_db()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()
```
Handlers become `async def stats(db = Depends(db_conn))` — migrate router by
router (mechanical, ~153 sites shrink as touched; no flag-day). Fold in E4
here: give `PostgresConnection.execute_fetchall` a no-transaction fast path
for connections that have not written. Fold in E5: hoist translation out of
the per-row loop in `executemany`. *Verify*: full pytest + pool integration
tests; pool `in_use` gauge flat under `ab -c 20` against `/api/cves`.

### Phase 13 — Postgres-first CI (independent; do before large SQL edits)
Add a CI matrix leg running `pytest backend/tests/` with `DATABASE_URL`
pointing at a service-container Postgres (the pool integration harness already
proves the plumbing). Tests that are SQLite-mechanism-specific get a skip
marker. This turns danger-zone 1 from "reviewer vigilance" into "CI failure".
No app code changes. *Verify*: both matrix legs green on an untouched tree.

### Phase 14 — Extractable worker process (behavior change: opt-in flag)
Goal: allow `BRIEFR_ROLE=web|worker|all` (default `all` = today's behavior).
`worker` runs lifespan + scheduler with no HTTP; `web` skips
`start_scheduler()`. Prerequisites created by earlier phases: job registry
(11), no in-process lock introspection from admin (11 exposes it via DB
`job_last_run`/lock table or Postgres advisory locks — `pg_try_advisory_lock`
keyed by job id replaces `asyncio.Lock` when role-split is active). In-memory
rate limits stay valid per-web-process only after documenting that `web` may
then scale to N workers. This is the only path to multi-worker uvicorn and to
keeping ONNX inference off the serving process. Ship dark (flag default
`all`), soak on the beta box, then flip the deploy unit to two services.

### Phase 15 — Frontend data hooks + api.js split (after Phases 4–5)
Split `api.js` (455 lines, 53 exports) into `src/api/core.js` (request/refresh
logic — unchanged) plus per-domain modules (`api/cves.js`, `api/admin.js`,
`api/auth.js`, …) re-exported from `api/index.js` so existing imports keep
working. Extract repeated component fetch patterns into hooks
(`useApi(fetcher, deps)` returning `{data, error, loading, reload}`) and move
App.jsx's health/stats/schedule polling into `useFeedHealth()` /
`useStats()`. No new dependency; App.jsx shrinks toward routing + layout.
*Verify*: `npm run build`; feed, drawer, admin pages exercise identical
network calls (compare devtools HAR before/after).

## E. Priority order (impact ÷ risk)

| Order | Item | Why first |
|-------|------|-----------|
| 1 | Phase 13 (Postgres CI) | Cheapest insurance; de-risks every later SQL-touching phase |
| 2 | Phases 1–2, 11 | Small, kills the two live sync hazards (CVE-ID checks, lock map) |
| 3 | Phase 3 (db split) + E8 collapse | Unlocks ownership boundaries everything else assumes |
| 4 | Phases 4, 5, 7, 15 | Frontend: bundle size + maintainability, all mechanical |
| 5 | Phases 12 (incl. E4/E5), 10 | Measured DB-path wins |
| 6 | Phases 6, 8, 9 | Hardening + guardrails once structure has settled |
| 7 | Phase 14 | Largest payoff, largest blast radius — last, behind a flag |
