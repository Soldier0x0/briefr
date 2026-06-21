# Admin Panel — Analyst / Operator Mode

**Status:** Implementation spec (ready for Claude Code)  
**Last updated:** 2026-06-21  
**Audience:** Claude Code (Sonnet 4.6 primary implementer; Opus 4.6 advisor on ambiguity)  
**Scope:** Frontend-only for v1 — no new backend endpoints required

---

## How to use this document (Claude Code)

1. **Read this file end-to-end** before writing code.
2. **Also read** (in order):
   - `PRODUCT.md` — Design Principles 1–3 (visible meaning, analyst-understandable UI)
   - `docs/AGENT_IMPLEMENTATION_GUIDE.md` — product truth, release discipline
   - `docs/HANDOVER.md` §7 — per-PR workflow, tests, branch naming
   - `frontend/src/pages/admin/` — current admin sub-app
   - `frontend/src/utils/displayPrefs.js` — localStorage prefs pattern to mirror
3. **Models:** Use **Claude Sonnet 4.6** for implementation. Escalate to **Claude Opus 4.6** only when:
   - Analyst vs operator boundary for a page is ambiguous
   - Deriving `overall` intel health from `GET /api/admin/system` needs a judgment call
   - CSS/layout trade-offs between mockup inspiration and existing `AdminPage.css` tokens
4. **Do not** invent features outside this spec. **Do not** remove operator capabilities.
5. **Branch:** `cursor/admin-analyst-operator-mode-<suffix>` off fresh `main`.
6. **Before PR:** `cd frontend && npm run build` and `cd backend && pytest tests/ -q`.

There is no repo skills folder. Treat `PRODUCT.md` + this document as the product guardrails.

---

## 1. Problem statement

The BRIEFR admin panel (`/admin`) is **operationally complete** but **analyst-ROI is low**:

- Exposes implementation language: `nvd_incremental_sync`, `LOCKED`, `integrity_check`, `open circuits`, `JOB ID`
- Dangerous actions (restart, full ingest, purge) visible to everyone
- Overview is an operator dashboard (DB integrity, active locks, 9-column scheduler table)

An analyst who did not write the code cannot easily answer:

- What is an integrity check?
- What does locked mean?
- What should I do when something is red?

**Success criterion** (from `PRODUCT.md`):

> An analyst trusts the data enough to act on it fast, and an operator can run the box without reading the source code to understand what a button does.

This spec adds a **soft Analyst / Operator toggle** and plain-language layers — not a replacement of operator tooling.

---

## 2. UI inspiration vs separation of concerns

Two reference UIs were discussed. **Visual inspiration** comes from the compact mockup; **feature separation** comes from the analyst/operator architecture we designed. They are related but not identical.

### 2.1 Mockup reference (“Image 1” — visual north star for Analyst)

Characteristics to **borrow**:

| Pattern | Mockup behavior | Apply in Analyst mode |
|---------|-----------------|------------------------|
| Card rhythm | Large number + muted subtitle explaining context | Every KPI card gets a secondary line |
| Top bar | Few outcome pills; one alert when something is wrong | 3–4 pills max; highlight worst issue |
| Scheduler | Slim 3-column table (Source / Last run / Next run) | No JOB ID, no Pause/Run in analyst view |
| Nav | Short sidebar; badge on item with issues | `ANALYST_NAV` only; badge on Source status |
| Chrome | No restart / full ingest in header | Analyst status bar is read-only + safe refresh |
| Subtitle | “Live snapshot — polls every 30s” | Set polling expectation on Intel status page |

Example mockup card subtitles (target copy style):

- CVE count: `7,041` → `+38 last 24h`
- NVD sync: `14m` → `ago · incremental`
- Backup: `9h` → `ago · threshold 12h`
- DB: `ok` → `checked on startup`
- Circuits: `1` → `sploitus · 60s cooldown`

**Plain-language overrides** (our catalog wins over mockup jargon):

| Mockup term | Analyst term |
|-------------|----------------|
| DB integrity | **Database health** |
| Open circuits | **Sources with issues** |
| Sploitus circuit open | **Sploitus unavailable** (with one-line explanation) |
| NVD incremental | **NIST CVE feed** (catalog label) |

