# BRIEFR UI/UX Overhaul Plan

> Load this file in a fresh Claude Code session and say "implement this plan" —
> it should start working directly. Each section is independently shippable;
> do them in the listed order. Verify with the running dev servers + Playwright
> screenshots before/after each change (servers: `cd backend && uvicorn main:app
> --port 8000`, `cd frontend && npm run dev` on :5173). No section here has been
> implemented yet — this is a plan only.

## Context

Two audit passes (main app + admin panel) against a UI/UX checklist (a11y,
touch targets, performance, style, layout, typography, animation, forms,
navigation, charts) plus live Playwright verification surfaced concrete,
confirmed issues below. Everything here is measured, not guessed — see
inline evidence.

---

## 1. Quick, verified-safe fixes (main app) — do these first, low risk

### 1a. Focus-indicator contrast (WCAG 2.4.7)
Every text input uses `outline: none` + a border-color change on focus as the
visible indicator. Measured actual contrast ratios:

| File | Current focus color change | Contrast ratio | Verdict |
|---|---|---|---|
| `App.css:127` (generic `input, textarea`) | `--border` → `--border-strong` | 1.32:1 | FAIL — fix |
| `Header.css:280` (`.tz-search`) | `--border` → `--border2` | 1.14:1 | FAIL — fix |
| `IOCLookup.css:117` (`.ioc-value-input`) | `--border` → `--border2` | 1.14:1 | FAIL — fix |
| `PdfExportModal.css:65` (`.pdf-modal-input`) | `--border` → `--border2` | 1.14:1 | FAIL — fix |
| `DigestModal.css:87` (`.digest-textarea`) | none at all | n/a | FAIL — fix (add one) |
| `CaseStudies.css:54` | `--border` → `--accent` | 7.33:1 | OK, leave alone |
| `AdminPage.css:387,400` | `--border` → `--red` | 3.97:1 | OK, leave alone |
| `CVECard.css:47` (`.cve-nav-selected`) | not an input; separate `:focus-visible` rule exists elsewhere in same file | n/a | OK, leave alone |

**Fix:** change the 4 failing `:focus` border-color targets to `var(--accent)`
(already proven at 7.33:1 in CaseStudies.css) and add an equivalent rule to
`.digest-textarea:focus`. Zero layout impact — pure color swap.

