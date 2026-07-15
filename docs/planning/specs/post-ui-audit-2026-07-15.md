# Post–UI modernization UX audit — remediation & IA plan

> **Prefer the ordered master plan:** [`e2e-ux-observations-2026-07-15.md`](e2e-ux-observations-2026-07-15.md)
> (E2E observations in traversal order + accent decision + ticket queue). This file retains
> phase-level detail for PM-0…PM-4.

**Status:** Plan of record — **no implementation in this document**  
**Date:** 2026-07-15  
**Audit basis:** Live browser walk (cloud agent, Postgres prod snapshot ~22k CVEs,
`main` @ 240657d). User-reported issues + agent verification + codebase trace.

**Supersedes / extends:** [`qa-audit-2026-07-12.md`](qa-audit-2026-07-12.md) (partial UI overlap),
[`reliability-and-bug-backlog.md`](../reliability-and-bug-backlog.md) (REL-3 admin 500, REL-*),
[`threat-modeling-security-architecture.md`](threat-modeling-security-architecture.md) (ARCH placement),
[`ui-modernization-plan.md`](../ui-modernization-plan.md) (E0–E9 shipped — this is the **next** UX wave).

**Execution:** per [`execution-playbook.md`](execution-playbook.md) — one PR per ticket where
possible, `./scripts/verify-local.sh` green, **live browser verification** on every UI PR.

**Central principle:**

> Ship a **production analyst tool**, not a maintainer documentation viewer in the main nav.
> Fix broken interactions before reskinning. Enforce **one** table standard and **one** accent
> application path (`--accent-selected` / `--accent-primary` from `tokens.css`).

---

## 1. Executive summary

UI modernization (E0–E9) delivered primitives and token wiring, but a full-product pass
exposes three classes of gap:

| Class | Examples | Outcome |
|-------|----------|---------|
| **P0 functional** | EPSS movers severity always UNKNOWN; drawer tooltips stick; admin `/system` 500 | Data + interaction bugs |
| **P1 design system drift** | Recharts white hover, tooltip contrast, table ellipsis default, checkbox accents | One standard everywhere |
| **P1 information architecture** | ARCH tab exposes ADRs, audit log, corpus footer to all analysts | Demote / merge / remove |

**Recommended program:** **5 phases, ~18 PRs**, dependency-ordered. Phases 0–1 are bug fixes
(no IA moves). Phase 2 is cross-surface design consistency. Phases 3–4 are ARCH demotion +
Forge MITRE navigator (largest scope).

**Explicitly out of scope here:** REL-1/REL-2 correlation precompute (ADR-004, E1 — separate
track), STIX export, V2.0 docker-compose, new framework checklists (TM-6+).

---

## 2. Findings registry (canonical IDs)

New ids use prefix **`UX-PM-*`** (post-modernization). Cross-refs to existing ids preserved.