### 2.2 Current admin (“Image 2” — Operator baseline)

Retain as **Operator mode** with polish:

- Full sidebar (14 pages)
- Status bar: metrics + Discord/Telegram + Run full ingest + Restart
- Overview: 6 stat cards, diagnostics, active locks, recent errors, full JobTable
- JOB ID column — hidden behind “Show technical IDs” toggle (collapsed default)

**Do not** dumb down Operator mode. Improve labels via `catalog.js`.

---

## 3. Solution architecture

### 3.1 Mode toggle

| Property | Value |
|----------|--------|
| Location | `StatusBar.jsx` — left side, before metrics |
| Control | Segmented toggle: **Analyst** \| **Operator** |
| Default | `analyst` |
| Persistence | `localStorage` key `briefr-admin-mode` (`analyst` \| `operator`) |
| Pattern | Mirror `frontend/src/utils/displayPrefs.js` (wrap all `localStorage` access in `try…catch` so private browsing / sandboxed iframes cannot crash the panel) → new `frontend/src/utils/adminMode.js` |
| Plumbing | `AdminPage.jsx` holds mode state; pass `mode` to StatusBar, Sidebar, all pages |

**Redirect guard:** If user is on an operator-only page and switches to Analyst → `setPage('overview')`.

**Optional (implement if low effort):**

- First-visit dismissible callout: explains two modes (`localStorage` `briefr-admin-mode-hint-dismissed`)
- First switch to Operator: lightweight acknowledgment modal (destructive actions exist) — friction only, no new auth

### 3.2 Display catalog (implement first)

**New file:** `frontend/src/pages/admin/catalog.js` — single source of truth for human labels.

Extend existing patterns:

- `formatters.js` → `SOURCE_DISPLAY` / `sourceLabel()`
- `constants.js` → `MANUAL_PIPELINES`
- `backend/scheduler.py` → `add_job(..., name=...)`
- `backend/config_schema.py` → `help_text` (do not duplicate env keys in catalog; reference help text for operator config UI)

#### JOB_CATALOG (required entries)

Every scheduler job id from `_JOB_LOCK_MAP` in `backend/routers/admin.py` and all `scheduler.add_job` ids:

```javascript
// Shape per job
{
  label: 'NIST vulnerability database',      // analyst primary
  short: 'NVD',                               // compact
  operatorName: 'NVD Incremental Sync',       // matches scheduler name= where possible
  analystDescription: 'New and updated CVEs from NIST.',
  refreshButton: 'Refresh NVD',
  // optional: expectedIntervalHint for subtitles
}
```

**Export helpers:** `jobLabel(id, mode)`, `jobShort(id)`, `jobRefreshLabel(id)`.

Minimum job ids to cover:

- `nvd_incremental_sync`
- `kev_metadata_sync`
- `epss_score_sync`
- `weekly_mitre_refresh`
- `otx_nightly_correlation`
- `incident_feed_refresh`
- `nightly_correlation`
- `vulnrichment_snapshot_sync`
- `cvelistv5_incremental_sync`
- `embeddings_backfill`
- `llm_product_extraction`
- `exploit_sources_sync`
- `backup_deadman_check` (if exposed in scheduler list)

#### STATUS_CATALOG

| Code | Analyst label | Operator label | Visible hint (not hover-only) |
|------|---------------|----------------|----------------------------|
| ACTIVE | Scheduled | ACTIVE | Runs automatically on its timer |
| PAUSED | Paused | PAUSED | Will not run until resumed |
| LOCKED | **Updating** | RUNNING | Sync in progress — avoid restarting the server |
| DISABLED | Turned off | DISABLED | Disabled in configuration |

**Analyst mode must never show the word LOCKED.**

#### AUDIT_ACTION_LABELS (operator audit log)

Map `refresh.nvd`, `backup.run`, `scheduler.pause`, etc. to plain English.

#### TERM_GLOSSARY

