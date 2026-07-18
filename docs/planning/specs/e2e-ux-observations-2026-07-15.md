# E2E UX observations & remediation plan — 2026-07-15

**Status:** Plan of record (observations + ordered fix queue)  
**Audience:** Maintainer + agents executing the post–UI-modernization UX wave  
**Environment:** Postgres prod snapshot (~22k CVEs), `main` @ 240657d, dev stack `:5173` / `:8000`  
**Auth for automation:** `agentctl` / `agent-control-test-32bytes!!`

**Supersedes as single entry point:** partial notes in session handoff; consolidates
[`post-ui-audit-2026-07-15.md`](post-ui-audit-2026-07-15.md) (remediation phases),
live-browser passes, Playwright exhaustive audit, and accent-color verification.

**Execution:** [`execution-playbook.md`](execution-playbook.md) — one PR per ticket,
`./scripts/verify-local.sh` green, live browser verification on every UI PR.

---

## 1. How this audit was done

| Pass | Method | What it proved |
|------|--------|----------------|
| **A** | Maintainer checklist (#1–16) + codebase trace | Root causes for known bugs |
| **B** | Live browser (computerUse) | Partial; some nav failures were automation artifacts |
| **C** | Playwright exhaustive (`scripts/e2e_audit_exhaustive.py`) | **276 steps**, 257 OK, 8 WARN, 11 SKIP, 0 click failures |
| **D** | Computed-style accent sampling | Token vs rendered color on active controls |
| **E** | Human visual | Chart tooltip contrast, tooltip stickiness, spacing — **not** fully automatable |

**Raw logs:** `/opt/cursor/artifacts/e2e-audit-exhaustive-2026-07-15.json`  
**Click inventory:** [`e2e-click-map-2026-07-15.md`](e2e-click-map-2026-07-15.md)  
**Step log:** [`e2e-audit-results-2026-07-15.md`](e2e-audit-results-2026-07-15.md)

---

## 2. Observations in traversal order

Each row: **E2E status** (automated click) · **UX finding** (human/code) · **Ticket**

### A. Global chrome

| Control | E2E | UX observation | Ticket |
|---------|-----|----------------|--------|
| BRIEFR logo → home | OK | — | — |
| Main tabs (BRIEF, FEED, IOC, INCIDENTS, FORGE, ARCH) | OK | ARCH leaves main shell (separate route); demote per IA §7 | PM-4c |
| ⋯ menu: Keyboard shortcuts, Tutorial, About, Privacy, Terms | OK | — | — |
| ⋯ My Stack / Clear session | SKIP (hidden when authed) | Expected for logged-in users | — |
| Timezone popover → search → pick | OK | — | — |
| Notifications: open, dismiss all, mark seen | OK (dismiss one SKIP: empty queue) | — | — |
| Account menu: Admin, Preferences | OK | Logout not exercised (session kept) | — |
| Command palette (Ctrl+K) | OK | — | — |
| Mobile tab bar (390px) | OK | BRIEF / FEED / IOC / INCIDENTS tabs clickable | — |
| **Active tab accent** | OK (clicks) | Pre-E8 tan `#c8b88a` felt “missing”; **maintainer chose BRIEFR orange `#e85533`** | PR #602, PM-2a |

### B. BRIEF tab

| Control | E2E | UX observation | Ticket |
|---------|-----|----------------|--------|
| Stats row cards (click → feed filter) | OK | — | — |
| Morning brief filter chips | OK | — | — |
| Brief row → drawer | OK | — | — |
| Open full feed → | OK | — | — |
| Analyst charts collapse/expand | OK | — | — |
| KEV vendors chart hover + view as table | OK | **Tooltip body low contrast; white bar hover** on Recharts | UX-PM-1, PM-1a |
| EPSS movers window picker | OK | — | — |
| EPSS row → drawer | OK | **All severities show UNKNOWN** — API omits `severity` on changes | UX-PM-2, PM-0a |
| Scroll page | OK | — | — |

### C. FEED tab

| Control | E2E | UX observation | Ticket |
|---------|-----|----------------|--------|
| Quick filters (8) | OK | Active chip accent was weak with tan token; orange token helps | PR #602 |
| Search, stack input, vendor multi-select | OK | — | — |
| Generate digest, Export CSV/XLSX | OK | — | — |
| Stack hint dismiss | OK | — | — |
| Sidebar YOUR FILTERS (KEV, PoC, EPSS, My stack) | OK | **Grid cramped / misaligned**; toggles use **red** when on, not accent | UX-PM-6, PM-1c; PM-2a |
| 14-day sparkline / heatmap day click | OK | 14-day counts accuracy not validated vs NVD | Q5 |
| Top techniques click | SKIP (no rows in snapshot) | — | — |
| CVE card → drawer (KEV + generic) | OK | See §D | — |
| Load more | OK | — | — |
| Patch filter via stats tile | OK | Stats live on BRIEF panel, not FEED | — |

### D. CVE detail drawer

| Control | E2E | UX observation | Ticket |
|---------|-----|----------------|--------|
| Pin, investigation, REPORT, ⋯ overflow | OK | — | — |
| Tabs OVERVIEW / INTEL / DETECT / RELATED | OK | — | — |
| Overview score tooltips | OK (hover) | **Tooltips stick** after open (`hover-focus` + focus) | UX-PM-3, PM-0b |
| Overview score row layout | OK (scroll) | **“Exploit Availability” overlaps SIGNAL** column | UX-PM-4, PM-0c |
| Intel: PoC, technique pills | OK | — | — |
| Detect: copy rule | SKIP (no rules on sample CVEs) | — | — |
| Related CVE + back stack | SKIP (no related rows on samples) | — | — |
| Close drawer | SKIP (timing; drawer closed by other steps) | — | — |

### E. IOC LOOKUP

| Control | E2E | UX observation | Ticket |
|---------|-----|----------------|--------|
| IP / domain / invalid lookups | OK | Enrichment empty without API keys (expected) | — |
| Scroll results | OK | — | — |

### F. INCIDENTS & NEWS

| Control | E2E | UX observation | Ticket |
|---------|-----|----------------|--------|
| Case cards (211 visible) | OK | — | — |
| Open case card | OK | — | — |

### G. FORGE

| Control | E2E | UX observation | Ticket |
|---------|-----|----------------|--------|
| Coverage / Scenarios / Campaigns / Backlog / Library tabs | OK | — | — |
| Coverage technique → hunt pack rail | OK | — | — |
| Stack-only toggle | OK | — | — |
| Library filters, sort, row click, delete cancel | OK | **Filter toolbar stacked / weak hierarchy** | UX-PM-7, PM-1d |
| Hunt pack rail: generate, PDF, proof bench | OK (visibility) | — | — |

### H. ARCH (`/security-architecture`)

| Control | E2E | UX observation | Ticket |
|---------|-----|----------------|--------|
| All 12 sidebar sections | OK | — | — |
| Export PDF (Overview, Threat Scenarios) | OK | — | — |
| Table column sorts | OK | **Truncation until Wrap**; weak row borders | UX-PM-12, PM-2b |
| Graph reset, search, node click, pan, zoom | OK | **Zoom anchors top-left**; fixed height; pan selects text | UX-PM-9, PM-3a |
| Wrap/Center toggles | OK (where present) | Per-table wrap prefs noisy | PM-2c |
| Context rail | OK (visible) | **Wastes width** when empty | UX-PM-14, PM-3c |
| Corpus footer | SKIP (not in DOM on sampled sections) | **Maintainer wants removed** from analyst UI | UX-PM-17, PM-4b |
| Nav label **“Mitre Attack”** | OK (nav works) | Misspelling — should be **MITRE ATT&CK** | UX-PM-13, PM-2c |
| Overview metric tiles | OK | Poor segmentation/spacing | UX-PM-8, PM-2d |
| Trust Boundaries diagram | OK | Static layout feels janky | UX-PM-11, PM-2d |
| Security Decisions section | OK (loads) | **Internal ADRs — remove from product UI** | UX-PM-15, PM-4b |
| Reviews section | OK (loads) | **Duplicates Admin audit log** | UX-PM-16, PM-4b |

### I. Admin — analyst mode

| Control | E2E | UX observation | Ticket |
|---------|-----|----------------|--------|
| Intel status, Source status, Alert channels, Pinned CVEs, Display | OK | **Intel status cards empty** — `/api/admin/system` 500 | UX-PM-18, PM-0d |
| Breadcrumbs, needs-attention panel | OK | — | — |
| Operator switch | OK (via localStorage in script) | Confirm modal exists in live UX | — |

### J. Admin — operator mode

| Control | E2E | UX observation | Ticket |
|---------|-----|----------------|--------|
| All 16 operator pages + control sweep | OK | 8 WARN: disabled/loading buttons on Scheduler, Webhooks, AI ops, Audit log | — |
| Display prefs apply/save/reset | OK | — | — |

### K. Static routes

| Route | E2E | UX observation | Ticket |
|-------|-----|----------------|--------|
| `/wallboard` | OK | Token gate UI | — |
| `/login` | OK | — | — |
| `/privacy`, `/terms` | OK | — | — |

### L. Cross-cutting (requires human eyes)

| Theme | E2E | UX observation | Ticket |
|-------|-----|----------------|--------|
| Loading / empty / error states | Partial | Correlation slow-load on DETECT tab | — |
| Accent on active/selected/checkbox | Clicks OK; color pass | Tan was inconsistent; **orange adopted** (#602); sidebar toggles still red | PR #602, PM-2a |
| Table truncation / borders / h-scroll | ARCH exercised | One DataGrid standard needed | PM-2b |
| Tooltip stickiness after click/focus | Not automated | Drawer score rows | PM-0b |

---

## 3. Findings registry (canonical IDs)

| ID | Sev | Area | Finding | Root cause |
|----|-----|------|---------|------------|
| UX-PM-1 | P0 | BRIEF charts | KEV tooltip illegible; white bar hover | Recharts defaults + low-contrast tooltip styles |
| UX-PM-2 | P0 | BRIEF EPSS movers | Severities **UNKNOWN** | `get_recent_cve_changes()` omits `severity` |
| UX-PM-3 | P0 | FEED drawer | Score tooltips **stick** | `ControlTooltip` `trigger="hover-focus"` |
| UX-PM-4 | P0 | FEED drawer | Score rows **overlap** | `.drawer-risk-comp-header--semantics` label column too narrow |
| UX-PM-5 | P1 | Global | Accent felt missing | Incomplete token application; tan vs brand orange |
| UX-PM-6 | P1 | FEED sidebar | YOUR FILTERS grid cramped | `Sidebar.jsx` 2×2 toggle layout |
| UX-PM-7 | P1 | FORGE Library | Filter toolbar layout | `LibraryView.jsx` vertical stack |
| UX-PM-8 | P1 | ARCH Overview | Metric tiles spacing | `OverviewSection` CSS |
| UX-PM-9 | P1 | ARCH graph | Zoom/pan/viewport | `ArchitectureGraphSection.jsx` scale-only wheel zoom |
| UX-PM-10 | P1 | ARCH graph | Corpus may be stale | `architecture.json` drift |
| UX-PM-11 | P1 | ARCH Trust | Flow diagram janky | Static SVG/CSS |
| UX-PM-12 | P1 | ARCH tables | Truncation, borders, wrap | DataGrid defaults |
| UX-PM-13 | P1 | ARCH nav | “Mitre Attack” label | `humanizeSectionId('mitre_attack')` |
| UX-PM-14 | P2 | ARCH | Context rail width | Empty persistent rail |
| UX-PM-15 | P2 | ARCH | Security Decisions in UI | ADR corpus exposed |
| UX-PM-16 | P2 | ARCH | Reviews in UI | Duplicates audit log |
| UX-PM-17 | P2 | ARCH | Corpus footer | Manifest metadata in product chrome |
| UX-PM-18 | P0 | Admin | Intel status empty (500) | `build_webhook_destination_health` SQL `text >= timestamptz` |
| UX-PM-19 | P1 | Data | `detected_at` as TEXT on Postgres | Schema gap in `cve_change_history` |

---

## 4. Accent color — observations & decision

### 4.1 Before change (E8 tokens)

| Token | Value | Used for |
|-------|-------|----------|
| `--c-accent` / `--accent-selected` | `#c8b88a` (tan) | Nav, filters, FORGE/ARCH active, focus ring |
| `--admin-accent` | `#e85533` (orange) | Admin only (duplicate hex) |

**Rendered inconsistencies (computed-style pass):**

- Main nav active tab: tan fill (correct per token)
- FEED active filter: **desaturated** border/text — accent hard to see
- BRIEF active chip: neutral text, faint tan background
- FORGE / ARCH active nav: tan — OK
- Admin sidebar active: tan inset bar, **not** admin orange (used `--accent-selected`, not `--admin-accent`)
- Sidebar KEV/PoC/EPSS toggles: **red** when on (intentional signal, not accent)

### 4.2 Maintainer decision (2026-07-15)

> Use **BRIEFR orange `#e85533`** as the single brand accent everywhere, not tan.

**Implementation:** PR [#602](https://github.com/Soldier0x0/briefr/pull/602) — `tokens.css` `--c-accent` → `#e85533`; `--text-on-accent` → white; admin `--admin-accent*` → `var(--accent-primary)`.

**Follow-up (PM-2a):** Sidebar toggles → accent or documented exception; verify every active state after orange lands.

---

## 5. Information architecture (locked)

| Decision | Choice |
|----------|--------|
| **ARCH header tab** | Remove after migration (Phase 4) |
| **System Architecture graph** | Admin → Security posture; full viewport; zoom-to-cursor |
| **Overview, Trust, Attack Surface, Risks** | Admin → Security posture (analyst read-only) |
| **Security Decisions, Reviews** | Remove from product UI |
| **Context rail** | Remove or inline on node click |
| **MITRE tables in ARCH** | Replace with FORGE interactive navigator |
| **Accent** | **Orange `#e85533`** (resolved — was tan in E8 spec) |

---

## 6. Remediation plan (dependency order)

Ship in this order. Do **not** start Phase 4 until Phase 0 P0s are merged.

### Phase 0 — P0 bugs (no IA moves)

| PR | Title | Fixes | Primary files | Acceptance |
|----|-------|-------|---------------|------------|
| **PM-0a** | EPSS movers severity | UX-PM-2 | `backend/db/enrichment.py`, `BriefCharts.jsx` | Severity column not UNKNOWN |
| **PM-0b** | Drawer tooltips hover-only | UX-PM-3 | `OverviewTab.jsx` | No stuck tooltips on open |
| **PM-0c** | Drawer score grid overlap | UX-PM-4 | `DetailDrawer.css` | No overlap at 1440px / 1024px |
| **PM-0d** | Admin system status 500 | UX-PM-18 | `backend/db/webhooks.py` | Intel status cards populate |
| **PM-0e** | `detected_at` → timestamptz | UX-PM-19 | Alembic migration | Time filters work on Postgres |

**Parallel:** PM-0a ∥ PM-0d. Merge **PR #602 (orange accent)** with or before PM-2a.

### Phase 1 — Charts & analyst surfaces

| PR | Title | Fixes | Acceptance |
|----|-------|-------|------------|
| **PM-1a** | Recharts tooltip + bar hover | UX-PM-1 | Readable tooltip; no white hover |
| **PM-1b** | Chart audit sweep | UX-PM-1 | All charts use `rechartsTheme.js` |
| **PM-1c** | FEED sidebar filter grid | UX-PM-6 | Aligned toggles |
| **PM-1d** | Forge Library filter toolbar | UX-PM-7 | Single toolbar row |

### Phase 2 — Design system enforcement

| PR | Title | Fixes | Acceptance |
|----|-------|-------|------------|
| **PM-2a** | Accent application audit | UX-PM-5 | Orange on all active/selected; document toggle exception |
| **PM-2b** | DataGrid standard v2 | UX-PM-12 | Borders, padding, one wrap/center per page |
| **PM-2c** | ARCH MITRE label + shared grid prefs | UX-PM-13, UX-PM-12 | “MITRE ATT&CK”; shared wrap |
| **PM-2d** | ARCH Overview + Trust layout | UX-PM-8, UX-PM-11 | Tiles + flow diagram polish |

### Phase 3 — ARCH graph (route still live)

| PR | Title | Fixes | Acceptance |
|----|-------|-------|------------|
| **PM-3a** | Graph viewport + zoom | UX-PM-9 | Zoom at cursor; no text selection on pan |
| **PM-3b** | Fit-to-view + reset | UX-PM-9 | Frames all nodes |
| **PM-3c** | Node detail panel | UX-PM-14, UX-PM-10 | Replaces empty context rail |
| **PM-3d** | Corpus regen / drift check | UX-PM-10 | CI or admin regen trigger |

### Phase 4 — Information architecture

| PR | Title | Fixes | Acceptance |
|----|-------|-------|------------|
| **PM-4a** | Admin Security posture shell | IA | Operator nav section |
| **PM-4b** | Remove ADR/Reviews/footer | UX-PM-15–17 | Gone from analyst UI |
| **PM-4c** | Remove ARCH tab + redirect | IA | Five main tabs only |
| **PM-4d** | FORGE MITRE navigator MVP | UX-PM-13 | Interactive tactic → technique |
| **PM-4e** | Cross-links drawer ↔ Forge | IA | Technique pill → Forge filter |

---

## 7. User checklist → tickets (#1–16)

| # | Report | Phase / PR |
|---|--------|------------|
| 1 | Charts + nav color | PM-1a/b, **#602**, PM-2a |
| 2 | EPSS UNKNOWN | PM-0a, PM-0e |
| 3 | Your filters layout | PM-1c |
| 4 | Drawer tooltips + overlap | PM-0b, PM-0c |
| 5 | Hunt Pack Library | PM-1d |
| 6 | ARCH Overview | PM-2d |
| 7 | System architecture graph | PM-3a/b/c/d |
| 8 | Trust boundaries | PM-2d |
| 9 | Checkbox/selection color | **#602**, PM-2a |
| 10 | MITRE spelling + nodes | PM-2c, PM-4d |
| 11 | Context rail | PM-3c, PM-4b |
| 12 | Row spacing standard | PM-2b |
| 13 | Tables + Security Decisions | PM-2b, PM-4b |
| 14 | Horizontal scroll + borders | PM-2b |
| 15 | Reviews section | PM-4b |
| 16 | Corpus footer | PM-4b |

---

## 8. Verification matrix

| Check | Command / method |
|-------|------------------|
| Backend | `cd backend && pytest tests/ -q` (+ Postgres via `postgres-dev.sh`) |
| Frontend | `cd frontend && npm run build` |
| Merge gate | `./scripts/verify-local.sh` |
| E2E regression | `python3 scripts/e2e_audit_exhaustive.py` |
| UI smoke | `PLAYWRIGHT_SMOKE=1` when stack available |
| Visual | Live browser: §2 rows marked UX finding |

**Minimum browser checklist per UI PR:** BRIEF charts + EPSS · FEED drawer scroll · FORGE Library · Admin Intel status · ARCH graph pan/zoom.

---

## 9. Open questions

| # | Question | Status |
|---|----------|--------|
| Q1 | Tan vs orange accent? | **Resolved — orange `#e85533` (#602)** |
| Q2 | Analyst read-only Security posture? | Default yes |
| Q3 | FORGE MITRE: matrix vs graph? | Default tactic columns + expand |
| Q4 | `/security-architecture` redirect? | **Kept — reassessed 2026-07-18.** No release has been cut since PM-4c (#638, 2026-07-16; repo has no tags/version-bump process, continuous deploy off `main`). "One release" has no signal to trigger on yet — leave the redirect until a deliberate release process exists or the route sees zero traffic in access logs. |
| Q5 | 14-day publication accuracy? | **Resolved by audit — 2026-07-18.** `/api/stats/timeline` groups by `DATE(published)` where `published` is written verbatim from the NVD API's own `published` field (UTC, unmodified) — no transform to introduce drift. `cve_id` is the upsert conflict key everywhere (`db/cve.py`), so no duplicate-row inflation. Postgres date-object vs SQLite string normalization is covered by `tests/test_stats_timeline.py`. Local dev DB has only synthetic seed data (not real NVD history), so a live count-for-count diff against NVD wasn't possible in this session — no code defect found; if a discrepancy is ever reported, it'll be a data-freshness question (scheduler lag under the FEED gap banner), not a query bug. |
| Q6 | Sidebar toggles: red vs orange when on? | **Resolved — already shipped.** `1b4f685` (PM-2a, 2026-07-15) moved `.toggle-on`/`.toggle-thumb` onto `--accent-primary`/`--surface-selected` tokens (orange `#e85533`), no red. Grid alignment fixed same window in `55edb6d` (PM-1c, #611, 2026-07-16). This row was just never marked done. |

---

## 10. Success criteria (program complete)

1. No P0 rows open in §3.  
2. Orange accent applied consistently (§4).  
3. Main nav: BRIEF, FEED, IOC, INCIDENTS, FORGE only.  
4. Security posture under Admin; FORGE MITRE navigator MVP.  
5. One DataGrid standard in `design-system.md`.  
6. `PRODUCT_STATUS.md` updated; HANDOVER per merged PR.

---

## 11. Wiring

| Doc | Role |
|-----|------|
| **This file** | Single ordered observations + plan |
| [`BACKLOG.md`](../BACKLOG.md) §12 | Checkbox queue |
| [`SPRINT_2026-07.md`](../SPRINT_2026-07.md) PM track | Sprint activation |
| [`post-ui-audit-2026-07-15.md`](post-ui-audit-2026-07-15.md) | Phase detail (archive sibling; prefer §6 here) |

**Related PRs (consolidated kickoff):** This branch merges **#601** (audit script) + **#602** (orange accent) + **#603** (master plan) into one merge to `main`. After merge, execute **PM-0a** next.

**Implementation queue (22 PRs after kickoff):** see §6.