| ID | Sev | Area | Finding | Root cause (code) |
|----|-----|------|---------|-------------------|
| **UX-PM-1** | P0 | BRIEF charts | KEV chart tooltip body nearly invisible; white bar hover highlight | Recharts default `activeBar` + `tooltipContentStyle` uses low-contrast `--text2` on `--bg2` |
| **UX-PM-2** | P0 | BRIEF EPSS movers | All severities **UNKNOWN** | `GET /api/changes` omits `severity`; `BriefCharts.jsx` reads `row.severity` |
| **UX-PM-3** | P0 | FEED drawer | CVSS / score tooltips **stick** after open | `ControlTooltip` `trigger="hover-focus"` on drawer rows; focus on open |
| **UX-PM-4** | P0 | FEED drawer | Threat score rows overlap ("Exploit Avail" ∩ "SIGNAL") | `.drawer-risk-comp-header--semantics` grid `5.5rem` label column too narrow |
| **UX-PM-5** | P1 | Global nav | Signature accent feels "missing" on tabs, logo, checkboxes | Incomplete token migration; user memory of pre-E8 orange vs canonical `#c8b88a` tan |
| **UX-PM-6** | P1 | FEED sidebar | "YOUR FILTERS" grid misaligned / cramped | `Sidebar.jsx` 2×2 `Toggle` grid, multi-line labels |
| **UX-PM-7** | P1 | FORGE Library | Filter toolbar wonky (stacked inputs, weak hierarchy) | `LibraryView.jsx` vertical stack, no shared filter row |
| **UX-PM-8** | P1 | ARCH Overview | Metric tiles poor segmentation / spacing | `OverviewSection` grid CSS |
| **UX-PM-9** | P1 | ARCH graph | Zoom anchors top-left; not viewport-height; pan UX | `ArchitectureGraphSection.jsx` wheel zoom scale-only; fixed content height |
| **UX-PM-10** | P1 | ARCH graph | Graph may feel stale | Corpus `architecture.json` drift vs `main` until regen job/CI |
| **UX-PM-11** | P1 | ARCH Trust | Flow diagram janky | Static SVG/CSS layout |
| **UX-PM-12** | P1 | ARCH tables | Text truncated until Wrap; no row borders; Wrap/Center per subsection | `DataGrid` / `ArchDataGrid` defaults + per-tactic grid mounts |
| **UX-PM-13** | P1 | ARCH nav | "Mitre Attack" misspelling | `humanizeSectionId()` — no ATT&CK acronym map |
| **UX-PM-14** | P2 | ARCH chrome | Context rail wastes width | `ContextRail` persistent empty state |
| **UX-PM-15** | P2 | ARCH content | Security Decisions = internal ADRs | Curated corpus in user nav |
| **UX-PM-16** | P2 | ARCH content | Reviews duplicates Admin audit log | `ReviewHistorySection` merges `audit_log` |
| **UX-PM-17** | P2 | ARCH chrome | `corpus v1 · reviewed …` footer | `SecurityArchitecturePage.jsx` manifest metadata |
| **UX-PM-18** | P0 | Admin | Intel status cards empty (HTTP 500) | `build_webhook_destination_health` SQL `text >= timestamptz` |
| **UX-PM-19** | P1 | Data layer | `cve_change_history.detected_at` is `TEXT` on Postgres | Schema/migration gap — fragile time filters |

---

## 3. Product / IA decision (locked for this program)

These decisions implement the maintainer direction from the 2026-07-15 review.

| Decision | Choice |
|----------|--------|
| **ARCH header tab** | **Remove** from main nav after migration (Phase 4). Until then, keep route for bookmarks. |
| **System Architecture graph** | **Keep** — move to **Admin → Security posture** (operator mode), full viewport height, zoom-to-cursor, fit-to-view. |
| **Overview, Trust Boundaries, Attack Surface, Risks** | Move to **Admin → Security posture** (read-only analyst can view; edit/review operator-only later). |
| **Security Decisions, Reviews** | **Remove from product UI** — ADRs stay in `docs/decisions/`; audit stays Admin → Audit log only. |
| **Context rail** | **Remove** when ARCH moves to admin (or collapse to inline drawer on node click). |
| **MITRE ATT&CK tables in ARCH** | **Replace** with interactive navigator under **FORGE** (Phase 4) — tactic → technique nodes, linked to hunt packs / CVE evidence. |
| **Controls, Abuse Cases, Threat Scenarios** | **Forge links** only (threat scenarios API already powers Forge); drop standalone ARCH sections after Forge navigator ships. |
| **Accent color** | **Orange `#e85533`** (`--accent-selected`) — shipped in PR #602; enforce on sidebar toggles in PM-2a |

---

## 4. Phase plan (dependency-ordered PRs)

### Phase 0 — P0 bugs (ship first, no IA moves)

**Gate:** each PR includes live browser repro of the fixed symptom.

| PR | Title | Fixes | Files (primary) | Acceptance |
|----|-------|-------|-----------------|------------|
| **PM-0a** | EPSS movers: join severity from `cves` | UX-PM-2 | `backend/db/enrichment.py` `get_recent_cve_changes`, router serializer, `BriefCharts.jsx` test | TOP EPSS MOVERS shows LOW/MEDIUM/HIGH/CRITICAL for known CVEs |
| **PM-0b** | Drawer tooltips: hover-only in score section | UX-PM-3 | `OverviewTab.jsx` — `trigger="hover"` on drawer breakdown tooltips | Open drawer → no tooltip until hover; scroll does not leave tooltip stuck |
| **PM-0c** | Threat score breakdown grid overlap | UX-PM-4 | `DetailDrawer.css` — widen label column / stack on narrow widths | "Exploit Availability" + SIGNAL never overlap at 1440px and 1024px |
| **PM-0d** | Admin system status 500 (webhook health SQL) | UX-PM-18 | `backend/db/webhooks.py` — cast `detected_at`/timestamps for Postgres | Admin → Intel status cards populate; no HTTP 500 |
| **PM-0e** | `cve_change_history.detected_at` → `timestamptz` (Postgres) | UX-PM-19 | New Alembic migration + dual SQLite compat in queries | `since_hours` filters work both ways; existing rows backfilled |