| Key | Analyst | Operator | Explanation (for HelpTip) |
|-----|---------|----------|---------------------------|
| db_integrity | Database health | DB integrity | Checks whether the database **file** is corrupted — not whether CVE data is accurate |
| open_circuits | Sources with issues | Open circuits | Upstream API failed repeatedly; BRIEFR paused calls temporarily |
| active_locks | Syncs in progress | Active locks | A background refresh is running right now |
| circuit_reset | Try again | Reset circuit | Clears the pause and retries the source |

**Rule:** No raw `snake_case` job ids in analyst-visible UI, toasts, or lock lists.

### 3.3 Navigation

**`constants.js`** — two configs:

#### ANALYST_NAV

```
INTEL
  overview      → Intel status
  feedhealth    → Source status        (badge: open_circuit_count)
  alerts        → Alert channels       (new slim page)

YOUR DATA
  watchlist     → Pinned CVEs

PREFERENCES
  display       → Display
```

Footer link in sidebar: *“Backups, config, logs → switch to Operator view”*

#### OPERATOR_NAV

Existing `NAV` array. Optional section renames:

| Current | Operator rename |
|---------|-------------------|
| OVERVIEW | System |
| DATA | Data & storage |
| CONFIGURATION | Configuration |
| OBSERVABILITY | Monitoring |
| AUDIT | Audit |

Analyst sidebar legend (replace operator STATUS_LEGEND):

- **Current** — data is fresh
- **Delayed** — older than expected
- **Updating** — sync in progress

---

## 4. Page-by-page specification

### 4.1 Intel status (`overview`) — Analyst view

**Inspired by mockup layout; content from our analyst architecture.**

**Title:** Intel status  
**Subtitle:** Live snapshot — refreshes every 30 seconds

#### Section A — Overall banner (derive from `GET /api/admin/system`)

Traffic light summary (one line):

| State | When | Copy example |
|-------|------|----------------|
| Green | NVD fresh, no open circuits, no job errors, incidents not stale | **Intel looks current** — all sources are within expected windows |
| Amber | One of: NVD aged, 1 circuit open, incidents stale | **Some sources are delayed** — see details below |
| Red | Multiple failures or DB integrity failed | **Intel may be unreliable** — see details below |

#### Section B — Five-card grid (mockup rhythm)

| Card | Primary | Subtitle (required) | Show in analyst? |
|------|---------|---------------------|------------------|
| CVEs in database | `cve_count` | See §5.1 for `+N last 24h` | Always |
| NIST CVE feed | `fmtAge(last_nvd_sync_age_seconds)` | `usually every {NVD_SYNC_INTERVAL_HOURS}h · incremental` | Always |
| Last backup | `fmtAge(last_backup_age_seconds)` | `threshold {backup_threshold_seconds}` converted to hours | **Only if** `last_backup_age_seconds != null` (matches `StatusBar.jsx`; no `backup_enabled` on the system payload today — add later if needed); see §5.2 |
| Database health | Healthy / Problem | `checked on startup` or `run health check in Operator view` | Always; red callout if `db_integrity.ok === false` |
| Sources with issues | `open_circuit_count` or “All OK” | Name worst source + cooldown if available from `feeds.sources` | Always |

Use `ageColor()` thresholds already in `formatters.js` for green/amber/red values.

#### Section C — Per-source rows (optional table OR cards)

Mockup-style **3-column table**:

| Source | Last updated | Next update |
|--------|--------------|-------------|

Populate from `scheduler_jobs` merged with catalog labels. Status column optional as badge: Current / Delayed / Updating / Paused.

**Safe action:** Per-row **Refresh** button only when stale or on user request → `POST /api/admin/scheduler/run`.

**No** Pause, **no** JOB ID, **no** duration/records columns in analyst view.

#### Section D — Syncs in progress (conditional)

Only when `active_locks.length > 0`:

> **Background sync in progress**  
> {jobLabel} — started recently.  
> Wait before restarting the server.

#### Section E — Problems (conditional)

Only when issues exist. Template:

> **{sourceLabel} temporarily unavailable**  
> Too many failed requests. BRIEFR paused calls to avoid hammering the API.  
> [Try again] · [Operator view for details]

