# Detail Drawer + Forge + Shell UX RCA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status (2026-07-21):** **EXECUTED** on branch `cursor/ux-rca-drawer-forge-shell-86fc` (PR #729). Tasks 1–9 implemented; merge when `./scripts/verify-local.sh` is green.

**Goal:** Fix 23 reported UX defects and their codebase-wide sibling instances by repairing shared root classes (not one-screen patches).

**Architecture:** Five sequential PRs. PR-A owns DetailDrawer + shared keyboard/hover/panel chrome (including keep-mounted drawer tabs). PR-B owns display label SSOT. PR-C owns pulse aggregation. PR-D owns Forge + personalization honesty. PR-E owns app-shell history. Every PR finishes with its class sweep checklist. Do not parallelize DetailDrawer edits.

**Tech Stack:** React 19 + Vite frontend (`frontend/`), FastAPI backend (`backend/`), existing design tokens (`frontend/src/styles/tokens.css`), design SSOT (`docs/design/design-system.md` §23).

## Codebase freshness (no graphify)

- **Do not use `graphify` / `graphify-out/` for this work.** The graph is stale by dozens of PRs; treat it as absent.
- **RCA source of truth:** live files on `origin/main` (verified by `git show origin/main:<path>`), plus recent merged PR list via `gh`.
- **Baseline when this freshness pass ran:** `origin/main` at `b372581e` — `feat(secarch): precise self-stack Risk Register matching via CPE (#728)` (2026-07-21 ~03:36 UTC). Planning workspace was **9 commits behind** at check time; DetailDrawer / Forge / `pulse_families` / `campaignClusterOpen` / drawer keyboard handler **anchors unchanged** vs that tip.
- **Concurrent main activity (do not fight):** Program 2 self-stack / secarch (#728 and follow-ons), admin verify-local gate (#727), Waves 1–7 durable jobs / catchup / FEED hybrid (#720–#726). Open PRs at check time: none.
- **Before any execution:** `git fetch origin && git checkout main && git pull origin main`, then re-grep the RCA anchors in §“Anchor re-verify”. If another PR touched the same files, rebase the plan task file list and re-confirm line-level hooks.

### Recent PRs that affect this plan’s sweep (not the core drawer RCAs)

| PR | Relevance |
|---|---|
| **#723** FEED hybrid technique/campaign hits | **New sibling surfaces:** `CVEFeed.jsx` `SemanticCampaignRow` / `SemanticTechniqueRow` — apply `formatIntelLabel` to campaign `label`; technique names wrap/title; campaign click → `openForgeCampaigns` (history C13). Section labels already without `//`. |
| **#725** FE dead-code | No DetailDrawer/Forge path hits in PR file filter; still re-check after pull. |
| **#710** Phase 1 leftovers / IOCLookup extract | C15 `//` heading strip must follow **current** IOC file paths after pull. |
| **#727–#728** admin gate + secarch CPE | Orthogonal to drawer UX; may churn `PRODUCT_STATUS` / `HANDOVER` / verify-local — merge carefully, don’t overwrite their docs entries. |
| **#720–#722, #724, #726** durable jobs / catchup | Admin/shell only; no change to issues 1–23 RCAs. |

## Global Constraints

- **Planning freeze:** no code/impl/commits from this plan until explicit execute + fresh pull.
- Never hardcode colors/spacing — semantic tokens only (`--accent-*`, `--border-active`, `--type-*`, `--motion-*`).
- Red/`--danger` only for destructive, critical severity, error — not links, selection, or primary actions.
- Accent ghost actions: accent **text**, quiet border; hover uses `--border-active` (not full-strength accent box). Includes `.drawer-gn-load-btn` (today hover sets `border-color: var(--accent)`).
- Animate only `transform`/`opacity`; honor `prefers-reduced-motion` and `data-motion`.
- Headings: uppercase mono, **no** `//` prefix (product-wide analyst titles). Empty/loading lines may keep `//`.
- Do not store secrets, tokens, markdown reports, or IOC payloads in localStorage/sessionStorage.
- Drawer UI chrome: keep-mounted `hidden` panels; reset on CVE change/close — not user_preferences.
- Postgres-native SQL when touching `db/`; run default + Postgres pytest for `db/`/`correlation/` changes.
- Merge gate: `./scripts/verify-local.sh` (restored by #727 — still the gate).
- Docs: runtime behavior → `docs/PRODUCT_STATUS.md`; API shape → `docs/API_REFERENCE.md`; prepend `docs/HANDOVER.md` (do not rewrite concurrent-session entries).
- **Never regenerate or trust graphify for orientation on this track.**

---

## RCA summary (root classes — fix these)

| ID | Class | Symptom examples | Shared fix locus |
|---|---|---|---|
| C1 | Ad-hoc expand + shortcuts + sticky hover | Campaigns auto-open; Ctrl+C steals selection; sticky `:hover` | `keyboardScope.js`; expand default=closed; `useClearPointerStateOnHide` |
| C2 | Under-accented / wrong-accent chrome | Muted Pin/Investigate; red CVE links; GreyNoise full accent border | Accent-ghost tokens; `--text-link`; soft `--border-active` |
| C3 | Raw feed strings | `Known_Cve` | `formatIntelLabel.js` |
| C4 | Split aggregation | Duplicate pulses in Active Campaigns | UI cluster + stronger `normalize_pulse_name` |
| C5 | Hint/empty composition | MITRE hint + empty; restating lane notes | Hint only in data state |
| C6 | Type token debt | Sub-12px corr/OTX/Detect/Forge | Remap to `--type-*` |
| C7 | Overview IA | Description buried; OP underuses width | Description → OP\|Env twin → … |
| C8 | Panel edge chrome | 4-side flat borders; uneven gutters | `.drawer-panel` L-edge |
| C9 | Missing hover presence | Boxes feel dead | Micro `scale(1.012)` on interactive panels |
| C10 | Identity truncation | Forge technique ellipsis | Wrap + `title=` |
| C11 | Dishonest primary CTAs | Generate Pack; OPEN CVEs→1 | Inventory-first; honest labels |
| C12 | Personalization theater | Campaigns “for your stack” when empty | Empty guidance / Unpersonalized badge |
| C13 | History replace-as-default | Back → login | `pushContext` vs `replaceHygiene` |
| C14 | Conditional-mount amnesia | Intel expands reset after Detect | Keep-mounted `hidden` drawer tabs |
| C15 | `//` on headings | `// ACTIVE CAMPAIGNS` | Strip headings product-wide; keep on empty/loading |

### Per-issue → class map (1–23)

| # | Issue | Class | PR |
|---|---|---|---|
| 1 | Active Campaigns expand defaults | C1 | A |
| 2 | Sources blend into background | C2/C8 | A |
| 3 | `Known_Cve` formatting | C3 | B |
| 4 | Part 1/2 meaning / missing 2/2 | C3/C4 | B/C |
| 5 | Duplicate titles / false positives | C4 | C |
| 6 | MITRE hint contradicts empty | C5 | A |
| 7 | Ctrl+C copies full markdown | C1 | A |
| 8 | Correlation strength fonts | C6 | A |
| 9 | Campaign Links CVE bunch + buttons | C2/C6 | A |
| 10 | Sticky hover after tab switch | C1 | A |
| 11 | Related Incidents dead `//` note | C5 | A |
| 12 | Overview description / reading order | C7 | A |
| 13 | Pin / Investigate / Review accent text | C2 | A |
| 14 | Panel alignment / flush edges | C8 | A |
| 15 | L-edge accent borders (left+top) | C8 | A |
| 16 | Micro hover grow on boxes | C9 | A |
| 17 | Forge technique name ellipsis | C10 | D |
| 18 | Technique click → CVE list; demote Generate Pack | C11 | D |
| 19 | Campaign clusters noise without stack | C12 | D |
| 20 | OPEN CVEs opens one CVE | C11 | D |
| 21 | Browser Back loses Forge | C13 | E |
| 22 | Drawer tab state not preserved | C14 | A |
| 23 | `//` on headings unnecessary | C15 | A |

### Gaps closed in this rewrite (were under-specified)

1. **GreyNoise load button** (`.drawer-gn-load-btn`) — already accent text; hover uses full `border-color: var(--accent)` (= signature orange/red). Include in soft-border accent-ghost rules ([`DetailDrawer.css`](frontend/src/components/DetailDrawer.css) ~1077–1094).
2. **MITRE heading** uses legacy `drawer-section-label` without `mono` — migrate to `drawer-human-label mono` with peers ([`IntelTab.jsx`](frontend/src/components/DetailDrawer/IntelTab.jsx) ~872).
3. **`//` heading scope** — strip from **all analyst-facing section titles** (DetailDrawer + Morning Brief + IOC + Investigation + Shortcuts + FilterBar vendor label), not drawer-only. Empty/loading keep `//`.

### Sibling sweep (must not leave behind)

- BacklogView Generate Pack primary; Wallboard “on your stack” when global; Forge hero personalization copy
- `.ui-btn--ghost`; Investigation red CVE type chip; Sidebar/ARCH technique ellipsis
- NotificationBell / IntelTab `location.assign`; Admin `replace:true` tab switches
- Forge `viewMode` unmount (C14 sibling — fix in PR-D if low-risk, else note defer with issue link)
- Detect framing always-on; sub-12px outside corr-priority
- **FEED hybrid (#723):** `SemanticCampaignRow` labels via `formatIntelLabel`; technique row titles wrap/`title=`; Forge open from FEED uses pushContext (C13); do not claim campaign row opens all linked CVEs

### Anchor re-verify (run on `origin/main` before execute)

Confirmed still true at `b372581e` — re-run after pull:

```bash
rg -n "defaultOpen=\{items\.length" frontend/src/components/DetailDrawer/IntelTab.jsx
rg -n "e\.key === 'c'|activeTab === 'intel'" frontend/src/components/DetailDrawer/index.jsx
rg -n "replace: true" frontend/src/App.jsx | head
rg -n "openCvesLabel|ranked for your stack" frontend/src/utils/campaignClusterOpen.js frontend/src/components/forge/CampaignsView.jsx
rg -n "fg-tech-node-name|ellipsis" frontend/src/components/Forge.css
rg -n "def normalize_pulse_name" -A3 backend/correlation/pulse_families.py
rg -n "drawer-gn-load-btn:hover|border-color: var\\(--accent\\)" frontend/src/components/DetailDrawer.css
rg -n "drawer-section-label|MITRE ATT" frontend/src/components/DetailDrawer/IntelTab.jsx
rg -n "SemanticCampaignRow|feed-semantic-row-title" frontend/src/components/CVEFeed.jsx
```

---

## File map

| Area | Primary files |
|---|---|
| Drawer tabs / state | `frontend/src/components/DetailDrawer/index.jsx`, `IntelTab.jsx`, `OverviewTab.jsx`, `DetectTab.jsx`, `RelatedTab.jsx`, `DetailDrawer.css` |
| Keyboard | `frontend/src/utils/keyboardScope.js`, `keyboardScope.test.js` |
| Labels | Create `frontend/src/utils/formatIntelLabel.js` + `.test.js`; wire Intel/Forge/Wallboard/`correlationPresentation.js` |
| Aggregation | `backend/correlation/pulse_families.py`, `frontend` Active Campaigns clustering in `IntelTab.jsx` |
| Forge | `CoverageView.jsx`, `HuntPackRail.jsx`, `CampaignsView.jsx`, `BacklogView.jsx`, `campaignClusterOpen.js`, `Forge.css`, `backend/routers/forge.py` |
| Personalization copy | Create `frontend/src/utils/personalizationCopy.js` (+ test); Forge + Wallboard |
| Shell history | `frontend/src/App.jsx`, `shellUrlState.js`, Forge URL writers, `NotificationBell.jsx` |
| Design docs | `docs/design/design-system.md` §23, `docs/PRODUCT_STATUS.md`, `docs/HANDOVER.md` |

---

### Task 1: PR-A foundations — keyboardScope + pointer clear + expand default

**Files:**
- Modify: `frontend/src/utils/keyboardScope.js`
- Modify: `frontend/src/utils/keyboardScope.test.js`
- Create: `frontend/src/utils/clearPointerState.js` (+ test)
- Modify: `frontend/src/components/DetailDrawer/index.jsx` (shortcut handler)
- Modify: `frontend/src/App.jsx` (tab change clears pointer state)
- Modify: `frontend/src/components/DetailDrawer/IntelTab.jsx` (`defaultOpen={false}`)

**Interfaces:**
- Produces: `shouldIgnoreGlobalShortcut(event)` also true when `ctrlKey|metaKey|altKey` or non-collapsed selection
- Produces: `hasTextSelection()` helper
- Produces: `clearStalePointerState()` — blur activeElement if inside `[hidden]`; optional brief pointer-events nudge

- [ ] **Step 1: Extend keyboardScope tests (fail first)**

```js
// keyboardScope.test.js — add cases
it('ignores when ctrlKey set', () => {
  assert.equal(shouldIgnoreGlobalShortcut({ ctrlKey: true, key: 'c', target: null }), true)
})
it('ignores when selection non-collapsed', () => {
  // mock getSelection → { isCollapsed: false, toString: () => 'x' }
})
```

- [ ] **Step 2: Implement guards in `keyboardScope.js`; drawer `C` uses them and only fires when not ignored**

- [ ] **Step 3: `CampaignPulseGroups` `defaultOpen={false}`; audit Forge `SavedPack` — leave open-when-one unless product wants closed (document choice: SavedPack stays)**

- [ ] **Step 4: Wire `clearStalePointerState` on `selectAppTab` / activeTab change**

- [ ] **Step 5: Run `cd frontend && npm run test:unit -- keyboardScope`**

- [ ] **Step 6: Commit** `fix(ui): keyboard selection guards and closed campaign defaults`

---

### Task 2: PR-A — keep-mounted drawer tabs (issue 22 / C14)

**Files:**
- Modify: `frontend/src/components/DetailDrawer/index.jsx` (~878–971)
- Modify: `frontend/src/components/DetailDrawer.css` (per-tab scroll)

**Interfaces:**
- Each tab wrapped: `<div className="drawer-tab-panel" hidden={activeTab !== 'intel'} …>`
- Optional `visitedTabs` Set for lazy first mount (like Admin)
- Outer `key={cve_id}` remains — CVE change remounts chrome

- [ ] **Step 1: Replace `activeTab === 'x' &&` with hidden panels for overview/intel/detect/related**

- [ ] **Step 2: Give each panel its own scroll container (`overflow: auto; flex: 1; min-height: 0`)**

- [ ] **Step 3: Manual verify — expand Active Campaigns source → Detect → Intel; expands still open**

- [ ] **Step 4: Commit** `fix(drawer): preserve tab UI state with hidden panels`

---

### Task 3: PR-A — Overview IA + panel chrome (issues 12–16, 2, 8–9)

**Files:**
- Modify: `OverviewTab.jsx`, `IntelTab.jsx` (CorrelationFindings layout), `DetailDrawer.css`, `CVECard.css`
- Modify: design-system §23 note for `.drawer-panel` + accent-ghost

**Overview order (locked):**
1. DESCRIPTION  
2. Twin: Operational Priority | Environment Relevance  
3. WHY THIS MATTERS  
4. SEVERITY CONTEXT  
5. KEY SIGNALS → EXPLOITATION  
6. AFFECTED PRODUCTS  
7. REMEDIATION  
8. REFERENCES  
9. CAPEC / enrichment  

**`.drawer-panel` chrome:**
- Left: `box-shadow: var(--shadow-inset-indicator-start)`
- Top: `1px solid var(--border-active)`
- Right/bottom: none or hairline `--border-subtle`
- Interactive hover: `transform: scale(1.012)`; motion-off → no scale
- Twin row: `display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3)`; stack at narrow width
- Drop `EnvironmentTierChip` inside OP when full Environment panel is beside it

**Actions (accent ghost):** `.cve-action-btn`, `.drawer-inv-btn`, `.drawer-report-btn`, `.drawer-gn-load-btn`, `.ui-btn--ghost` — `color: var(--accent)`; border `--border2`; hover `--border-active` + ≤12% accent mix fill. Active/pinned keep current accent treatment.

**Correlation finding:**
- Members as flex-wrap chips (not inline prose)
- Foot action bar with gap + min-height 30px
- `.corr-cve-link` → `var(--text-link)` not red
- `.corr-priority-*` → `--type-meta` / `--font-size-id` / `--type-body`

- [ ] **Step 1: Implement `.drawer-panel` + twin grid + Overview reorder**

- [ ] **Step 2: Accent-ghost + GreyNoise soft border; Campaign Links restructure**

- [ ] **Step 3: `npm run build` + browser Overview/Intel**

- [ ] **Step 4: Commit** `feat(drawer): overview IA, L-edge panels, accent-ghost actions`

---

### Task 4: PR-A — copy composition + `//` headings (issues 6, 11, 23)

**Files:**
- Modify: `IntelTab.jsx` (MITRE hint gated; heading → `drawer-human-label mono`; strip `//` from headings)
- Modify: `RelatedTab.jsx` (remove Incidents restating note)
- Modify: `DetectTab.jsx`, `OverviewTab.jsx`, `DrawerAtlasSection.jsx`
- Modify: `MorningBrief.jsx`, `IOCLookup.jsx`, `InvestigationPanel.jsx`, `ShortcutsPanel.jsx`, `FilterBar.jsx` (heading `//` only)
- Create: `frontend/src/utils/sectionHeading.js` — `formatSectionHeading(text)` strips leading `//`

- [ ] **Step 1: Unit test** — `formatSectionHeading('// ACTIVE CAMPAIGNS') === 'ACTIVE CAMPAIGNS'`; empty strings untouched for empty-state helpers

- [ ] **Step 2: Apply heading strip + MITRE empty composition (hint only when `techList.length > 0`)**

- [ ] **Step 3: Keep empty/loading lines with `//`

- [ ] **Step 4: Commit** `fix(ui): section headings without //; MITRE empty composition`

---

### Task 5: PR-B — formatIntelLabel SSOT (issues 3–4)

**Files:**
- Create: `frontend/src/utils/formatIntelLabel.js`, `formatIntelLabel.test.js`
- Modify: `IntelTab.jsx`, Forge campaign titles, `correlationPresentation.js`, `WallboardPage.jsx`
- Modify: `frontend/src/components/CVEFeed.jsx` — `SemanticCampaignRow` title (`campaign.label`); technique `name` display as needed

**Behavior:**
- `_` → space for display; collapse whitespace
- Parse `| Part N/M` → `{ title, part: { n, m } }` for badge + tooltip (“OTX author split; other parts may not link this CVE”)
- Raw string in `title=` attribute
- Never mutate API/DB

- [ ] **Step 1: Tests for Known_Cve, Part 1/2, trailing period titles**

- [ ] **Step 2: Implement + wire call sites (including FEED hybrid campaign labels from #723)**

- [ ] **Step 3: Commit** `feat(ui): formatIntelLabel for OTX/campaign titles`

---

### Task 6: PR-C — aggregation (issue 5)

**Files:**
- Modify: `backend/correlation/pulse_families.py` `normalize_pulse_name`
- Modify: `backend/tests/test_pulse_families.py`
- Modify: `IntelTab.jsx` within-source title clustering UI

**normalize_pulse_name matching-only:**
- lowercase, whitespace collapse
- strip `| Part N/M` (case insensitive)
- strip trailing punctuation `.!?`
- `_` → space

**UI:** cluster by normalized base title within author; primary card + “N related pulses”; optional “also seen from …” cross-source meta. Do not change Jaccard threshold.

- [ ] **Step 1: Failing tests for Part/punctuation/`_` name identity**

- [ ] **Step 2: Implement normalize + UI cluster**

- [ ] **Step 3: `cd backend && pytest tests/test_pulse_families.py -q` (and Postgres path if DATABASE_URL available)**

- [ ] **Step 4: Commit** `fix(correlation): stronger pulse name normalize + campaign UI clusters`

---

### Task 7: PR-D — Forge navigator + campaigns (issues 17–20)

**Files:**
- Modify: `Forge.css` (wrap `.fg-tech-node-name`)
- Modify: `backend/routers/forge.py` — `linked_cves` add `description` (truncate ~180), `linked_cve_total`
- Modify: `HuntPackRail.jsx` — inventory rows; remove Generate Pack primary
- Modify: `BacklogView.jsx` — demote Generate Pack similarly
- Modify: `CampaignsView.jsx`, `campaignClusterOpen.js`
- Create: `frontend/src/utils/personalizationCopy.js` (+ test)
- Modify: `WallboardPage.jsx` empty coverage copy; Forge hero copy

**Campaigns when stack+pins empty:** guidance empty state; optional “Browse global (unpersonalized)” — never “ranked for your stack”.

**OPEN CVEs:** replace with member inventory + singular “Open CVE” if needed.

- [ ] **Step 1: CSS wrap technique names; API description + total; FE inventory UI**

- [ ] **Step 2: personalizationCopy + Campaigns empty-stack honesty**

- [ ] **Step 3: Update `docs/API_REFERENCE.md` + `PRODUCT_STATUS.md`**

- [ ] **Step 4: Commit** `fix(forge): technique wrap, CVE inventory, honest campaigns`

---

### Task 8: PR-E — shell history SSOT (issue 21)

**Files:**
- Create: `frontend/src/utils/navHistory.js` (+ test) — `pushContext(setSearchParams, mutator)` vs `replaceHygiene(...)`
- Modify: `App.jsx` `selectAppTab` / `openCve` → push for tab + Forge→CVE
- Modify: `App.jsx` `openForgeTechnique` / `openForgeCampaigns` (FEED #723 + drawer MITRE pivots) — align on pushContext
- Modify: Forge URL writers; Admin page switches for intentional nav
- Modify: `NotificationBell.jsx`, IntelTab forge fallback — router navigate not `location.assign`
- Optional: sync open drawer to `?cve=` while open; clear on close (Back closes drawer first)

- [ ] **Step 1: Unit tests for push vs replace helpers**

- [ ] **Step 2: Wire App/Forge/Admin/FEED→Forge pivots; kill assign pivots**

- [ ] **Step 3: Browser — Forge campaigns → Open CVE → Back returns to Forge; FEED campaign row → Forge → Back returns to FEED**

- [ ] **Step 4: Commit** `fix(nav): push context changes so Back restores Forge`

---

### Task 9: Docs + verify-local + HANDOVER

**Files:**
- Modify: `docs/PRODUCT_STATUS.md`, `docs/design/design-system.md` §23 (panel L-edge, accent-ghost, `//` rule, nav push/replace, drawer keep-mount)
- Modify: `docs/HANDOVER.md` (newest first)
- Modify: `docs/API_REFERENCE.md` if hunt-pack payload changed
- Run: `./scripts/verify-local.sh`

- [ ] **Step 1: Docs updates for operator-visible behavior**

- [ ] **Step 2: Full verify-local**

- [ ] **Step 3: Final commit** `docs: UX RCA pass status and design-system rules`

---

## Mandatory sweep checklist (run at end of each PR)

- [ ] Expand heuristics default closed where analyst inventory lists
- [ ] Shortcuts ignore modifiers + selection + `shouldIgnoreGlobalShortcut`
- [ ] Sticky hover cleared on `hidden` / tab change (CSS + JS hover + Tooltip)
- [ ] Accent-ghost on primary non-destructive actions including GreyNoise load
- [ ] No red CVE links / non-severity red chips
- [ ] `formatIntelLabel` on external pulse/campaign labels
- [ ] Hints not above empty; no restating lane notes
- [ ] No heading starts with `//`; empty/loading may
- [ ] Sub-12px literals remapped in touched CSS
- [ ] Identity labels wrap (or justified ellipsis + title)
- [ ] No Generate Pack / plural-open lies as primary CTAs
- [ ] No “for your stack” without stack
- [ ] Intentional nav uses push; hygiene uses replace; no `location.assign` pivots
- [ ] Multi-panel UIs use `hidden` not unmount when state must survive

---

## Out of scope

- Jaccard threshold / ML similarity changes
- Mutating stored OTX `pulse_name`
- Fabricating Part 2/2
- Deleting hunt-pack subsystem entirely
- Community-Sigma into Forge generate
- Opening hundreds of drawers for one cluster
- Persisting drawer chrome to localStorage / user_preferences
- Parallel DetailDrawer feature work (M1, C-Evolve-3, H2, H4)

---

## Self-review

1. **Spec coverage:** Issues 1–23 each map to a Task/PR above; GreyNoise/MITRE class/`//` shell scope gaps closed; FEED #723 siblings added to PR-B/E sweeps.
2. **Placeholder scan:** No TBD/TODO steps; concrete files and behaviors listed.
3. **Type consistency:** `formatIntelLabel`, `personalizationCopy`, `pushContext`/`replaceHygiene`, `clearStalePointerState`, `.drawer-panel` named consistently across tasks.
4. **Freshness:** Re-verified against `origin/main` `b372581e` without graphify; core RCA hooks still present; implementation blocked until explicit execute + pull.

---

## Execution handoff

**Not starting implementation now** (concurrent session on `main`; maintainer planning freeze).

When ready to execute:
1. Pull latest `main` and re-run §Anchor re-verify.
2. Choose: **Subagent-Driven** (recommended) or **Inline Execution**.
3. Do not use graphify for orientation.