**Parallelism:** PM-0a and PM-0d independent. PM-0e should merge before relying on time-window EPSS queries in production.

---

### Phase 1 — Charts & analyst surfaces

| PR | Title | Fixes | Acceptance |
|----|-------|-------|------------|
| **PM-1a** | Recharts theme: tooltip contrast + bar hover | UX-PM-1 | KEV vendor chart: tooltip body readable; hover uses `--surface-selected` or `--accent` tint, not white |
| **PM-1b** | Chart audit sweep | UX-PM-1 | All Recharts instances use `rechartsTheme.js`; add Playwright or visual checklist row in PR body |
| **PM-1c** | FEED sidebar filter grid | UX-PM-6 | YOUR FILTERS: aligned 2×2 or single-column stack; consistent `Toggle` sizing |
| **PM-1d** | Forge Hunt Pack Library filter toolbar | UX-PM-7 | One toolbar row: technique + priority + KEV + search; matches Admin filter patterns |

---

### Phase 2 — Global design system enforcement

**Gate:** extend [`design-system.md`](../../design/design-system.md) with table + chart rules.

| PR | Title | Fixes | Acceptance |
|----|-------|-------|------------|
| **PM-2a** | Accent application audit | UX-PM-5 | Header logo, active tab, checkboxes, sort icons, DataGrid active row use `--accent-selected`; add unit test like `activeStateGate.test.js` |
| **PM-2b** | DataGrid standard v2 | UX-PM-12 | Default: light row borders, `8–12px` row padding, optional horizontal scroll; **one** Wrap/Center per grid page |
| **PM-2c** | ArchDataGrid → shared DataGrid prefs | UX-PM-12, UX-PM-13 | MITRE tactic groups share parent toolbar OR inherit global wrap pref; label map: `mitre_attack` → **MITRE ATT&CK** |
| **PM-2d** | ARCH Overview + Trust Boundaries layout | UX-PM-8, UX-PM-11 | Metric cards: consistent gap, border, hover; trust flow: aligned connectors |

**Note on accent:** PM-2a documents that tan gold **is** the signature color post-E8. If maintainer wants orange-red CVE brand on nav, open **ADR-006** before PM-2a.

---

### Phase 3 — ARCH graph hardening (still at `/security-architecture` route)

Overlaps **REL-3** (pan selects text) — fold fix here.

| PR | Title | Fixes | Acceptance |
|----|-------|-------|------------|
| **PM-3a** | Architecture graph viewport + zoom | UX-PM-9, REL-3 | Canvas `min-height: calc(100vh - header)`; wheel zoom centers on cursor; `user-select: none` on canvas |
| **PM-3b** | Fit-to-view + reset control | UX-PM-9 | "Fit graph" button; initial view frames all nodes |
| **PM-3c** | Node detail expansion | UX-PM-10 | Click node → side panel (replace empty Context rail content) with tables/jobs/routers from corpus |
| **PM-3d** | Corpus regen in CI / admin trigger | UX-PM-10 | `generate_security_corpus.py` drift check or Admin "Regenerate architecture" job |

---

### Phase 4 — Information architecture (largest change)

| PR | Title | Work | Acceptance |
|----|-------|------|------------|
| **PM-4a** | Admin → Security posture shell | New admin section `securityposture` (operator nav); embed Overview, System Architecture, Trust Boundaries, Attack Surface, Risks | Operator sees sections; analyst read-only |
| **PM-4b** | Remove ARCH user-facing sections | Drop Security Decisions, Reviews, Components from nav; remove corpus footer | UX-PM-15, UX-PM-16, UX-PM-17 gone |
| **PM-4c** | Remove ARCH header tab + redirects | Remove **ARCH** tab; `/security-architecture` → redirect to admin or 404 with link | Main nav: BRIEF, FEED, IOC, Incidents, FORGE only |
| **PM-4d** | FORGE MITRE ATT&CK navigator (MVP) | Tactic columns or expandable tree; technique nodes link to coverage + hunt packs | UX-PM-13 satisfied; no flat-only tables |
| **PM-4e** | Cross-links | Forge scenarios ↔ MITRE nodes ↔ CVE drawer technique pills | Click technique in drawer → Forge navigator pre-filtered |

