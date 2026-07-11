# Forge Redesign — IA, Hunt Pack Library & Live-Data Completeness

**Status:** Plan of record — **no implementation in this document**
**Date:** 2026-07-11
**Audit basis:** Direct trace of `frontend/src/components/Forge.jsx` (1084 lines),
`Forge.css`, `routers/forge.py`, `routers/detection_backlog.py`, `routers/atlas.py`,
`routers/proof.py`, `hunt_packs` schema in `db/init.py`.

**Execution:** phases run per [`execution-playbook.md`](execution-playbook.md) — entry
gates, dual-DB test runs, browser verification walk, smoothness budget, dogfood loop.
A phase is complete only when merged with evidence in the PR body.

**Naming decision:** Forge keeps its name. The problems below are information
architecture, not vocabulary; API paths (`/api/forge/*`, `/api/hunt-packs/*`) and code
identifiers never change. If the header label still bothers anyone after FR-2 ships, a
label-only change (e.g. DETECT) is a one-line follow-up — explicitly out of scope here.

---

## 1. Problems (all verified in code)

| # | Problem | Evidence |
|---|---------|----------|
| P1 | View state is not in the URL — no deep links, refresh resets to Coverage | `viewMode` is plain `useState('coverage')` (Forge.jsx:854); Admin solved this with `?p=` |
| P2 | Inconsistent layouts: Coverage/Scenarios get the two-column shell with Hunt Pack rail; Campaigns/Backlog are full-width and the rail vanishes — even though Backlog has "generate pack" actions whose result the user then cannot see | Forge.jsx:1012–1081 |
| P3 | Four sub-tools hidden behind small toolbar toggles; flat hierarchy inside each view; no persistent orientation | `fg-view-toggle` toolbar (Forge.jsx:936–974) |
| P4 | **Hunt packs cannot be listed or deleted.** API has only `POST /api/hunt-packs/generate` and `GET /api/hunt-packs/{technique_id}`. The `hunt_packs` table grows forever; saved work is reachable only by clicking through techniques one at a time | routers/forge.py:252,379; db/init.py:445 |
| P5 | Atlas case studies (`/api/atlas/*`) are not cross-linked from coverage rows — real-world incident context per technique exists in the DB and is not surfaced in Forge | routers/atlas.py; no atlas reference in Forge.jsx |

---

## 2. Target information architecture

Adopt the same three-panel shell as Admin and the planned Security Architecture module
(`threat-modeling-security-architecture.md` §3) — **Forge, Admin, and ARCH become one
design language.**

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Header — tab FORGE active                                                │
├─────────────┬──────────────────────────────────────┬─────────────────────┤
│ Left rail   │ Center workspace                     │ Hunt Pack rail      │
│ 220px       │ flex 1                               │ 320px, persistent   │
│             │                                      │ across ALL views    │
│ Coverage    │ (view content)                       │                     │
│ Scenarios   │                                      │ Selected technique/ │
│ Campaigns   │                                      │ pack detail, proof  │
│ Backlog     │                                      │ runner, save/delete │
│ Library ★   │                                      │                     │
│ ─────────   │                                      │                     │
│ gap/comm/   │                                      │                     │
│ yours counts│                                      │                     │
└─────────────┴──────────────────────────────────────┴─────────────────────┘
```

- **Left rail:** five sections (Library is new) + the gap/community/yours coverage
  counts always visible as posture, not buried in a toolbar. MY STACK ONLY toggle lives
  here too — it applies to every view.
- **URL state:** `?view=coverage|scenarios|campaigns|backlog|library`
  (+ `&technique=`, `&pack=` for selection). Deep-linkable, bookmarkable, matches the
  Admin `?p=` pattern. Command palette gains one entry per view.
- **Hunt Pack rail is persistent in every view** (fixes P2): generating a pack from
  Backlog or Scenarios shows the result in place — no view switch, no lost context.
  Collapsible; `Escape` closes overlay below 1280px (same breakpoints as ARCH spec §3.1).
- Responsive/motion/CSS rules: identical to ARCH spec §3.1/§6 — `--fg-*` tokens mirror
  `--admin-*`, no new palette, 120–180ms ease-out, `prefers-reduced-motion` respected.

Component split (fixes the 1084-line monolith): `Forge.jsx` becomes a shell;
each view moves to `frontend/src/components/forge/` (CoverageView, ScenariosView,
CampaignsView, BacklogView, LibraryView, HuntPackRail). Behavior-preserving move —
same fetch logic, same endpoints.

---

## 3. Hunt Pack Library (new — the P4 fix)

**Placement decision:** generation, viewing, and deletion all live **in Forge**. Hunt
packs are analyst work products; Admin is operator configuration. No admin surface is
added. (Rejected: "saved packs page under Admin" — splits the analyst workflow across
two pages, which is the exact pivot friction this redesign removes.)

### 3.1 Library view

`AdminDataGrid`-style table over the existing `hunt_packs` table:

Columns: Technique, CVE, Title, Priority, KEV (from joined `cves.is_kev`), Created,
Updated. Sort by updated; filter by technique/priority/KEV; text search on title.

Row click → pack opens in the Hunt Pack rail (same renderer as everywhere else: Sigma,
SIEM queries, log patterns, notes, proof runner).

Row actions: **Export** (existing download paths), **Delete** (confirm dialog; hard
delete of the row — packs are regenerable from templates, soft-delete is unnecessary).

### 3.2 API additions (additive only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/hunt-packs` | List saved packs (paginated; filter `technique_id`, `cve_id`, `priority`, `q`) |
| DELETE | `/api/hunt-packs/{id}` | Delete one pack; 404 if missing; writes an `audit_log` entry (`hunt_pack_deleted`, technique+CVE in detail) |