#### Section F — Connection status (read-only)

From masked `GET /api/admin/config`:

| Integration | Status |
|-------------|--------|
| NIST (NVD) | Key configured / Not configured |
| VirusTotal | … |
| Discord alerts | … |

Link: *Configure in Operator view → API keys*

#### Analyst overview must NOT include

- Quick diagnostics (smoke / integrity buttons)
- Active locks panel with JOB ID table
- Recent errors panel with raw ids
- Full 9-column JobTable
- Run full ingest / Restart

### 4.2 Intel status — Operator view

Keep current `OverviewPage.jsx` structure with these improvements:

- Apply catalog labels in JobTable and lock lists
- Rename stat card `DB INTEGRITY` → `DB INTEGRITY` (operator OK) but add HelpTip with glossary text
- Rename `OPEN CIRCUITS` subtitle to show source names when count > 0
- JOB ID behind toggle (see JobTable)

### 4.3 Source status (`feedhealth`)

| | Analyst | Operator |
|---|---------|----------|
| Page title | Source status | Feed health |
| “Open circuits” heading | Sources temporarily paused | Open circuits |
| Badge CLOSED | Healthy | CLOSED |
| Button | Try again | Reset circuit |

Accept `mode` prop; reuse existing `FeedCard` with label overrides.

### 4.4 Alert channels (`alerts`) — NEW page

Slim slice of `WebhooksPage.jsx`:

- Which channels configured (Discord, Telegram) — pills
- Test delivery buttons
- Read-only; no delivery log table in analyst mode
- Copy: *“To change URLs or tokens, switch to Operator view → Webhooks / API keys”*

### 4.5 Pinned CVEs (`watchlist`) — Analyst simplified

| | Analyst | Operator |
|---|---------|----------|
| Title | Pinned CVEs | Watchlist & cache |
| Subtabs | Watchlist only (pins) | watchlist + IOC cache + hunt packs |
| Danger zone | Hidden | Visible |

### 4.6 Display (`display`)

Unchanged in both modes.

### 4.7 Operator-only pages (hidden from analyst nav)

| Page | Notes |
|------|-------|
| backups | Unchanged |
| storage | Unchanged |
| database | Unchanged |
| apikeys | Show `help_text` as primary label; env key monospace secondary |
| scheduler | Title: **Data refresh schedule**; filter LOCKED → RUNNING |
| webhooks | Full page |
| security | Unchanged |
| ingestlog | Unchanged |
| auditlog | Use AUDIT_ACTION_LABELS; filter chips: “Refreshes” not `refresh.*` |
| coming-soon | Operator only |

---

## 5. Discussion points & recommended decisions

Implement per **Recommendation** unless the operator overrides later.

### 5.1 CVE “+N last 24h” subtitle (mockup parity)

**Question:** Mockup shows `+38 last 24h` under CVE count. No field on `GET /api/admin/system` today.

| Option | Effort | Recommendation |
|--------|--------|----------------|
| A. Omit subtitle in v1 | None | **Ship v1 without it** |
| B. Add backend field `cves_added_24h` to `/api/admin/system` | Small backend change | v2 if mockup parity matters |
| C. Frontend calls existing stats endpoint if one exists | Investigate first | Only if zero backend change |

**Decision:** **Option A for v1.** Card shows count only; subtitle: `CVEs stored locally`.

### 5.2 Backup card in analyst view

**Question:** Do analysts need backup age?

| Option | Recommendation |
|--------|----------------|
| Always show | No — confuses analysts |
| Hide unless amber/red | **Yes** |
| Never show | Too hidden for solo operator-analyst |

**Decision:** Show the card **only when** `last_backup_age_seconds != null` (same gate as `StatusBar.jsx` — the backend omits age when backups are disabled or `BACKUP_DIR` is unset). Within that, prefer showing when `last_backup_age_seconds > backup_threshold_seconds * 0.75` (warning) or backup is missing/stale. Subtitle explains threshold. Otherwise omit card (grid becomes 4 cards).

### 5.3 Slim scheduler table in analyst view

**Question:** Mockup has 3-column schedule table. Alternative: cards only.

