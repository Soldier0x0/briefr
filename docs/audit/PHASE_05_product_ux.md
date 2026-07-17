# PHASE 5 — Product Experience, UX, UI, Design System, Accessibility & Data Presentation

*Reviewed at commit `61c686f`. Frontend: React 19 + Vite, plain JSX/CSS + Radix (ADR-003, no
Tailwind). Design system: `docs/design/design-system.md` (24 sections), `src/styles/tokens.css`
(238 tokens), `src/components/ui/*` (30 components), 50 CSS files (~20k LOC).*

> Covers the full Phase-5 sub-audit list: Product Experience · User Journey · Information
> Architecture · Navigation · UI Consistency · UX Consistency · Visual Design · Design System ·
> Component Library · Interaction/Microinteractions · Accessibility · Responsive · Empty/Loading/
> Error States · Table & Data Presentation · Forms & Inputs · Search & Filtering · Dashboard &
> Analytics · Charts & Graphs.

---

## Executive Summary

This is the **strongest area of the product**. BRIEFR has a real, documented design system — a
24-section `design-system.md` (WCAG 2.1 AA target, four-state discipline, severity/status color
semantics, motion timings, keyboard a11y, an entire §23 of "permanent repo-wide UX standards"),
238 design tokens in `tokens.css`, and a 30-component library (`AsyncState`, `EmptyState`,
`ErrorState`, `Skeleton`, `ChartShell`+`ChartDataTable`, `ReferenceTooltip`, shared
`DateTimePicker`, `DataGrid`, etc.). Accessibility is taken seriously in practice: **580 `aria-*`
usages**, correct roles (`menuitem`, `status`, `columnheader`/`cell`, `progressbar`,
`list`/`listitem`), `role="status"`/`aria-live="polite"`/`aria-busy` on async surfaces,
`role="img"`+`aria-label` on charts with a tabular `ChartDataTable` alternative, **14
`prefers-reduced-motion`** blocks, **69 media queries**, and **zero hardcoded hex colors in JSX**.
The four-states contract is centralized in `AsyncState`, and UX contracts are encoded as
"gate tests."

The weaknesses are **consistency-at-scale and migration-in-flight**, not absence of a system:
(1) an **in-progress token migration** — `design-system.md` A2 admits `tokens.css` supersedes an
ad-hoc `App.css` token block but legacy aliases (`--red`, `--bg2`, `--text3`) "remain until
migration completes"; (2) heavy **inline-style sprawl** — 436 `style={{…}}` blocks, only ~137
using `var(--token)`, so ~68% embed raw values that bypass the system; (3) **typography tokens are
under-used** — 682 raw `font-size` declarations vs 197 token-based (~78% bypass the type scale);
(4) the **light theme is not actually shipped** (A3: `light-theme.css` exists but is not imported)
despite 36 theme references; (5) the **icon strategy is unresolved** (Open-Q3) — `lucide-react` is
a dependency yet inline SVGs persist; (6) the excellent gate-tests that would enforce all of this
**don't run in CI** (Phase 4 F4.2); (7) `AsyncState`'s error surfacing depends on the caller
passing `empty` correctly, so a first-load error without `empty=true` renders an empty body
instead of the error.

**Overall Score: 8 / 10** — the highest-scoring phase so far; the gaps are polish and consistency
enforcement, not foundational design failure.

---

## Findings

### F5.1 — Inline-style sprawl bypasses the token system (436 blocks, ~68% raw values) · Priority: MEDIUM · Architectural
- **Location:** frontend-wide — 436 `style={{…}}` occurrences across `*.jsx`; only ~137 reference
  `var(--…)`. Concentrated in large components (`IOCLookup.jsx`, `App.jsx`, `DetailDrawer/*`,
  admin pages).
- **Description:** Two-thirds of inline styles embed literal values (spacing, sizes, colors as
  non-token) directly in JSX, bypassing `tokens.css` and the CSS layer. This is the classic route
  by which a token system erodes: values drift, dark/light parity breaks, and global restyling
  becomes a find-and-replace.