Existing `generate` and `GET /{technique_id}` are untouched. Session auth, default rate
bucket, ORJSON — same as the rest of the router.

The audit entry means deletions appear in the ARCH module's Review History merge for
free (`threat-modeling-security-architecture.md` §5.14).

---

## 4. Live-data completeness (nothing recent goes to waste)

Checked against the current DB/API surface; only items with existing data are included:

| Data (already shipping) | Forge surface (new) |
|--------------------------|---------------------|
| Atlas case studies (`/api/atlas/casestudies`, `/api/case-studies/*`) | Coverage row + Hunt Pack rail show "Case studies (n)" chip per technique → drawer/atlas link. Real-world incident context next to detection status (fixes P5) |
| Notifications v2 (server-backed, PR #448-era) | New KEV backlog item for the user's stack emits an in-app notification deep-linking to `?view=backlog`. One scheduler-side emit at backlog refresh — no request-path work |
| Proof runner (`/api/proof/run`) | Unchanged, but now reachable in every view via the persistent rail |
| `cves.cwe_ids` / `epss_score` (already selected by generate) | Shown on Library rows and pack detail header — no extra queries |
| jsPDF 4.x + `utils/exportCommon.js` branding (already shipping, dynamically imported) | **Export pack as PDF** from the rail and Library: Sigma, SIEM queries, log patterns, notes, CVE/KEV context — new `utils/huntPackPdf.js` on the existing `pdfReport.js` pattern. No new dependency |

Deliberately excluded: ThreatFox IOC feed and watchlists (world-intel, belongs in
IOC/Feed views); typography prefs (global, not Forge's concern).

---

## 5. Implementation phases

### FR-1 — Hunt pack list + delete API
- `GET /api/hunt-packs`, `DELETE /api/hunt-packs/{id}` + audit entry
- Tests alongside existing forge router tests; run default suite **and** with
  `DATABASE_URL` pointing at Postgres (db-layer change — CLAUDE.md danger zone 1)
- Acceptance: pytest green both ways; deleting a pack writes the audit row

### FR-2 — Shell + URL state + Library view
- Three-panel shell, left rail, `?view=` routing, component split
- Library grid wired to FR-1 endpoints; delete confirm; export
- Persistent Hunt Pack rail across all five views
- Acceptance: `npm run build`; refresh preserves view + selection; generate-from-backlog
  shows pack in rail without leaving Backlog; browser-verified at 375/960/1280px

### FR-3 — Live-data enrichment + PDF export
- Case-study chips on coverage rows + rail
- KEV backlog notification emit (scheduler-side)
- CWE/EPSS on Library rows
- `utils/huntPackPdf.js` — pack export via existing jsPDF/`exportCommon.js` path
- Acceptance: technique with case studies shows chip with count; new backlog item
  produces a notification linking to `?view=backlog`; exported pack PDF opens with
  Sigma + queries + branding footer intact

**Docs (same PRs):** `API_REFERENCE.md` (FR-1), `PRODUCT_STATUS.md` + `SYSTEM_DESIGN.md`
(FR-2/FR-3), per CLAUDE.md docs rules.

**Ordering:** FR-1 → FR-2 → FR-3, no parallelization (FR-2 touches everything FR-3
extends). Forge redesign has priority over ARCH implementation phases if scheduling
conflicts arise — Forge is daily-workflow, ARCH is governance.

---

## 6. Acceptance criteria (program complete)

1. Every Forge view deep-linkable via `?view=`; refresh never loses state
2. Hunt Pack rail visible and functional in all five views
3. Saved packs listable, searchable, deletable (with confirm + audit entry) in Library
4. No admin surface added or changed
5. Coverage counts + stack toggle visible in every view (left rail)
6. Case-study context visible per technique where data exists
7. Side-by-side with Admin: indistinguishable design language
8. `cd backend && pytest tests/ -q` green (SQLite and Postgres), `npm run build` green,
   browser verification of P1–P5 fixes

---

## 7. Related documents

| Doc | Relationship |
|-----|--------------|
| [`threat-modeling-security-architecture.md`](threat-modeling-security-architecture.md) | Shared three-panel shell pattern; audit-log merge consumes pack deletions |
| `docs/PRODUCT_STATUS.md` | Update in FR-2/FR-3 PRs |
| `docs/API_REFERENCE.md` | Update in FR-1 PR |
