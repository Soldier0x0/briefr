# PHASE 5 — Product Experience, UX, UI, Design System, Accessibility & Data Presentation

*Reviewed at pinned commit `ff23c18a4925b3b7082a2b1d1600884324d90d02`. Frontend: React 19 +
Vite, plain JSX/CSS + Radix (ADR-003, no Tailwind). Design system:
`docs/design/design-system.md` (24 sections), `src/styles/tokens.css` (semantic tokens wired from
`main.jsx`), `src/components/ui/*`, and 56 frontend unit/gate tests.*

> Covers the full Phase-5 sub-audit list: Product Experience · User Journey · Information
> Architecture · Navigation · UI Consistency · UX Consistency · Visual Design · Design System ·
> Component Library · Interaction/Microinteractions · Accessibility · Responsive · Empty/Loading/
> Error States · Table & Data Presentation · Forms & Inputs · Search & Filtering · Dashboard &
> Analytics · Charts & Graphs.

---

## Executive Summary

This remains the **strongest area of the product**. BRIEFR has a real, documented design system:
WCAG 2.1 AA targets, four-state discipline, severity/status color semantics, motion rules,
keyboard/accessibility standards, and §23 permanent repo-wide UX standards. The token layer is
explicitly wired, Radix is used without Tailwind, and UX/a11y contracts are increasingly encoded as
frontend unit/gate tests.

The refresh changes the classification more than the score. One user-facing bug is **closed**:
`AsyncState` now derives `hasData`, renders `ErrorState` on no-data errors, and has a regression
test. Icon usage also moved materially toward Lucide (27 `lucide-react` import lines vs 4 inline
`<svg>` tags). The remaining gaps are consistency-at-scale: 434 inline `style={{...}}` blocks,
only 142 with same-line token vars; 924 CSS `font-size:` declarations, only 228 via any `var(--*)`
and only 12 via the semantic `--font-size-*` scale; 1,817 legacy color/surface alias references and
224 legacy `--type-*` references; light-theme selectors exist but the light theme is still not
shipped; 56 frontend tests exist but CI still does not run `npm run test:unit`.

**Overall Score: 8.1 / 10** — production-grade UX foundation with one silent-error defect fixed;
the remaining risk is unmanaged design-system drift unless the gates become required.

---

## Findings

### F5.1 — Inline-style sprawl bypasses the token system (434 blocks, ~67% raw/unverified) · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** frontend-wide — 434 `style={{…}}` occurrences across 49 `*.jsx` files; 142
  same-line occurrences reference `var(--…)`. Concentrated in admin pages
  (`AiOperationsPage.jsx`, `OverviewPage.jsx`, `WebhooksPage.jsx`, `FeedHealthPage.jsx`) plus
  `IOCLookup.jsx` and detail surfaces.
- **Description:** Two-thirds of inline styles embed literal values (spacing, sizes, colors as
  non-token) directly in JSX, bypassing `tokens.css` and the CSS layer. This is the classic route
  by which a token system erodes: values drift, dark/light parity breaks, and global restyling
  becomes a find-and-replace.
- **Why it matters:** The product's competitive strength is a coherent dense terminal aesthetic;
  inline raw values are how that coherence quietly degrades over years/contributors.
- **Evidence:** Python scan at pinned SHA → 434 inline style blocks; 142 same-line token-var blocks;
  292 raw or unverified blocks.
- **Risk:** Visual drift, broken theming, high restyle cost.
- **Recommended solution:** (a) Add a lint rule (stylelint for CSS + an ESLint rule/gate test) that
  flags inline `style` with literal color/size values, allowing only `var(--…)` and layout-dynamic
  values (computed widths, transforms). (b) Migrate the worst offenders (large components) to CSS
  classes/token vars. (c) Encode as a gate test so new raw inline styles fail CI (once F4.2 lands).
- **Acceptance criteria:** Inline styles contain only dynamic/computed values or `var(--…)`; a new
  raw-color inline style fails the gate.