### 1b. CVE card share button touch target
`CVECard.css:131-141` — `.card-share-btn` is 18×18px with 2px/4px padding.
Measured live: 34px of real horizontal clearance exists between the share
button and the CVSS badge (`right: 8px` to `right: 60px`), so it can grow
toward 32-38px safely. Also: it's only visible on `:hover` (`.cve-card:hover
.card-share-wrap { opacity: 1 }`, `CVECard.css:127`) with **no
`:focus-within` and no `@media (hover: none)` fallback** — on touch devices
it is present in the DOM, clickable, but never visibly shown. This is worse
than "too small."

**Fix:**
- Increase `.card-share-btn` padding (target ~32-38px hit area, verified
  headroom allows it).
- Add `.cve-card:focus-within .card-share-wrap { opacity: 1 }` so keyboard
  Tab reveals it.
- Add `@media (hover: none) { .card-share-wrap { opacity: 1 } }` so touch
  devices always show it (purely additive, zero desktop impact).

### 1c. Font-size floor
`App.css:269-293,321` and others use 9-10px text. Before bumping to a 12px
floor, check each site for fixed-width containers / truncation logic that
might overflow with larger text (e.g. badge pills, monospace meta rows).
Bump where safe.

### 1d. Pre-existing React duplicate-key warning (unrelated, found incidentally)
Console shows `Encountered two children with the same key` repeated, traced
to single-letter weekday labels (S/M/T/W/T/F/S) in the 90-day heatmap
component — almost certainly keyed by the letter itself instead of index.
Find the heatmap weekday-label render and key by index or a unique id
instead. Independent bug, not part of the audit, just noticed.

---

## 2. Mobile navigation redesign (main app)

### Confirmed bug
At 390px viewport width, `<header>`'s content overflows to `scrollWidth:
1050px` against a `385px` box (`overflow-x: visible` on the header itself),
and because `body { overflow-x: hidden }` is global, that overflow is
**silently clipped and unreachable** — not small, completely gone. Profile
button, Admin link, legal-links menu, clock: none of it is reachable on a
phone today. Measured live via Playwright at 390×844.

### Recommended fix: bottom tab bar for primary nav, not a hamburger
Per nav-pattern guidance: hamburgers are wrong for primary/top-level
destinations (extra tap, kills discoverability); bottom tab bars are right
for ≤5 items, which BRIEFR has exactly (BRIEF / FEED / IOC LOOKUP /
INCIDENTS & NEWS / FORGE).

- **Primary nav → fixed bottom tab bar, mobile-only** (`@media (max-width:
  640px)`, same breakpoint convention already used for
  `.header-legal-mobile`). Active tab reuses the existing solid-fill active
  style already used on desktop (e.g. FEED tab renders as a solid orange
  block when active — reuse that exact treatment, don't invent a new one).
  Each tab ≥44×44pt. Respect safe-area: `padding-bottom:
  env(safe-area-inset-bottom)`.
- **Secondary items (Profile, Admin, About/Privacy/Terms, clock) → existing
  hamburger/dropdown.** `.mobile-menu-btn` / `.mobile-menu-dropdown` already
  exist (`Header.jsx:181-201`, currently only used for legal links) — extend
  the same dropdown to also hold Profile + Admin instead of building a new
  component.
- **Top bar on mobile** simplifies to: wordmark + LIVE indicator + overflow
  trigger only. Tagline/clock are already hidden under 640px
  (`Header.css:417,421-422`) — keep that.
- Desktop nav is **untouched** — this is purely additive markup + one new
  media-query block, following the exact pattern `.header-legal-desktop` /
  `.header-legal-mobile` already establishes in this codebase. No shared
  selector gets modified.
- Motion: tab-switch transition 150-200ms, matching the 0.1-0.2s rhythm
  already used everywhere else. `prefers-reduced-motion` already handled
  globally — inherits for free.

### Verification required before calling this done
Screenshot at 360px, 390px, 414px, and 768px-landscape via Playwright (not
just one size). Re-test with `prefers-reduced-motion` forced on. Confirm
desktop (1280px+) is pixel-identical to before.

---

## 3. Admin panel — full visual/IA pass ("SaaS dashboard" quality bar)

Current state: 7/10 functionally, but looks like an internal dev tool, not
a product. Do ALL of the below, not a subset.

### 3a. Kill the permanent warning banner
`ApiKeysPage.jsx` renders a non-dismissible amber banner about
`load_dotenv()` behavior on every page load, permanently, at full visual
weight — same color as genuinely urgent warnings elsewhere (backup overdue,
circuit open). This trains the operator to ignore amber. **Fix:** move to a
small ⓘ info icon/tooltip next to the page title, or collapse to a single
dismissible line. Reserve amber/red for things that need actual attention
right now.

### 3b. Status indicator legend — every state needs a visible meaning
Currently the admin panel shows raw state words (`LOCKED`, `ACTIVE`,
`DISABLED`, `PAUSED`, the Discord/Telegram pill colors, `DB ok`, circuit
open/closed) with **no legend anywhere** explaining what they mean. A new
analyst has no way to know `LOCKED` means "currently running, don't touch"
vs `PAUSED` meaning "won't run until resumed" vs `DISABLED` meaning
"env-gated off."

**Fix:**
- Add a persistent, small "Status legend" disclosure (collapsible, in the
  sidebar footer or as a `?` icon in the status bar) listing every status
  badge/pill color used anywhere in the panel with a one-line plain-English
  meaning. Single source of truth — one component, referenced conceptually
  everywhere, not duplicated per page.
- Every status badge gets a `title=""` tooltip with the same text, for
  in-context hover discovery without needing the legend open.
- Audit every status word currently in use across all 12 pages
  (`JobStatusBadge` in `shared/JobTable.jsx`, the Discord/Telegram pills in
  `StatusBar.jsx`, `DB ok`/`degraded`, circuit `OPEN`/`CLOSED`, backup
  `integrity` badges) and write the legend from that real inventory — don't
  guess at a list.

### 3c. Visual hierarchy
Section titles (`API KEYS`, `WEBHOOKS — DISCORD / TELEGRAM / GENERIC`, etc.)
are currently flat gray all-caps with no weight distinction from body text.
Give page titles, section titles, and field labels three distinct visual
weights (size/weight/color), consistently, across all pages — reuse
existing `--text`, `--text2`, `--text3` tokens rather than inventing new
ones.

### 3d. Status pills need actual state color
Discord/Telegram pills in `StatusBar.jsx` currently only convey "configured
or not" via a flat label with no color-coded state. Give them real
state-driven color (configured+healthy = green, configured+failing = amber,
not configured = gray) consistent with the legend from 3b.

### 3e. Contextual help for non-author analysts
Every page needs a one-line purpose statement under its `<h1>` — what this
page is for, and a rough sense of who should be touching it (e.g.
Scheduler: "Controls when each ingest job runs. Pausing a job stops it from
running automatically until resumed — safe to pause individual jobs while
debugging a feed issue."). This is distinct from the per-field help text
already built in `config_schema.py` (merge that PR — `feat/config-schema`
branch — for the per-field half of this; write the per-page half fresh).

---

## 4. Admin panel — stop reloading pages you just visited

**Root cause, confirmed in code:** `AdminPage.jsx`'s page switch is a plain
object lookup (`{ overview: <OverviewPage/>, backups: <BackupsPage/>, ... }
[page]`) — every sidebar click fully unmounts the page you're leaving and
mounts a fresh instance of the one you're entering. Switching back to a page
visited 4 seconds ago re-fetches from scratch and re-shows the loading
skeleton, every time.

**Existing precedent in this exact codebase:** the main app's tab panels
(BRIEF/FEED/IOC/etc.) deliberately stay mounted using a `hidden` attribute
specifically to preserve scroll/filter state across tab switches. The admin
panel just never got the same treatment.

**Fix:** render all (or at least recently-visited) admin pages
simultaneously, toggling visibility via the `hidden` attribute instead of
conditional mounting — matching the main app's established pattern exactly.
Each page's existing `useEffect`-on-mount fetch becomes effectively a
"fetch once, cache for the session" pattern. Watch for: pages with polling
intervals (e.g. live status) need their interval cleared/paused while
hidden, not just visually hidden, to avoid wasted background requests.

---

## 5. Admin panel — "danger zone" pattern for destructive actions

Confirm-text gating already exists (`destructive_actions.py` registry +
`ConfirmModal`) but destructive controls aren't **visually segregated**
before the user's cursor even gets near them. Storage page's purge cards
sit in a plain grid with the same visual weight as a read-only row-count
table above it.

**Fix:** introduce one consistent "danger zone" visual treatment — clearly
bordered (red-tinted border, warning icon, heading literally saying "Danger
zone — these actions cannot be undone") — and apply it everywhere a
destructive action lives:
- Storage page's purge cards
- Watchlist's clear-snoozes / clear-all-IOC-cache
- Scheduler's pause-all/resume-all
- Database page's migrate action
- StatusBar's restart controls

This is a single shared CSS class/component (`shared/DangerZone.jsx` or
similar), not six different implementations — reuse the existing
`ConfirmModal`/`destructive_actions` registry IDs to decide what belongs in
a danger zone automatically rather than hand-flagging each one.

---

## 6. Fix: restart dropdown menu invisible/clipped

**Root cause, confirmed by live measurement:** `.admin-statusbar`
(`AdminPage.css:14-27`) sets `overflow-x: auto` for horizontal-scroll
handling on narrow screens. Per CSS spec, setting only `overflow-x` to a
non-`visible` value forces the browser to also compute `overflow-y` as
`auto` even though nobody set it — confirmed via
`getComputedStyle().overflow` returning `"auto"` on both axes. The restart
split-button's dropdown (`.admin-split-menu`, `position: absolute`, 67.8px
tall) is a descendant of that status bar, so it gets vertically clipped to
the status bar's own ~44px height — only a sliver renders, and that sliver
is "scrollable" because the status bar itself became an accidental scroll
container. `z-index: 200` does not help — z-index cannot escape an
ancestor's overflow clipping.

**Fix:** render the dropdown via a React portal (`document.body` or a
dedicated overlay root) and position it with `position: fixed` anchored to
the trigger button's `getBoundingClientRect()`, instead of `position:
absolute` inside the clipped ancestor. This is the durable general fix for
any menu/tooltip living inside a scrollable or sticky header — apply the
same pattern if other dropdowns in the admin panel have the same ancestor
(audit for other `position: absolute` menus inside `.admin-statusbar` or
any element with `overflow-x`/`overflow-y` set).

---

## 7. New: operator display/accessibility settings panel

Self-hosted, single-operator tool — every analyst running their own
instance should be able to tune the lab to their own eyes. Codebase already
uses CSS variables + `rem` units throughout (confirmed, no hardcoded
px/hex scattered in components), so this is cheaper than it sounds.

**Fix:** new admin page ("Display" or "Preferences") with:
- Font-size scale (e.g. small/medium/large, or a slider) — implemented as a
  single root-level CSS variable multiplier applied to the base `rem` size,
  not per-component overrides.
- Density mode (compact/comfortable) — adjusts spacing-scale variables.
- Persisted per-operator via `localStorage` (this is single-operator
  self-hosted, no backend/multi-user storage needed).
- This satisfies the WCAG dynamic-type guideline from the original audit
  for free — frame it as both a personalization feature and an
  accessibility one.

---

## Suggested execution order

0. **Section 11 (P0 scheduler fixes)** — real prod errors; unblocks badge
   truthfulness and correlation/backup/MITRE pipelines.
1. Sections 1 + 8 (quick safe fixes + feed-health dot) — same session, low
   risk, ship together; §8 unblocks cleaner mobile header left rail.
2. Section 6 (restart dropdown) — small, isolated, fully diagnosed already.
3. Section 4 (stop reloading pages) — foundational, makes every other admin
   change feel better immediately.
4. Section 3 (admin visual/IA pass, incl. 3b status legend) — the biggest
   perceived-quality jump.
5. Section 5 (danger zone pattern) — builds on section 3's visual language.
6. Section 2 (mobile nav redesign) — independent, do whenever.
7. Section 7 (settings panel) — independent, do last, it's additive and
   non-urgent.
8. Sections 9–10 (admin badge truthfulness, precise delay copy, schedule
   cadence) — ship together after §11 clears the error count.

Also merge the already-built-but-unmerged `feat/config-schema` branch
(per-field help text in API keys & config) — it directly supports section
3e and is just sitting there ready.

---

## 8. Consolidate feed-health LIVE indicator (discussion — batch with other UI work)

**Problem:** The same feed-health badge appears twice today — in
`Header.jsx` (top right) and again in `FeedRefreshStatus` at the bottom of
BRIEF/FEED (`App.jsx`). Both read the same `feedHealth` from `/api/health`
(polled every 60s). The right side of the header is already crowded
(clock, legal, shortcuts, user menu).

**Agreed direction (2026-06-24 discussion):**

- **Single placement only** — one indicator in the header, nowhere else.
  Remove the duplicate from `FeedRefreshStatus`; keep the footer text-only
  (“Last refreshed … · Next refresh …”).
- **Placement:** header **left**, beside logo/tagline (e.g. after “CVE
  intelligence”), not top right.
- **Dot-only UI** — drop the “LIVE” label. Keep `title` + `aria-label` for
  hover/focus discoverability.
- **One dot, four mutually exclusive states** (evaluate in order below; first
  match wins — syncing takes precedence over bootstrapping). Color + pulse
  speed encode state:

  | State | When (first match wins) | Color | Pulse |
  |---|---|---|---|
  | Syncing | `refresh_in_progress` | Amber | Faster (~1s) |
  | Bootstrapping | `cve_count < 10` and not syncing | Gray | Static |
  | Healthy | `cve_count ≥ 10` and not syncing | Green | Slow (~2s) |
  | Unknown / degraded | Health not loaded or poll failed | Gray or muted red | Static or slow |

- **Scope:** stays tied to **backend pipeline health** (`/api/health` ingest
  status, CVE count, refresh). Do **not** pulse on every frontend API call
  (drawer, infinite scroll, IOC lookup) — too noisy and loses meaning.
  Optional later: explicit “degraded” when a feed circuit is open.

**Files likely touched:** `Header.jsx`, `Header.css`, `App.jsx`
(`FeedRefreshStatus`), mobile header simplification in §2 (update “wordmark +
LIVE indicator” to “wordmark + status dot” on the left).

**Verification:** green/amber/gray states visible with seeded DB; footer has
no second dot; tooltip text matches state; `aria-label` present without
visible “LIVE” text; desktop + mobile header screenshots.

---

## 9. Admin notification badge must be truthful + dismissible (discussion — 2026-06-24)

**Problem (confirmed in prod screenshots):** Sidebar shows a red **3** on
“Intel status” / “System health”, but Analyst mode does not surface what
those 3 items are. User perceives it as dummy data.

**Root cause — not dummy:** The badge is `jobs_with_errors_count` from
`GET /api/admin/system` — a real count of scheduler jobs whose last run set
`had_error: true` in `sync_state` (`scheduler.last_run.{job_id}`). In the
reported instance the three errors are:

1. `nightly_correlation` — Postgres SQL: `SELECT DISTINCT … ORDER BY
   ocp.fetched_at` in `prefetch_pulse_iocs_for_nightly` (`engine.py`) —
   `fetched_at` is not in the SELECT list (Postgres rejects; SQLite did
   not).
2. `scheduled_backup` — `pg_dump not found on PATH` (missing
   `postgresql-client` on the host).
3. `weekly_mitre_refresh` — `DELETE FROM atlas_techniques` blocked by FK
   from `cve_atlas_map` (`replace_atlas_techniques` in `database.py`).

Operator mode **does** show these in “Recent errors” + Scheduler ERROR
rows. Analyst mode’s `JobTable` (`mode="analyst"`) omits the ERROR column
entirely — badge and banner disagree with what the page shows.

**Agreed direction:**

- **Rename/reframe badge** — not “notifications” generically; label as
  **“N issues”** or **“Job failures”** with tooltip explaining scheduler
  last-run errors (distinct from circuits, auth failures, log errors —
  each badge type already has its own `badgeKey` in `constants.js`).
- **Analyst Intel status must list the same errors** Operator sees — add a
  “Problems” card when `jobs_with_errors_count > 0` (job name, truncated
  error, “Retry” / link to Operator scheduler). Do not show a count badge
  without a matching visible list on that page.
- **Mark all as read / acknowledge** — persist per-operator acknowledgment
  in `localStorage` (or `sync_state` if we want cross-device): store
  `{ job_id, last_run_utc }` tuples the user has seen; badge count =
  unacknowledged errors only. Provide **“Mark all as read”** on the
  problems panel. Re-surface an item when the same job fails again with a
  newer `last_run_utc`.
- **No zero-truth badges anywhere** — audit all `badgeKey` usages in
  `Sidebar.jsx` (`open_circuit_count`, `failed_auth_last_24h`,
  `ingest_error_count`, `jobs_with_errors_count`) and ensure each linked
  page surfaces the underlying items.

**Files likely touched:** `OverviewPage.jsx`, `JobTable.jsx`, `Sidebar.jsx`,
`intelStatus.js`, `AdminPage.css`, optionally new
`adminNotifications.js` helper.

---

## 10. Precise “delayed” messaging + configured refresh cadence (discussion — 2026-06-24)

**Problem:** Analyst banner says **“Some sources are delayed”** with vague
“See details below”, while NVD at **4h** triggered amber (`NVD_AMBER_SECONDS
= 7200` in `intelStatus.js`) even though no circuit is open. Stat card
sub-label says **“usually hourly · incremental”** — we have exact APScheduler
triggers, not guesses.

**Agreed direction:**

- **Banner names names** — e.g. “**NIST CVE feed — 4h since last sync**
  (expected every 1h)” instead of “Some sources are delayed”. Enumerate
  every stale source in one sentence (NVD age, open circuits by
  `sourceLabel`, incidents stale, job errors — separate lines if multiple).
- **Per-source configured cadence** — expose from backend (extend
  `_build_job_info` or add `schedule` block to `/api/admin/system`):
  interval/cron from APScheduler trigger + env (`NVD_SYNC_INTERVAL_HOURS`,
  `KEV_SYNC_INTERVAL_MINUTES`, cron for nightly jobs, etc.). Display as
  **“Every 1h”**, **“Daily at 01:00 UTC”**, or user TZ when
  `briefr_timezone` / admin display prefs set.
- **Replace “usually …” copy** — delete `subLabel="usually hourly ·
  incremental"` from `OverviewPage.jsx`; use computed cadence string.
