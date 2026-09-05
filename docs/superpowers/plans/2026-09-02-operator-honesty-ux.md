# Operator honesty UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Do not implement on SQLite PR #752.** One PR per workstream below. Base each PR on current `main`.

**Goal:** Make operator numbers, notifications, stack, briefs, headlines, DETECT, Related, and ENV webhooks match live truth without destroying history.

**Architecture:** Reuse `user_notifications.dismissed_at` (do not delete on job success). Fix `fetch_table_sizes` to `app`/`intel`. Stop FEED seed from My Stack. Brief labels via `software_catalog`. ENV delete writes config, not a hide-flag. UI tokens from `frontend/src/styles/tokens.css` only.

**Tech Stack:** FastAPI, asyncpg, React/Vite, existing Admin CSS (`admin-two-col`), Discord embed JSON (one embed).

**Spec:** `docs/superpowers/specs/2026-09-02-operator-honesty-ux-design.md`

## Global Constraints

- Dark-only; semantic tokens; no Fira/cyberpunk; no emoji icons.
- Merge gate: `./scripts/verify-local.sh`. Frontend: `cd frontend && npm run test:unit && npm run build`.
- After each code edit: `graphify update .` from the repository root. Do not commit `graphify-out/` (gitignored).
- Update `docs/PRODUCT_STATUS.md` and `docs/API_REFERENCE.md` in the PR that changes the contract.
- Do not invent CPE vendor names. Do not hard-delete notification rows on job success.
- Process-level env vars still win over `backend/.env` (`load_dotenv` without override) — webhook Delete must say so if the URL remains injected.

## File map

| File | Responsibility |
|------|----------------|
| `backend/storage_metrics.py` | Table sizes for `app`+`intel`; optional system |
| `backend/efficiency_audit.py` | Subsystem bytes from those sizes |
| `backend/db/database_metrics.py` | Stop `public`-only if it still feeds operator UI |
| `backend/routers/admin/storage.py` | Join counts to sized tables; separate backup vs DB forecast |
| `frontend/src/pages/admin/StoragePage.jsx` | DBA table; no backup-trend caption on TABLE SIZES |
| `frontend/src/pages/admin/ResourcesPage.jsx` | Efficiency bytes; pool counts; later 2-col |
| `frontend/src/pages/admin/formatters.js` | Keep `fmtBytes` for bytes only |
| `backend/scheduler.py` | After successful `_write_job_last_run`, dismiss open `job_error` for that job |
| `backend/db/user_notifications.py` | Bulk dismiss by `entity_type`+`entity_id` |
| `backend/reports/daily_brief.py` | Titles, lede, ops from open jobs, one severity field |
| `backend/reports/market_clusters.py` | Catalog display names |
| `frontend/src/App.jsx` | Remove My Stack → FEED seed |
| `backend/preferences/repo.py` / `backend/db/sync_state.py` | Env stack migrate-once |
| `backend/feeds/incident_news.py` | Event title excludes; no title-as-description |
| `frontend/src/components/advisories/shared.jsx` | Skip equal subtitle |
| `frontend/src/components/DetailDrawer/DetectTab.jsx` | Framing only when community > 0 |
| `frontend/src/components/DetailDrawer.css` | Related type floor |
| `frontend/src/components/DetailDrawer/RelatedTab.jsx` | Similarity layout without CVSS spacer |
| `backend/webhooks/destinations.py` | Skip bootstrap when URL cleared |
| `backend/routers/admin/webhooks.py` | Allow Delete of reserved ids via config clear |
| `frontend/src/pages/admin/WebhookDestinationCard.jsx` | Show Delete on env cards |

---

### Task 1: PR — honest table sizes + pool counts (ship first)

**Files:**
- Modify: `backend/storage_metrics.py`
- Modify: `backend/efficiency_audit.py`
- Modify: `backend/db/database_metrics.py` (if `nspname = 'public'` still used for operator sizes)
- Modify: `backend/routers/admin/storage.py`
- Modify: `frontend/src/pages/admin/StoragePage.jsx`
- Modify: `frontend/src/pages/admin/ResourcesPage.jsx` (`PoolStatsCard` / `CapacityBar`)
- Test: `backend/tests/test_admin_storage.py`, `backend/tests/test_efficiency_audit.py`, `frontend/src/pages/admin/formatters.test.js` (or a new `ResourcesPage` unit if formatters stay bytes-only)