- **Effort:** Medium (incremental). **Type:** Architectural.

### F5.2 — Typography tokens under-used (924 declarations; only 12 semantic `--font-size-*`) · Status: UPDATED · Priority: MEDIUM · Quick Win
- **Location:** 48 CSS files; `tokens.css` defines the semantic type scale
  (`--font-size-title`, …), but the CSS still mostly uses raw sizes or legacy `--type-*` aliases.
- **Description:** The type scale exists but isn't the source of truth in practice, producing
  inconsistent text sizing and undermining the "density over decoration" typographic rhythm.
- **Why it matters:** Inconsistent type scale is the most visible form of UI inconsistency and the
  easiest to regress.
- **Evidence:** Python scan → 924 `font-size:` declarations; 228 use any CSS var; only 12 use
  `var(--font-size-*)`; 696 are raw/non-var. Legacy `--type-*` aliases account for most var usage.
- **Recommended solution:** Codemod raw `font-size` and legacy `--type-*` aliases to the semantic
  `--font-size-*` scale, then add a stylelint/gate rule banning raw `font-size` outside
  `tokens.css`.
- **Acceptance criteria:** All `font-size` outside `tokens.css` use `var(--font-size-*)`; stylelint
  enforces it.
- **Effort:** Quick Win–Medium (codemod). **Type:** Quick Win.

### F5.3 — Token migration is mid-flight (dual token systems: legacy aliases + `tokens.css`) · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `docs/design/design-system.md` §21 A2 (legacy raw names `--red`, `--bg2`,
  `--text3` "remain as aliases until migration completes, then are removed"; "Open: exact
  alias-removal cut-line per component"); `App.css` (610 LOC) still carries an ad-hoc token block.
- **Description:** The system is self-aware that it's mid-migration from `App.css` ad-hoc tokens to
  `tokens.css`. Two naming systems coexist with no completion criteria per component.
- **Evidence:** Current scan found 1,817 legacy color/surface alias references
  (`--red`/`--bg2`/`--text3`/etc.) plus 224 legacy `--type-*` references in `frontend/src`.
- **Why it matters:** Dual token vocabularies mean contributors pick either, indefinitely — the
  migration never finishes without a forcing function, and F5.1/F5.2 keep recurring.