- **Why it matters:** The product's competitive strength is a coherent dense terminal aesthetic;
  inline raw values are how that coherence quietly degrades over years/contributors.
- **Evidence:** `grep 'style={{'` → 436; `grep 'style={{...var(--'` → 137.
- **Risk:** Visual drift, broken theming, high restyle cost.
- **Recommended solution:** (a) Add a lint rule (stylelint for CSS + an ESLint rule/gate test) that
  flags inline `style` with literal color/size values, allowing only `var(--…)` and layout-dynamic
  values (computed widths, transforms). (b) Migrate the worst offenders (large components) to CSS
  classes/token vars. (c) Encode as a gate test so new raw inline styles fail CI (once F4.2 lands).
- **Acceptance criteria:** Inline styles contain only dynamic/computed values or `var(--…)`; a new
  raw-color inline style fails the gate.
- **Effort:** Medium (incremental). **Type:** Architectural.

### F5.2 — Typography tokens under-used (682 raw `font-size` vs 197 token-based) · Priority: MEDIUM · Quick Win
- **Location:** 50 CSS files; `tokens.css` defines a type scale (`--font-size-title`, …) but ~78%
  of `font-size` declarations use raw px/rem.
- **Description:** The type scale exists but isn't the source of truth in practice, producing
  inconsistent text sizing and undermining the "density over decoration" typographic rhythm.
- **Why it matters:** Inconsistent type scale is the most visible form of UI inconsistency and the
  easiest to regress.
- **Recommended solution:** Define the full type scale as tokens (title/body/label/mono sizes +
  line-heights), codemod raw `font-size` values to the nearest token, and add a stylelint rule
  banning raw `font-size` outside `tokens.css`.
- **Acceptance criteria:** All `font-size` outside `tokens.css` use `var(--font-size-*)`; stylelint
  enforces it.
- **Effort:** Quick Win–Medium (codemod). **Type:** Quick Win.