**Interfaces:**
- Consumes: asyncpg `pg_class` / `pg_namespace`
- Produces: `fetch_table_sizes(db, *, include_system: bool = False) -> list[dict]` with keys `schema`, `table`, `size_bytes`

- [ ] **Step 1: Write the failing test**

Add in `backend/tests/test_admin_storage.py` (or new `test_storage_metrics.py`):

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_table_sizes_includes_app_or_intel(pg_db):
    from storage_metrics import fetch_table_sizes
    rows = await fetch_table_sizes(pg_db)
    pairs = {(r["schema"], r["table"]) for r in rows}
    assert ("app", "api_call_events") in pairs or ("intel", "cves") in pairs or any(
        schema in {"app", "intel"} for schema, _table in pairs
    )
    assert all(schema in {"app", "intel"} for schema, _table in pairs)
    assert all(table != "procrastinate_jobs" for _schema, table in pairs)
```

If the suite has no `pg_db` fixture name, use the existing Postgres fixture from `conftest.py` (same as other admin storage tests).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_admin_storage.py::test_fetch_table_sizes_includes_app_or_intel -q`

Expected: FAIL (`api_call_events` missing because query is `nspname = 'public'`).

- [ ] **Step 3: Implement sizes query**

Replace `_TABLE_SIZES_PG` in `backend/storage_metrics.py` with namespaces `app` and `intel`, return `schema` + `table`. Default SQL:

```sql
SELECT n.nspname AS schema,
       c.relname AS name,
       pg_total_relation_size(c.oid)::bigint AS size_bytes
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = ANY ($1::text[])
  AND c.relkind = 'r'
ORDER BY size_bytes DESC
```

Pass `['app','intel']` by default; `include_system=True` adds `public`.

Update `_table_bytes` in `efficiency_audit.py` to match by `table` (and schema if duplicated). Storage API: merge `COUNT(*)` for the same `schema.table`. Storage UI: Rows must not be `—` for `api_call_events`. Move “Estimated growth from 10d backup trend” off the TABLE SIZES heading; keep it under backups only.

- [ ] **Step 4: Pool bar is counts**

In `ResourcesPage.jsx`, `PoolStatsCard` must not call `CapacityBar` (that function always `fmtBytes`). Render `{inUse} / {size} ({pct}%)` as integers. Sub line already has `2 in use · 3 idle · max 20`.

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_admin_storage.py tests/test_efficiency_audit.py tests/test_database_metrics.py -q`  
Run: `cd frontend && npm run test:unit`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/storage_metrics.py backend/efficiency_audit.py backend/db/database_metrics.py \
  backend/routers/admin/storage.py frontend/src/pages/admin/StoragePage.jsx \
  frontend/src/pages/admin/ResourcesPage.jsx backend/tests docs/PRODUCT_STATUS.md \
  docs/API_REFERENCE.md
git commit -m "fix(admin): size app/intel tables and stop fmtBytes on pool counts"
```

---

### Task 2: PR — open job errors vs Cleared history

**Files:**
- Modify: `backend/db/user_notifications.py`
- Modify: `backend/scheduler.py` (success path after `_write_job_last_run`)
- Modify: `backend/reports/daily_brief.py` (`_fetch_notifications` / ops)
- Test: `backend/tests/test_user_notifications.py`, `backend/tests/test_daily_brief.py`, `backend/tests/test_admin_scheduler.py`
- Docs: `docs/PRODUCT_STATUS.md` Admin / notifications row

**Interfaces:**
- Produces: `async def dismiss_job_error_notifications(db, job_id: str) -> int` — sets `dismissed_at` where `category='job_error'` AND `entity_type='job'` AND `entity_id=job_id` AND `dismissed_at IS NULL`

- [ ] **Step 1: Failing test**

```python
@pytest.mark.asyncio
async def test_dismiss_job_errors_on_success_leaves_cleared_row(db):
    # insert job_error for kev_metadata_sync
    # call dismiss_job_error_notifications(db, "kev_metadata_sync")
    # list view=inbox → empty for that job
    # list view=cleared → row present
```