**Decision:** **Include slim table** (mockup-inspired) for these **6 job ids only**:

- `nvd_incremental_sync`
- `kev_metadata_sync`
- `epss_score_sync`
- `weekly_mitre_refresh`
- `incident_feed_refresh`
- `nightly_correlation`

**Hide** all other scheduler jobs from the analyst table unless they have a recent error (`last_run_had_error === true`), e.g. `embeddings_backfill`, `llm_product_extraction`, `exploit_sources_sync`, `otx_nightly_correlation`, `vulnrichment_snapshot_sync`, `cvelistv5_incremental_sync`, `backup_deadman_check`.

Export a constant in `intelStatus.js` or `catalog.js`, e.g. `ANALYST_SCHEDULE_TABLE_JOB_IDS`, so Claude Code does not guess filter logic.

### 5.4 Top bar alert pill

**Question:** Always show worst issue vs only when non-green?

**Decision:** **Only when non-green.** Analyst status bar: CVE count, NVD age, sources-with-issues count (not the word “circuits”). Single amber/red pill: e.g. `Sploitus unavailable`.

### 5.5 Visual parity with mockup

**Question:** New card CSS vs existing `AdminPage.css` tokens?

**Decision:** **Reuse existing tokens** (`admin-card`, `stat-card-row`, `StatCard.jsx`) but add:

- `.stat-card-subtitle` for muted secondary line
- `.intel-banner` for traffic-light summary
- `.admin-mode-toggle` for segmented control

Do not introduce a new design system or light theme.

### 5.6 Operator acknowledgment modal

**Decision:** **Implement** — one-time `localStorage` flag `briefr-operator-ack`.

### 5.7 Main app stale banner (bridge)

**Question:** Banner on main FEED when intel stale → link to `/admin`?

**Decision:** **Out of scope v1** — document as follow-up in PR description. Optional v1.1.

### 5.8 URL param `?mode=operator`

**Decision:** **Out of scope v1.** localStorage only.

### 5.9 Backend `analyst_summary` endpoint

**Decision:** **Frontend derivation v1.** Opus may advise on fragile logic; prefer pure functions in `frontend/src/pages/admin/intelStatus.js` (new helper module).

---

## 6. Status bar specification

### 6.1 Analyst status bar

```
[ Analyst ● | Operator ]   CVEs {n}   NVD {age}   [if issues] {worst source} unavailable
                                                      [Refresh all sources]
```

| Show | Hide |
|------|------|
| Mode toggle | Git commit |
| CVE count | Discord/Telegram pills |
| NVD sync age | Backup age (unless critical — see §5.2) |
| Worst-issue pill when `open_circuit_count > 0` | Run full ingest |
| **Refresh all sources** → `POST /api/refresh` with manual `X-BRIEFR-Admin-Key` (`getAdminKey()`, same as `handleRunIngest`) | Restart now / drain |

### 6.2 Operator status bar

Current `StatusBar.jsx` plus catalog label tweaks. Keep all actions.

---

## 7. Shared components

### 7.1 `JobTable.jsx`

| | Analyst | Operator |
|---|---------|----------|
| JOB ID column | Hidden | Behind “Show technical IDs” toggle (default off) |
| NAME column | Uses `jobLabel(id, 'analyst')` | Uses `jobLabel(id, 'operator')` |
| STATUS | STATUS_CATALOG analyst labels | Operator labels |
| RECORDS / DURATION | Hidden | Visible |
| Actions Run/Pause | Hidden | Visible |

### 7.2 `JobStatusBadge.jsx`

Use STATUS_CATALOG; render visible hint below badge in analyst mode (not title-only).

### 7.3 `HelpTip.jsx` (new, small)

Reusable `?` / `ⓘ` trigger button/icon. Use React’s `useId()` to generate a unique id for the tooltip/description element and associate it with the trigger via `aria-describedby` (avoids id collisions when multiple HelpTips render on one page). Use on: database health, sources paused, circuit breaker.

### 7.4 Toasts

Never: `Job started: nvd_incremental_sync`  
Always: `NVD sync started` (via catalog)

---

## 8. Plain-language rename table (complete)