### F5.3 — Token migration is mid-flight (dual token systems: legacy aliases + `tokens.css`) · Priority: MEDIUM · Architectural
- **Location:** `docs/design/design-system.md` §21 A2 (legacy raw names `--red`, `--bg2`,
  `--text3` "remain as aliases until migration completes, then are removed"; "Open: exact
  alias-removal cut-line per component"); `App.css` (610 LOC) still carries an ad-hoc token block.
- **Description:** The system is self-aware that it's mid-migration from `App.css` ad-hoc tokens to
  `tokens.css`. Two naming systems coexist with no completion criteria per component.
- **Why it matters:** Dual token vocabularies mean contributors pick either, indefinitely — the
  migration never finishes without a forcing function, and F5.1/F5.2 keep recurring.
- **Recommended solution:** Define the per-component cut-line (A2's open item) as a checklist; add a
  stylelint rule that bans the legacy alias names in new/changed files; delete aliases once the
  checklist is complete. Track as a ratchet (legacy-alias count may only decrease).
- **Acceptance criteria:** Legacy alias usage count is tracked and monotonically decreasing; new
  files may not reference legacy aliases.
- **Effort:** Medium. **Type:** Architectural.

### F5.4 — Light theme documented as a parity target but not shipped · Priority: LOW · Architectural
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

### F5.5 — Icon strategy unresolved: `lucide-react` dependency + persistent inline SVGs · Priority: LOW · Quick Win
- **Location:** `package.json` (`lucide-react`); design-system.md §21 Open-Q3 still lists "icon
  library choice (existing inline SVGs vs a set like Lucide)" as open; inline SVGs remain in
  components.
- **Description:** Two icon approaches coexist with no decision, risking inconsistent stroke
  weights/sizes/metaphors and unnecessary bundle weight (shipping Lucide + hand SVGs).
- **Recommended solution:** Pick one (Lucide is already a dep and tree-shakeable); migrate inline
  SVGs or remove the Lucide dependency; close Open-Q3 in the design doc.
- **Acceptance criteria:** One icon source; design-system.md Open-Q3 resolved; bundle contains one
  icon system.
- **Effort:** Quick Win–Medium. **Type:** Quick Win.

### F5.6 — `AsyncState` error surfacing depends on the caller computing `empty` correctly · Priority: MEDIUM · Quick Win
- **Location:** `src/components/ui/AsyncState.jsx` — `ErrorState` renders only when `error &&
  empty`; a set `error` with `empty=false` falls through to render `children` (the body).
- **Description:** The four-state component only shows the error UI when the caller also flags
  `empty`. On a first-load failure where the caller hasn't set `empty=true` (e.g. data is `null`,
  not an empty array, so the caller's `empty` heuristic is false), the component renders the body
  with no data and **no visible error** — a silent failure state, contradicting the CLAUDE.md rule
  that every async view needs a designed error state with the request-id.
- **Why it matters:** Silent error states are the worst UX failure — the user sees a blank/broken
  panel with no explanation or retry, and no `ref: <request-id>` to report.
- **Evidence:** the `if (error && empty)` guard in `AsyncState.jsx`; no branch for `error &&
  !empty`.
- **Recommended solution:** Show `ErrorState` whenever `error` is set **and there is no existing
  data** (stale-while-revalidate should keep old data only when data exists). Change the guard to:
  render `ErrorState` if `error && !hasData`; keep body (with a non-blocking error toast/banner)
  only when `error && hasData` (refresh failure over existing data). Add a gate test for the
  first-load-error path.
- **Acceptance criteria:** A first-load fetch error renders `ErrorState` with retry regardless of
  the `empty` flag; a refresh error over existing data keeps data + shows a non-blocking notice.
- **Effort:** Quick Win. **Type:** Quick Win.

### F5.7 — UX/design contracts are encoded as gate-tests but not enforced in CI · Priority: HIGH · Quick Win
- **Location:** 47 `*.test.js` incl. `iconOnlyAriaGate`, `nativeSelectGate`,
  `dataGridStandardGate`, `selectionAccentGate`, `activeStateGate`, `motion`, `safeExternalUrl`,
  `dateTimePickerStandardGate`; CI runs none (Phase 4 F4.2).
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

### F5.8 — Command palette vs sidebar navigation strategy is undecided (IA/navigation) · Priority: LOW · Architectural
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

### F5.9 — Contrast/type validation is aspirational (automated contrast lint not in place) · Priority: MEDIUM · Quick Win
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

### F5.10 — Data-density adherence and table presentation are strong but need a consistency gate · Priority: LOW · Quick Win
- **Location:** `DataGrid.jsx`/`DataGrid.css` (+ `@tanstack/react-table`), `dataGridStandardGate`
  test, `ChartDataTable`, CLAUDE.md UI rule ("density over decoration; no narrow centered column").
- **Description:** Tables/grids are centralized and there's already a `dataGridStandardGate` — good.
  The risk is per-page bespoke tables drifting from the standard grid (some admin/detail tabs render
  their own `role="columnheader"/"cell"` markup, e.g. `IntelTab.jsx`).
- **Why it matters:** Divergent table implementations fragment sorting/keyboard/empty-state behavior
  and a11y.
- **Recommended solution:** Route tabular data through `DataGrid`/`ChartDataTable`; extend
  `dataGridStandardGate` to flag ad-hoc `role="columnheader"` outside the standard components.
- **Acceptance criteria:** All data tables use the shared grid or an explicitly-allowlisted
  exception; gate enforces it.
- **Effort:** Quick Win. **Type:** Quick Win.

### F5.11 — Every status word needs a discoverable explanation — verify coverage · Priority: LOW · Quick Win
- **Location:** CLAUDE.md UI rule + `docs/PRODUCT.md` design principle 1 ("every status word/pill/
  badge ships with a discoverable explanation"); components `Pill.jsx`, `Badge.jsx`,
  `ReferenceTooltip.jsx`, `Tooltip.jsx`.
- **Description:** The system provides the tools (Tooltip/ReferenceTooltip) and the rule, but there's
  no gate proving every `Pill`/`Badge`/status word actually has an attached explanation. Given the
  density of jargon (KEV, EPSS, momentum, correlation confidence), an unexplained badge is a real UX
  gap for newer analysts.
- **Recommended solution:** Add a gate/lint that `Pill`/`Badge` for status semantics must be wrapped
  in or carry a `ReferenceTooltip`/`title`; audit existing usages.
- **Acceptance criteria:** Every status pill/badge has a discoverable explanation; gate enforces it.
- **Effort:** Quick Win. **Type:** Quick Win.

---

## Overall Score: **8 / 10**

| Sub-audit | Score | | Sub-audit | Score |
|---|---|---|---|---|
| Product Experience | 8 | | Accessibility | 8.5 |
| User Journey | 7.5 | | Responsive Design | 8 |
| Information Architecture | 7 | | Empty/Loading/Error States | 8 |
| Navigation | 7 | | Table & Data Presentation | 8 |
| UI Consistency | 7 | | Forms & Inputs | 8 |
| UX Consistency | 7.5 | | Search & Filtering | 8 |
| Visual Design | 8.5 | | Dashboard & Analytics | 8 |
| Design System | 8 | | Charts & Graphs | 8.5 |
| Component Library | 8.5 | | Interaction/Microinteractions | 8 |

## Strengths
- Real, documented 24-section design system with WCAG 2.1 AA target and a permanent repo-wide UX
  standards section (§23); 238 tokens; 30-component library.
- Serious accessibility in practice: 580 `aria-*`, correct roles, `aria-live`/`aria-busy` async
  states, accessible charts (`role="img"` + `ChartDataTable` tabular alternative), 14
  `prefers-reduced-motion`.
- Centralized four-state discipline (`AsyncState`/`EmptyState`/`ErrorState`/`Skeleton`); shared
  `DateTimePicker`/`DataGrid`; zero hardcoded hex colors in JSX; 69 responsive media queries.
- UX contracts encoded as executable gate-tests.

## Weaknesses
- Inline-style sprawl (F5.1) and under-used type tokens (F5.2) erode consistency.
- Mid-flight token migration with no cut-line (F5.3); light theme half-built (F5.4); icon strategy
  undecided (F5.5).
- Gate-tests not CI-enforced (F5.7); `AsyncState` silent-error edge (F5.6); no automated contrast
  lint (F5.9).

## Immediate Action Items
1. Fix `AsyncState` first-load-error surfacing (F5.6) — a real silent-failure UX bug.
2. Wire gate-tests into CI (F5.7) and add the contrast lint (F5.9).
3. Add stylelint bans for raw `font-size`/inline raw colors + legacy aliases (F5.1, F5.2, F5.3).

## Long-Term Recommendations
1. Complete the token migration to a cut-line and delete legacy aliases (F5.3).
2. Decide light-theme and icon strategy; close design-system open questions (F5.4, F5.5, Open-Qs).
3. Finalize the IA/navigation model (sidebar vs palette) (F5.8).
4. Route all tables through the shared grid; enforce status-word explanations (F5.10, F5.11).

## Production-Readiness Assessment (Phase 5 areas)
**Ready with polish — 8/10.** This is production-grade product design: the system, accessibility
posture, and component library exceed the bar for most self-hosted security tools. The blockers for
an **enterprise procurement** context are specifically: a VPAT-grade automated contrast proof (F5.9)
and CI-enforced UX gates (F5.7) so accessibility can't silently regress; the light-theme decision
(F5.4) will come up in enterprise deals. The consistency-erosion items (F5.1–F5.3) are not
launch-blocking but should be gated before the frontend doubles in size. Fix F5.6 promptly — it's a
user-facing silent-error bug, not just a consistency issue.