Use existing `list_notifications(..., view=)` from `user_notifications.py`.

- [ ] **Step 2: Run — expect FAIL** (function missing).

- [ ] **Step 3: Implement dismiss helper; call it when `had_error` is false** after `_write_job_last_run` in `scheduler.py` (the shared wrapper around line ~217 today only emits on error — add the success dismiss next to that).

- [ ] **Step 4: Brief ops**

Change ops collection so it does **not** use in-window `created_at` for resolved jobs. Source of truth: `scheduler.last_run.*` in `sync_state` (`had_error` true) **or** undismissed `job_error` after Task 2 dismiss. Prefer last-run flags so a dismissed-but-still-failing job still shows. Deduplicate by `job_id`. Three identical KEV lines become one if only current state is failed.

Titles stay for Task 5; this PR only ops filtering.

- [ ] **Step 5: Tests + commit**

```bash
git commit -m "fix(notify): auto-clear open job_error into Cleared when job succeeds"
```

---

### Task 3: PR — stack honesty

**Files:** `frontend/src/App.jsx` (remove seed `useEffect` at the `getSavedStack` / `briefr-stack-loaded` block), `frontend/src/components/filterBarStackPersistGate.test.js`, `backend/preferences/repo.py`, `backend/db/sync_state.py`, `backend/config_schema.py`, `backend/.env.example`, `backend/tests/test_me_stack.py`, `backend/tests/test_wallboard.py`, `backend/tests/test_detection_backlog.py`

**Interfaces:**
- FEED `filters.stack` initial `''` and **must not** be set from `getSavedStack()` on load.
- `get_operator_stack_assets`: My Stack only after migrate.
- One-time migrate: persist `sync_state` key `stack_terms_env_migrated`. Copy non-empty `BRIEFR_STACK_TERMS` into admin My Stack only when that marker is unset **and** both `stack_terms` and profile-derived assets are empty. Set the marker even when copy is skipped. After the operator clears My Stack, a reload must not copy env again.

- [ ] Write frontend unit: load App seed helper or extract `applyLoadedStackToFeedFilters` and assert it is **not** called from App (gate test: `App.jsx` must not match `setFilters((prev) => (prev.stack ? prev : { ...prev, stack:`).

- [ ] Sequence test: env set + empty My Stack → terms copied once; operator clears My Stack; reload leaves stack empty (marker prevents remigration). Flip `test_effective_stack_terms_prefers_env` to “env does not match after migrate”.

- [ ] Commit: `fix(stack): do not seed FEED from My Stack; retire env keyword matching`

---

### Task 4: PR — headlines cleanup

**Files:** `backend/feeds/incident_news.py`, `frontend/src/components/advisories/shared.jsx`, `backend/tests/test_incident_news.py`

```python
EXCLUDED_NEWS_TITLE_PATTERNS = [
    re.compile(r"name that toon", re.I),
    re.compile(r"\[virtual event\]", re.I),
    re.compile(r"\bwebinar\b", re.I),
    re.compile(r"\bregister now\b", re.I),
]
```

When building the item dict, if `description == title` after fallback, set `description` to `""`. `FeedCard`: if `!card.description` or description equals title, do not render `<p className="cs-card-desc">`.

- [ ] Tests for `[Virtual Event] Building a Secure AI Strategy` excluded; duplicate subtitle not rendered (frontend test on a small helper `shouldShowFeedDescription(title, description)` in `shared.jsx` export).

- [ ] Commit: `fix(intel): drop virtual-event headlines and cloned titles`

---

### Task 5: PR — daily brief copy (EOD + morning)

**Files:** `backend/reports/daily_brief.py`, `backend/reports/market_clusters.py`, `backend/db/software_catalog.py` (read-only lookup), `docs/design/daily-brief-format.md`, `backend/tests/test_daily_brief.py`, `backend/tests/test_market_clusters.py`

**Interfaces:**
- `slot_title`: `"EOD report"` / `"Morning report"`
- `template_headline`: max three short sentences; no single run-on lede
- Product label: `display_name_for(vendor, product, software_catalog.title)` so catalog `title` wins; if no title, `display_name_for(vendor, product)` or the raw vendor/product key. Never invent a brand.
- Embed: one severity field; morning omits products section when `slot=="standup"` if character budget tight (spec: morning = glance + stack + kev + open ops)

