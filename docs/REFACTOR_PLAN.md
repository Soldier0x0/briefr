# BRIEFR Codebase Refactor — Execution Reference

> **Purpose**: Structural refactoring across backend and frontend. Zero behavior changes.  
> **Status**: PLAN ONLY — not started  
> **Scope**: Both backend (Python) and frontend (React), structural depth  

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

| Phase | What | Risk | Est. Lines Touched |
|-------|------|------|-------------------|
| 1 | CVE ID validator helper | Very Low | ~25 |
| 2 | Scheduler lock consolidation | Low | ~60 |
| 3 | Split `database.py` into `db/` package | Medium | ~3200 moved |
| 4 | Split `DetailDrawer.jsx` into folder | Low | ~1967 moved |
| 5 | Export util consolidation (frontend) | Low | ~400 moved |

**Execute phases in order. Run tests after each phase before continuing.**

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

## Final Verification (After All Phases)

```bash
# Backend
pytest backend/tests/ -x --tb=short
python -c "from database import get_db, upsert_cves, get_sync_state_value; print('all ok')"

# Frontend
npm run build
# Run app locally and smoke test:
# - CVE list loads
# - DetailDrawer opens
# - All tabs work
# - PDF/XLSX export downloads correctly
# - Admin scheduler page works (lock status)

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
```

Then open a single PR from `refactor/structural-cleanup` → `main`.