**Dependency:** PM-4a before PM-4c. PM-4d can start in parallel with Phase 3 but merge after PM-3c (node interaction patterns).

---

## 5. Verification matrix (every phase)

| Check | How |
|-------|-----|
| Backend | `cd backend && pytest tests/ -q`; Postgres path via `postgres-dev.sh` for DB migrations |
| Frontend | `cd frontend && npm run test:unit && npm run build` |
| Merge gate | `./scripts/verify-local.sh` |
| UI | Live browser: login → each main tab → ARCH/admin targets → drawer open/close → chart hover |
| Regression | `backend/tests/test_playwright_smoke.py` with `PLAYWRIGHT_SMOKE=1` when stack available |

**Browser checklist (minimum per UI PR):**

1. BRIEF — KEV chart hover, EPSS movers severity column  
2. FEED — YOUR FILTERS, open CVE drawer, scroll drawer (no sticky tooltip)  
3. FORGE — Library filters + table  
4. Admin — Intel status (post PM-0d)  
5. Security posture / ARCH — graph pan/zoom, table wrap  

---

## 6. Mapping to user-reported list (§2026-07-15)

| User # | Phase / PR |
|--------|------------|
| 1 Charts + nav color | PM-1a/b, PM-2a |
| 2 EPSS unknown | PM-0a, PM-0e |
| 3 Your filters | PM-1c |
| 4 Drawer tooltips + overlap | PM-0b, PM-0c |
| 5 Hunt Pack Library | PM-1d |
| 6 ARCH Overview | PM-2d |
| 7 System architecture graph | PM-3a/b/c/d |
| 8 Trust boundaries | PM-2d |
| 9 Selection/checkbox color | PM-2a |
| 10 MITRE spelling + wrap + nodes | PM-2c, PM-4d |
| 11 Context rail | PM-3c (inline panel), PM-4b |
| 12 Row spacing standard | PM-2b |
| 13 Tables + Security Decisions | PM-2b, PM-4b |
| 14 Horizontal scroll + borders | PM-2b |
| 15 Reviews section | PM-4b |
| 16 Corpus footer | PM-4b |

---

## 7. Open questions (maintainer)

| # | Question | Default if no answer |
|---|----------|-------------------|
| Q1 | Revert accent to orange-red or keep tan gold? | **Resolved — orange `#e85533` (PR #602)** |
| Q2 | Can analysts view Security posture in admin read-only? | Yes |
| Q3 | FORGE MITRE navigator: flat matrix first or force-directed graph? | Tactic columns + expand (closer to attack.mitre.org) |
| Q4 | Hard delete `/security-architecture` route or 302 to admin? | 302 for 1 release, then remove |
| Q5 | 14-day publications inaccuracy — separate data ticket? | Park under PM-0e + validate `fetchStatsTimeline` against NVD `published` after timestamp fix |

---

## 8. BACKLOG / sprint wiring

- **Canonical checklist:** [`BACKLOG.md`](../BACKLOG.md) §12 (Post–UI modernization audit).  
- **Sprint:** add Phase 0 items to next sprint execution queue when activated.  
- **Do not duplicate** per-PR rows in `ui-modernization-plan.md` (that program is closed).

---

## 9. Success criteria (program complete)

1. No P0 items open in §2 registry.  
2. Main nav has no ARCH tab; security posture lives under Admin.  
3. FORGE has interactive MITRE navigator MVP with CVE/hunt-pack links.  
4. One table standard documented in `design-system.md` and applied to Admin, Forge Library, ARCH remnants.  
5. `PRODUCT_STATUS.md` + `USE.md` updated to describe new nav (no ADR/audit in analyst UI).  
6. Live browser verification recorded in HANDOVER per merged PR.