Depends on Task 2 for ops. If Task 5 lands first, still filter ops to last-run failures.

- [ ] Commit: `fix(brief): human titles, catalog product names, one severity field`

---

### Task 6: PR — DETECT framing + Related type

**Files:** `frontend/src/components/DetailDrawer/DetectTab.jsx`, `frontend/src/components/DetailDrawer/RelatedTab.jsx`, `frontend/src/components/DetailDrawer.css`, `frontend/src/utils/detectLabels.js`, `frontend/src/utils/detectLabels.test.js`

- Show `.det-framing-note` DRL paragraph only when `hasCommunity`.
- Else use existing empty/template strings from `detectLabels.js` (add `templateFallbackFraming()` if missing).
- CSS: `.drawer-related-sev`, `.drawer-related-sim` → `font-size: var(--type-micro)`; `.drawer-related-desc` → `var(--type-body)`; `.drawer-related-cvss` without `margin-left: auto` — use `margin-left: auto` on a trailing cluster wrapping CVSS+sim, or grid columns `id | sev | sim` so UNKNOWN does not wrap uniquely.

- [ ] Frontend unit: `detectLabels` framing helper.
- [ ] Commit: `fix(drawer): honest Detect fallback copy and Related type floor`

---

### Task 7: PR — Resources 2-column layout

**Files:** `frontend/src/pages/admin/ResourcesPage.jsx`, `frontend/src/pages/AdminPage.css`

Wrap `chartSections` in `admin-two-col` at `min-width: 901px` (existing breakpoint). Host capacity + pool as two children of one `admin-two-col`. Do this **after** Task 1 so operators are not rearranging false numbers.

- [ ] No visual regression of `fmtBytes` on pool.
- [ ] Commit: `fix(admin): denser Resources chart grid`

---

### Task 8: PR — ENV webhook Delete

**Files:** `backend/routers/admin/webhooks.py`, `backend/webhooks/destinations.py`, `frontend/src/pages/admin/WebhookDestinationCard.jsx`, `backend/tests/test_webhooks_destinations_crud.py`, `docs/API_REFERENCE.md`

**Interfaces:**
- DELETE `/api/admin/webhooks/destinations/discord` with `confirm_text=delete` **allowed**.
- Implementation: clear config keys `DISCORD_WEBHOOK_URL`, `DISCORD_WEBHOOK_ENABLED` via existing admin config apply helper (same path as API keys page — do not write `.env` if product no longer writes files). Delete DB row even when process env would 409. `load_env_destinations` returns None when URL empty.
- If `os.environ.get("DISCORD_WEBHOOK_URL")` is still set **after** those writes: return 409 with the unset-process-environment message. Do **not** preflight-skip writes — the operator asked to delete persisted state; process env can still rebuild a live card until those keys are unset (that is the 409).
- Show Delete on env cards.

- [ ] Test: delete reserved id when URL only in DB config succeeds; 409 when process env set **and** the destination row is already gone.
- [ ] Commit: `fix(webhooks): allow deleting env Discord bootstrap`

---

## PR order (do not parallelize 2+5 ops, or 1+7 layout)

1. Task 1 (false bytes)  
2. Task 2 (bell/brief health)  
3. Task 3 (stack)  
4. Task 4 (headlines)  
5. Task 5 (brief UX)  
6. Task 6 (drawer)  
7. Task 7 (Resources grid)  
8. Task 8 (webhook delete)

Shared: `daily_brief.py` in 2 then 5 — sequential. `ResourcesPage.jsx` in 1 then 7 — sequential. `destinations.py` only in 8.

## Self-review

- Spec items 1–9 each have a task (1→T4, 2→T2+T5, 3→T1, 4→T7, 5→T3, 6→T5, 7→T8, 8→T6, 9→T6).
- No TBD. Test snippets for T1–T2; T3–T8 name files, assertions, and commits.
- `dismiss_job_error_notifications` is the name Task 5 ops must not contradict.

## Reviews that do not apply to this docs PR

`/review-bugbot` and `/review-security` review **code diffs**. This branch is spec+plan only. Run both on **Task 1’s implementation branch**, not on #752 and not on this plan PR.