- **Recommended solution:** Define the per-component cut-line (A2's open item) as a checklist; add a
  stylelint rule that bans the legacy alias names in new/changed files; delete aliases once the
  checklist is complete. Track as a ratchet (legacy-alias count may only decrease).
- **Acceptance criteria:** Legacy alias usage count is tracked and monotonically decreasing; new
  files may not reference legacy aliases.
- **Effort:** Medium. **Type:** Architectural.

### F5.4 — Light theme documented as a parity target but not shipped · Status: OPEN · Priority: LOW · Architectural
- **Location:** `src/theme/light-theme.css` exists but is **not imported** (design-system.md §21
  A3: "Light theme is a parity target, not a shipped feature"); 36 `prefers-color-scheme`/
  `data-theme` references in CSS imply theming intent.
- **Description:** The app is effectively dark-only despite theming scaffolding. Enterprise buyers
  frequently require light mode (accessibility, projector/wallboard use, corporate standards).
- **Why it matters:** "Deployed to thousands of organizations" will surface light-mode demands;
  the half-built theming is latent debt (partial `prefers-color-scheme` handling can cause
  half-themed surfaces if a user's OS is light).
- **Recommended solution:** Either (a) finish and ship the light theme (import + contrast-lint both
  themes), or (b) explicitly neutralize `prefers-color-scheme` so a light-OS user gets a
  consistent dark UI, and document dark-only as a product decision. Decide, don't leave it half-on.
- **Acceptance criteria:** Either both themes pass a contrast lint, or the app renders identically
  regardless of OS theme with a documented decision.
- **Effort:** Medium (ship) / Quick Win (neutralize). **Type:** Architectural.

### F5.5 — Icon strategy mostly converged on Lucide, but Open-Q3 remains · Status: UPDATED · Priority: LOW · Quick Win
- **Location:** `package.json` (`lucide-react`); design-system.md §21 Open-Q3 still lists "icon
  library choice (existing inline SVGs vs a set like Lucide)" as open; inline SVGs remain in a few
  components.
- **Description:** Usage has shifted strongly toward Lucide, but the design-system decision remains
  unresolved, so new contributors still see two valid-looking approaches.
- **Evidence:** Current scan → 27 `lucide-react` import lines; 4 inline `<svg>` tags.
- **Recommended solution:** Declare Lucide the default icon source, allowlist custom SVGs only for
  chart/sparkline/graph primitives, and close Open-Q3 in the design doc.
- **Acceptance criteria:** One icon source; design-system.md Open-Q3 resolved; bundle contains one
  icon system.
- **Effort:** Quick Win–Medium. **Type:** Quick Win.

### F5.7 — UX/design contracts are encoded as gate-tests but not enforced in CI · Status: UPDATED · Priority: HIGH · Quick Win
- **Location:** 56 `*.test.js` incl. `iconOnlyAriaGate`, `nativeSelectGate`,
  `dataGridStandardGate`, `selectionAccentGate`, `activeStateGate`, `motion`, `safeExternalUrl`,
  `dateTimePickerStandardGate`, and `AsyncState.test.js`; CI runs none (Phase 4 F4.2).
- **Description:** The single most effective mechanism this team built to keep UI/UX/a11y
  consistent — executable design-system gates — provides zero automated protection because CI
  doesn't run them. Every consistency finding above (F5.1–F5.5) is exactly what these gates are
  meant to catch.
- **Why it matters:** Without CI enforcement, the design system's consistency depends on reviewer
  memory; the gates rot.
- **Recommended solution:** Wire `npm run test:unit` into CI as a required job (Phase 4 F4.2), then
  extend the gate suite with the new rules from F5.1/F5.2/F5.3/F5.6.
- **Acceptance criteria:** All gate tests run and are required on PRs.
- **Effort:** Quick Win. **Type:** Quick Win.

### F5.8 — Command palette vs sidebar navigation strategy is undecided (IA/navigation) · Status: OPEN · Priority: LOW · Architectural
- **Location:** design-system.md §21 Open-Q2 ("whether the command palette becomes the primary
  nav (affects sidebar work)"); `App.jsx` `paletteOpen` state; `Sidebar.jsx` (filters + supplementary
  data, not primary nav).
- **Description:** Information architecture has an unresolved question about whether primary
  navigation is the sidebar or the command palette. The sidebar is currently filters/supplementary,
  and top navigation lives elsewhere — the mental model isn't finalized.
- **Why it matters:** Navigation is the backbone of the user journey; an undecided primary-nav
  model produces inconsistent wayfinding as features are added.
- **Recommended solution:** Decide the primary navigation model, document it in the IA section of
  the design system, and align `Sidebar`/`Header`/palette roles to it. Resolve Open-Q2.
- **Acceptance criteria:** A documented IA/nav model; palette and sidebar have clearly distinct,
  non-overlapping roles.
- **Effort:** Medium. **Type:** Architectural.

### F5.9 — Contrast/type validation is aspirational (automated contrast lint not in place) · Status: OPEN · Priority: MEDIUM · Quick Win
- **Location:** design-system.md §21 Open-Q1 ("final `--text-muted` value validated by an automated
  contrast lint") — implies the contrast lint does not yet exist; §4 targets WCAG 2.1 AA.
- **Description:** The design system commits to WCAG 2.1 AA and even annotates `--text-muted` as
  "AA-guaranteed," but there's no automated check proving token combinations meet contrast ratios,
  so a token tweak could silently drop below AA.
- **Why it matters:** Accessibility compliance is a hard enterprise/procurement requirement (VPAT);
  "AA by inspection" doesn't survive audits or token changes.
- **Recommended solution:** Add an automated contrast test (compute WCAG contrast for every
  text-on-background token pair; fail below 4.5:1 body / 3:1 large). Run in CI. Produces evidence
  for a VPAT (Phase 11).
- **Acceptance criteria:** CI fails if any documented text/background token pair drops below AA.
- **Effort:** Quick Win. **Type:** Quick Win.

### F5.10 — Data-density adherence and table presentation are strong but need a consistency gate · Status: UPDATED · Priority: LOW · Quick Win
- **Location:** `DataGrid.jsx`/`DataGrid.css` (+ `@tanstack/react-table`), `dataGridStandardGate`
  test, `ChartDataTable`, CLAUDE.md UI rule ("density over decoration; no narrow centered column").
- **Description:** Tables/grids are more centralized and there's already a `dataGridStandardGate`.
  The risk is per-page bespoke table/grid markup drifting from the standard grid; the current gate
  checks `DataGrid.css` quality but does not yet ban ad-hoc tabular roles outside allowlisted
  components.
- **Why it matters:** Divergent table implementations fragment sorting/keyboard/empty-state behavior
  and a11y.
- **Recommended solution:** Route tabular data through `DataGrid`/`ChartDataTable`; extend
  `dataGridStandardGate` to flag ad-hoc `role="columnheader"` outside the standard components.
- **Acceptance criteria:** All data tables use the shared grid or an explicitly-allowlisted
  exception; gate enforces it.
- **Effort:** Quick Win. **Type:** Quick Win.

### F5.11 — Every status word needs a discoverable explanation — verify coverage · Status: UPDATED · Priority: LOW · Quick Win
- **Location:** CLAUDE.md UI rule + `docs/PRODUCT.md` design principle 1 ("every status word/pill/
  badge ships with a discoverable explanation"); components `Pill.jsx`, `Badge.jsx`,
  `ReferenceTooltip.jsx`, `Tooltip.jsx`.
- **Description:** The system provides the tools (Tooltip/ReferenceTooltip) and now has
  `domainTermTips.test.js` coverage for key jargon/rate-limit bucket explanations, but there's no
  generic gate proving every `Pill`/`Badge`/status word carries or links to an explanation.
- **Recommended solution:** Add a gate/lint that `Pill`/`Badge` for status semantics must be wrapped
  in or carry a `ReferenceTooltip`/`title`; audit existing usages.
- **Acceptance criteria:** Every status pill/badge has a discoverable explanation; gate enforces it.
- **Effort:** Quick Win. **Type:** Quick Win.

---

## Status Table

| ID | Status | Note |
|---|---|---|
| F5.1 | UPDATED | Inline-style count refreshed: 434 total / 142 same-line token-var. |
| F5.2 | UPDATED | Font-size count refreshed: 924 total / 12 semantic `--font-size-*`. |
| F5.3 | UPDATED | Legacy alias refs measured: 1,817 color/surface + 224 `--type-*`. |
| F5.4 | OPEN | Light theme remains a parity target, not a shipped/imported feature. |
| F5.5 | UPDATED | Lucide adoption is high, but Open-Q3 remains unresolved. |
| F5.6 | CLOSED | `AsyncState` no-data error path fixed and tested. |
| F5.7 | UPDATED | 56 frontend tests exist; CI still omits `npm run test:unit`. |
| F5.8 | OPEN | IA/nav Open-Q2 remains. |
| F5.9 | OPEN | No automated contrast lint found. |
| F5.10 | UPDATED | Shared grid/gate improved, but ad-hoc table-role gate is incomplete. |
| F5.11 | UPDATED | Jargon tips improved; generic status/pill explanation gate missing. |

## Overall Score: **8.1 / 10**

| Sub-audit | Score | | Sub-audit | Score |
|---|---|---|---|---|
| Product Experience | 8.2 | | Accessibility | 8.6 |
| User Journey | 7.5 | | Responsive Design | 8 |
| Information Architecture | 7 | | Empty/Loading/Error States | 8.7 |
| Navigation | 7 | | Table & Data Presentation | 8 |
| UI Consistency | 7 | | Forms & Inputs | 8 |
| UX Consistency | 7.5 | | Search & Filtering | 8 |
| Visual Design | 8.5 | | Dashboard & Analytics | 8 |
| Design System | 8 | | Charts & Graphs | 8.5 |
| Component Library | 8.5 | | Interaction/Microinteractions | 8 |

## Strengths
- Real, documented 24-section design system with WCAG 2.1 AA target and a permanent repo-wide UX
  standards section (§23); semantic tokens wired; Radix primitives without Tailwind.
- Serious accessibility in practice: 580 `aria-*`, correct roles, `aria-live`/`aria-busy` async
  states, accessible charts (`role="img"` + `ChartDataTable` tabular alternative), 14
  `prefers-reduced-motion`.
- Centralized four-state discipline (`AsyncState`/`EmptyState`/`ErrorState`/`Skeleton`) with the
  prior no-data error bug fixed; shared `DateTimePicker`/`DataGrid`.
- UX contracts encoded as 56 executable frontend unit/gate tests.

## Weaknesses
- Inline-style sprawl (F5.1) and under-used type tokens (F5.2) erode consistency.
- Mid-flight token migration with no cut-line (F5.3); light theme half-built (F5.4); icon strategy
  undecided (F5.5).
- Gate-tests not CI-enforced (F5.7); no automated contrast lint (F5.9); status explanation coverage
  still lacks a generic enforcement gate (F5.11).

## Immediate Action Items
1. Wire `npm run test:unit` into CI so existing gate tests protect the product (F5.7).
2. Add a contrast lint for documented token pairings (F5.9).
3. Add stylelint/gate bans for raw `font-size`, raw inline style values, and legacy aliases
   (F5.1, F5.2, F5.3).

## Long-Term Recommendations
1. Complete the token migration to a cut-line and delete legacy aliases (F5.3).
2. Decide light-theme and icon strategy; close design-system open questions (F5.4, F5.5, Open-Qs).
3. Finalize the IA/navigation model (sidebar vs palette) (F5.8).
4. Route all tables through the shared grid; enforce status-word explanations (F5.10, F5.11).

## Production-Readiness Assessment (Phase 5 areas)
**Ready with polish — 8.1/10.** This is production-grade product design: the system, accessibility
posture, and component library exceed the bar for most self-hosted security tools. The blockers for
an **enterprise procurement** context are specifically: a VPAT-grade automated contrast proof (F5.9)
and CI-enforced UX gates (F5.7) so accessibility can't silently regress; the light-theme decision
(F5.4) will come up in enterprise deals. The consistency-erosion items (F5.1–F5.3) are not
launch-blocking but should be gated before the frontend doubles in size.

## Resolved since last audit

### F5.6 — `AsyncState` no-data errors now surface correctly · Status: CLOSED · Priority: MEDIUM · Quick Win
- **Location:** `src/components/ui/AsyncState.jsx`; `src/components/ui/AsyncState.test.js`.
- **Description:** The prior silent-error path is fixed. `AsyncState` now derives `hasData`, renders
  `ErrorState` for `error && !hasData`, and keeps stale data with a compact non-blocking
  `ErrorState` for refresh failures.
- **Why it matters:** First-load fetch failures now render a designed error state instead of an
  empty body.
- **Evidence:** `AsyncState.test.js` asserts the old `if (error && empty)` guard is gone, checks
  `error && !hasData`, and verifies the compact refresh-error notice.
- **Recommended solution:** None for this finding; keep the regression test in the CI gate tracked
  by F5.7.
- **Acceptance criteria:** Met.
- **Effort:** Complete. **Type:** Quick Win.