| Technical | Analyst | Operator |
|-----------|---------|----------|
| System health | Intel status | System health |
| Feed health | Source status | Feed health |
| Scheduler | (hidden) | Data refresh schedule |
| Storage | (hidden) | Storage |
| LOCKED | Updating | RUNNING |
| Open circuits | Sources with issues | Open circuits |
| DB integrity | Database health | DB integrity |
| Active locks | Syncs in progress | Active locks |
| Run full ingest | Refresh everything | Run full ingest |
| Reset circuit | Try again | Reset circuit |
| Jobs with errors | Sync problems | Jobs with errors |
| Quick diagnostics | (hidden) | Quick diagnostics |

---

## 9. Implementation phases

Split into **up to 3 PRs** or one PR with logical commits.

### Phase 1 — Foundation (required first)

- [ ] `adminMode.js` + toggle in StatusBar
- [ ] `catalog.js` with all job ids and STATUS_CATALOG
- [ ] `ANALYST_NAV` / `OPERATOR_NAV` in constants.js
- [ ] Sidebar + page filtering + redirect guard
- [ ] `mode` prop plumbing through AdminPage
- [ ] JobTable / JobStatusBadge use catalog (both modes)

### Phase 2 — Analyst experience

- [ ] `intelStatus.js` — derive overall health + worst issue from system payload
- [ ] Analyst Overview layout (banner + cards + slim table + conditional sections)
- [ ] Analyst StatusBar variant
- [ ] `AlertsPage.jsx`
- [ ] FeedHealth + Watchlist mode props

### Phase 3 — Polish

- [ ] Operator Overview + Scheduler + Audit label polish
- [ ] HelpTip component
- [ ] First-visit callout + operator acknowledgment modal
- [ ] `ONBOARDING.md` admin UI table update (brief)

---

## 10. Files to create or modify

### New files

| Path | Purpose |
|------|---------|
| `frontend/src/utils/adminMode.js` | Mode persistence |
| `frontend/src/pages/admin/catalog.js` | Display catalog |
| `frontend/src/pages/admin/intelStatus.js` | Health derivation helpers |
| `frontend/src/pages/admin/AlertsPage.jsx` | Analyst alerts slice |
| `frontend/src/pages/admin/shared/HelpTip.jsx` | Inline explanations |

### Modify

| Path | Changes |
|------|---------|
| `frontend/src/pages/admin/AdminPage.jsx` | Mode state, Alerts page, pass mode |
| `frontend/src/pages/admin/StatusBar.jsx` | Toggle + analyst variant |
| `frontend/src/pages/admin/Sidebar.jsx` | NAV by mode, legend by mode |
| `frontend/src/pages/admin/constants.js` | ANALYST_NAV, OPERATOR_NAV |
| `frontend/src/pages/admin/OverviewPage.jsx` | Split layout by mode |
| `frontend/src/pages/admin/shared/JobTable.jsx` | Mode-aware columns/labels |
| `frontend/src/pages/admin/FeedHealthPage.jsx` | Mode prop |
| `frontend/src/pages/admin/WatchlistPage.jsx` | Mode prop |
| `frontend/src/pages/admin/AuditLogPage.jsx` | Action labels |
| `frontend/src/pages/admin/SchedulerPage.jsx` | Operator labels |
| `frontend/src/pages/admin/AdminPage.css` | Toggle, subtitles, banner |

### Do not modify (v1)

- Backend routers / API shapes
- `SYSTEM_DESIGN.md` (no runtime API change)
- Main app `App.jsx` (stale banner is follow-up)

---

## 11. Data sources (no new APIs v1)

All analyst UI derives from existing endpoints:

| Endpoint | Used for |
|----------|----------|
| `GET /api/admin/system` | Counts, ages, integrity, scheduler_jobs, active_locks, feeds, circuits |
| `GET /api/admin/config` | Masked key status (connection card) |
| `POST /api/admin/scheduler/run` | Per-source refresh |
| `POST /api/refresh` | Refresh all sources — **not** behind `adminApi`; pass `X-BRIEFR-Admin-Key` manually via `getAdminKey()` (see `handleRunIngest` in `AdminPage.jsx`) |
| `POST /api/admin/feeds/{id}/reset-circuit` | Try again |