- **Timestamps** — Last run / Next run already in job table; ensure they
  respect operator timezone preference (reuse `formatAbsolute` /
  `briefr_timezone`).

**Files likely touched:** `intelStatus.js`, `OverviewPage.jsx`, `formatters.js`,
`backend/routers/admin.py`, `backend/scheduler.py` (read trigger metadata).

---

## 11. P0 — Fix three scheduler errors + confirm watermark safety (discussion — 2026-06-24)

**Priority:** Ship before or with §9–§10 — failures are real; user asked
for ASAP and data-loss assurance.

### 11a. `nightly_correlation` SQL (Postgres)

Fix `prefetch_pulse_iocs_for_nightly` query: include `ocp.fetched_at` in
SELECT or drop DISTINCT and use subquery/`GROUP BY`. Add a Postgres CI test
if not already covered.

### 11b. `weekly_mitre_refresh` FK violation

`replace_atlas_techniques` must not blind `DELETE` while `cve_atlas_map`
references rows. Options (pick one in implementation):

- Upsert techniques + delete only orphaned IDs, or
- `DELETE FROM cve_atlas_map WHERE technique_id NOT IN (…)` for removed
  techniques before replace, or
- `ON CONFLICT` upsert without full table wipe.

ATLAS upstream version watermark (`ATLAS_UPSTREAM_VERSION_KEY`) must only
advance after successful refresh.