Key `system` fields: `cve_count`, `last_nvd_sync_age_seconds`, `last_backup_age_seconds`, `backup_threshold_seconds`, `db_integrity`, `open_circuit_count`, `feeds.sources`, `feeds.incidents`, `scheduler_jobs`, `active_locks`, `recent_errors`, `jobs_with_errors_count`, `refresh_in_progress`.

---

## 12. Testing & acceptance

### Commands

```bash
cd frontend && npm run build
cd ../backend && pytest tests/ -q
```

### Manual checklist

1. `/admin` opens in **Analyst** mode by default
2. Toggle to Operator — full nav + restart/ingest appear
3. On `scheduler` page, switch to Analyst — redirects to `overview`
4. Analyst overview: no `snake_case` job ids visible
5. LOCKED never shown to analysts — “Updating” instead
6. Refresh NVD works; toast uses human label
7. `active_locks` during sync → “Syncs in progress” with human names
8. Operator JobTable: technical IDs toggle works
9. Mode persists across reload
10. Admin API key gate still works
11. `npm run build` passes; pytest passes

### Acceptance criteria (all required)

- [ ] Analyst / Operator toggle on all admin pages
- [ ] Default Analyst; persisted in localStorage
- [ ] Analyst nav ≤ 5 destinations; operator full nav
- [ ] Analyst cannot reach restart, full ingest, purge, migrate without switching mode
- [ ] `catalog.js` is SSOT for job/status labels
- [ ] Analyst Overview uses mockup-inspired card subtitles + slim schedule table
- [ ] PRODUCT.md principles 1 & 3 satisfied (purpose subtitles + discoverable status meaning)
- [ ] WCAG: focus-visible on toggle; `prefers-reduced-motion` respected
- [ ] No new npm dependencies

---

## 13. PR template snippet

```markdown
## Summary
Admin panel Analyst/Operator mode with plain-language catalog and mockup-inspired Intel status view.

## Post-merge verification
1. Open https://<host>/admin — confirm Analyst mode default
2. Toggle Operator — confirm Restart + full sidebar
3. Trigger NVD refresh from Analyst overview — confirm human toast
4. cd frontend && npm run build
5. cd backend && pytest tests/ -q

## Follow-ups (not in this PR)
- Main app stale-intel banner → /admin link
- CVE +N last 24h subtitle (backend field)
- URL param ?mode=operator
```

---

## 14. Copy examples (analyst)

### Healthy state

> **Intel looks current**  
> All sources synced within expected windows.

### NVD delayed

> **NIST CVE feed — delayed**  
> Last updated 4 hours ago (usually every 1 hour). New CVEs may be missing.  
> [Refresh NVD]

### Sync in progress

> **Background sync in progress**  
> NIST CVE feed — updating. Wait before restarting the server.

### Source paused

> **Sploitus temporarily unavailable**  
> Too many failed requests. BRIEFR will retry automatically (about 60 seconds).  
> [Try again] · [Operator view for details]

### Database problem

> **Database health — problem detected**  
> The database file may be damaged. Contact whoever manages this server, or switch to Operator view → Backups.

---

## 15. Opus advisor prompts (when stuck)

Use Opus 4.6 read-only review on:

1. *“Given this `system` JSON, is the amber vs red logic in `intelStatus.js` correct?”*
2. *“Should embeddings_backfill appear in analyst schedule table when status is ACTIVE and no errors?”* → **No** (per §5.3)
3. *“Does this HelpTip copy violate PRODUCT.md density principle?”*

Sonnet implements; Opus reviews edge cases. Do not split into two implementing agents.

---

## 16. Non-goals (explicit)

- Light / SaaS theme mode
- New backend endpoints (v1)
- Multi-user / RBAC
- Removing operator pages or features
- Rewriting admin CSS from scratch
- Playwright tests in v1 (manual checklist sufficient; add smoke later if requested)

---

*End of spec. Implement Phases 1 → 2 → 3 in order.*