### 11c. `scheduled_backup` — `pg_dump` missing

Document in deploy (`POSTGRES.md` / `briefr-update.sh`): install
`postgresql-client` when `DATABASE_URL` is Postgres. Fail with actionable
message in admin if binary absent. Not a data-loss bug — backup never ran.

### Watermark / data-loss audit (answer for operator)

| Pipeline | Watermark / checkpoint | Advances on failure? |
|---|---|---|
| NVD incremental | `sync_state` `nvd_sync_watermark` | **No** — set only after successful upsert (`scheduler.py`) |
| cvelistV5 | `cvelistv5_head_sha` | **No** — only when `advance=True` from delta fetch |
| EPSS backfill | `epss_backfill_done` | **No** — only on completion |
| Correlation campaigns | `correlation_build_watermark` | **No** — set in `build_campaigns_from_pulses` on success |
| OTX / PoC GitHub | per-source `sync_state` keys | **No** — commit after success |
| Scheduler job errors | `scheduler.last_run.{id}` ring | Records `had_error` only — does not advance ingest watermarks |

**Conclusion:** These three job failures did **not** roll back or corrupt CVE
data; they blocked correlation rebuild, ATLAS refresh, and backups
respectively. NVD at 4h is **staleness** (scheduler still running on
interval — check why last success was 4h ago separately), not watermark
loss.

**Verification:** After fixes, Operator System health shows 0 job errors;
retry each job; Postgres `pytest` green; backup creates archive when
`pg_dump` present.
