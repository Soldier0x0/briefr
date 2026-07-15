# BRIEFR Design System

**Status:** DRAFT (v0.1) — single source of truth for BRIEFR's UI.
**Last updated:** 2026-07-14
**Owners:** UI modernization working group.

**Companion documents (keep in sync):**
- Tokens: [`frontend/src/styles/tokens.css`](../../frontend/src/styles/tokens.css)
- Roadmap: [`docs/planning/ui-modernization-plan.md`](../planning/ui-modernization-plan.md)
- Rationale: [`docs/decisions/ADR-003-ui-design-system.md`](../decisions/ADR-003-ui-design-system.md)
- Approved UI libraries: [`docs/decisions/ADR-005-component-library-strategy.md`](../decisions/ADR-005-component-library-strategy.md)
- Non-UI/bug backlog: [`docs/planning/reliability-and-bug-backlog.md`](../planning/reliability-and-bug-backlog.md)
- Cursor enforcement: [`.cursor/rules/design-system.mdc`](../../.cursor/rules/design-system.mdc)
- Existing runtime tokens this consolidates: [`frontend/src/App.css`](../../frontend/src/App.css)

> This document defines **rules**, not one-off fixes. When any other UI doc, or
> the code, disagrees with this file, this file wins — except where
> `docs/PRODUCT_STATUS.md` documents shipped runtime truth, which always wins over
> planning docs.

**Finding-id legend:** `UI-*` / `UI-BUG-*` ids resolve in the roadmap's audit table
(`ui-modernization-plan.md` §2); `REL-*` ids resolve in the reliability backlog;
`E*-*` ids are roadmap tickets (plan §4).

---

## 1. Design philosophy

BRIEFR is a **dense, dark, terminal-grade analyst console** for CVE intelligence and
detection engineering. It is not a marketing surface. The system optimizes for:

1. **Signal density** — fill the width; surface more real data per screen than a
   generic SaaS dashboard. `max-width` is for prose only, never feeds/tables/dashboards.
2. **Instant triage** — severity, status, and priority must be *seen* (color + shape +
   position), not *read*.
3. **Trust** — honest states (loading / empty / degraded / error are distinct),
   discoverable explanations for every status word, and no decorative motion.
4. **Consistency** — one token layer, one primitive per pattern, one "selected" accent.
5. **Keyboard-first, accessible** — WCAG 2.1 AA minimum; every workflow reachable and
   legible.

**Anti-references (do not build):** gradients, hero-marketing sections, icon+heading+text
"feature" card grids, rainbow charts, motion for decoration.

---

## 2. Visual language

- **Aesthetic:** dark newsprint/terminal. Mono for labels, identifiers, code, and
  numeric data (`--font-mono`); DM Sans for body (`--font-body`); DM Serif Display only
  for the wordmark/display (`--font-display`).
- **Depth:** flat by default in dark theme (`--shadow-*: none`); elevation is conveyed by
  surface tokens (`--surface-raised` / `--surface-sunken`) and borders, **except**
  overlays (modals/drawers) which use `--shadow-overlay`.
- **Borders over shadows** for separation. Every distinct container gets a
  `--border-subtle`; do not rely on background contrast alone (audit finding: BRIEF stat
  cards had no borders).
- **Signature accent:** `--accent-primary` (`#e85533`, BRIEFR orange). This — not red — is the
  brand accent and the selection color.

---

## 3. Enterprise dashboard principles

1. Content fills the viewport with normal gutters (`--gutter`, 24–32px). No centered
   narrow column in a wide viewport.
2. Every table/list uses the shared `Table`/`DataGrid` primitive (see §18). No bespoke
   per-page tables (audit: ARCH shipped 11 unstyled tables + 1 good one).
3. Every async region implements all four states (§16): loading, empty, error, data.
4. Every status token ships a discoverable explanation (tooltip/legend) — a standing
   BRIEFR rule (`CLAUDE.md`, `docs/PRODUCT.md`).
5. Destructive controls live in a "Danger Zone" **below** operational content and require
   typed confirmation. Never place destructive panels at the top.
6. Charts never grow unbounded — every chart lives in a fixed-height wrapper (audit
   CRITICAL: Resources chart infinite-growth).

---

## 4. Accessibility standards (WCAG 2.1 AA minimum)

| Requirement | Rule |
|---|---|
| Text contrast | ≥ 4.5:1 for < 18px; ≥ 3:1 for ≥ 18px or bold. `--text-muted` is defined to meet this (raised from prior ~3:1 grays). |
| Non-text contrast | ≥ 3:1 for borders, focus rings, control boundaries, chart lines. |
| Focus visible | Every interactive element shows `--focus-ring` (soft accent halo via `color-mix`, not a neon 4px ring). Never remove outlines without a replacement. |
| Color independence | Severity/status never encoded by color alone — pair with label, icon, or shape. |
| Target size | ≥ `--hit-target-min` (24px); primary buttons ≥ `--control-height-md` (30px). |
| Keyboard | All controls reachable + operable; logical tab order; visible focus; no traps; Esc closes overlays and restores focus. |
| Names | Icon-only controls (bell, "…", pin, close-X) require `aria-label`. |
| Motion | Respect `prefers-reduced-motion` and the tool-wide motion toggle (§12). |
| Charts | Provide an accessible text/table fallback or `aria-label` summary. |

Target: publishable VPAT / EN 301 549 conformance for the analyst + admin shells.

---

## 5. Typography guidelines

Use the scale tokens only; **12px (`--font-size-micro`) is the absolute floor** and is for
badges/pills, never body copy.

| Token | Size | Use |
|---|---|---|
| `--font-size-title` | 20px | Page titles |
| `--font-size-id` | 18px | CVE IDs, major identifiers |
| `--font-size-heading` | 15px | Section headings |
| `--font-size-subheading` | 14px | Card/panel titles |
| `--font-size-body` | 14px | Body |
| `--font-size-secondary` | 13px | Secondary copy |
| `--font-size-meta` | 13px | Timestamps, labels |
| `--font-size-micro` | 12px | Badges/pills only |

Weights: `--font-weight-regular/medium/semibold/bold`. Admin and analyst shells share this
scale (audit: admin previously felt denser/smaller — must not diverge). Table headers use
`--font-weight-semibold` + `--text-secondary` to establish hierarchy over data rows.

---

## 6. Color usage guidelines

- Consume **semantic tokens only** (`--text-*`, `--surface-*`, `--severity-*`,
  `--status-*`, `--accent-*`). Never raw hex, never the `--c-*` primitives directly.
- **Red is reserved** for `--danger` (destructive actions) and `--severity-critical` /
  `--status-error`. It must **not** be used for neutral selection, plain links, or neutral
  toggles (audit UI-3, plan ticket E4-2: red CVE links in Campaign Links, red "UTC" toggle, red radios).
- **Selection/active = `--accent-selected`** everywhere (nav tabs, sidebar items, filter
  chips, selected rows, selected radios). Exactly one visual language for "current."

---

## 7. Severity color semantics (CVSS / risk)

| Level | Token | Foreground | Surface |
|---|---|---|---|
| Critical | `--severity-critical` | red | `--severity-critical-bg` |
| High | `--severity-high` | amber | `--severity-high-bg` |
| Medium | `--severity-medium` | yellow | `--severity-medium-bg` |
| Low | `--severity-low` | green | `--severity-low-bg` |
| None/Unknown | `--severity-none` | slate | `--severity-none-bg` |

Rules:
- Hues are chosen for **at-a-glance separation** (audit: critical vs high badges were too
  close). Do not narrow the palette.
- **Cards carry a 3–4px left accent** in the severity color (`border-left`) in addition to
  the badge, so severity is seen before reading the number (audit UI-5, plan ticket E4-3).
- Never map EPSS "increasing" to green in a way that reads as "good" — use a directional
  arrow + `--status-warning` semantics (audit UI-21).

---

## 8. Status color semantics (health / ops)

| State | Token | Use |
|---|---|---|
| Success/OK | `--status-success` | healthy feed, job OK, circuit closed |
| Warning | `--status-warning` | degraded, needs attention, approaching limit |
| Error | `--status-error` | failed job, tripped circuit, unhealthy webhook, **high failure rate** |
| Info | `--status-info` | informational/neutral notices |
| Neutral | `--status-neutral` | disabled/unknown |

A **high failure metric must render as `--status-error`**, not muted gray (backlog REL-6,
plan ticket E9-1: a 91% LLM fail rate was dim gray). Status pills always ship a
tooltip/legend (§3.4).

---

## 9. Spacing system

4px base scale `--space-0…--space-8` (0/4/8/12/16/24/32/48/64). Page gutter `--gutter`.
Rules: consistent internal card padding (`--space-4`), consistent gaps between controls
(`--space-2`) and cards (`--space-4/5`); never let controls touch or text butt against
edges (audit UI-14, plan ticket E7-4: cramped FEED filter panel). Group related filters with a
`--border-subtle` divider.

## 10. Border radius system

`--radius-none/sm(4)/md(6)/lg(10)/pill`. Inputs/buttons/chips = `--radius-sm`; cards/panels
= `--radius-md`; modals/large surfaces = `--radius-lg`; badges/avatars = `--radius-pill`.
One radius per component category — no ad-hoc values.

## 11. Elevation / shadow system

Dark theme is flat (`--shadow-*: none`); separation via borders + surface tokens. Overlays
(modal/drawer/popover) always use `--shadow-overlay`. Light theme adds `--shadow-sm/md/lg`.

## 12. Motion guidelines & animation timings

- Durations: `--motion-fast` (120ms, hovers/toggles), `--motion-normal` (160ms, most
  transitions), `--motion-slow` (220ms, drawer/modal only). Easing `--ease-standard`
  (ease-out) by default.
- **Animate only `transform` and `opacity`** (GPU-friendly). Never animate `width/height/
  top/left` for layout; never infinite/decorative loops.
- **Tool-wide motion toggle** (`data-motion` on `<html>`), default **ON**, honoring
  `prefers-reduced-motion`, persisted in `user_preferences`. `off` sets all
  `--motion-*` to 0ms and disables Radix/CSS animations globally (spec in `tokens.css`).
  Consolidate the existing partial "motion" toggle on the Display page into this one.
- Purpose: motion must communicate state (enter/exit, expand/collapse, selection), never
  decorate.

## 13. Icon usage

One icon set, uniform stroke weight and size (`16`/`20`px). Icon-only controls require an
`aria-label` and a hover/focus affordance. Icons reinforce, never replace, text for primary
actions. Reserve the warning triangle for `--status-warning/error` only.

## 14. Keyboard accessibility

- Global shortcuts register at document level with input-focus guards so they don't type
  into fields (audit UI-10: `/`, `F`, `g d` typed into search). Document them in the command
  palette (⌘/Ctrl-K).
- Standard bindings: `/` focus search, `F` cycle filters, `g d` digest, `Esc` close, arrow
  keys navigate feed rows, `Enter` open, `C` copy markdown.
- Modals/drawers: focus moves in on open, is trapped, returns to trigger on close; Esc closes.

## 15. Responsive behavior

- Breakpoints `--bp-sm/md/lg/xl` (640/960/1280/1600). Analyst surfaces tighten at ≤ 960px;
  admin sidebar collapses at ≤ 700px. (Audit: layout survives 960/700 today — preserve it.)
- Use fluid grids (`repeat(auto-fill, minmax(…))`) for stat/card grids so boxes stay
  uniform (plan ticket E5-1: ARCH Overview boxes were jammed/non-uniform).
- Tables scroll horizontally within a bounded container; never overflow the page. Charts
  live in fixed-height wrappers at every breakpoint.

## 16. Empty / error / loading states (the four states)

Every async region MUST distinguish:
- **Loading** — skeleton (preferred) over spinner; never a layout jump.
- **Empty** — intentional message + optional CTA (FEED "no results / clear filters" is the
  reference quality bar).
- **Degraded/Error** — explicit message + `X-Request-ID` ("ref: …") + retry. Must be
  visually distinct from Empty (audit UI-11, plan ticket E1-3: correlation timeout looked like "no data"; the
  Resources chart looked empty when it was failing).
- **Data** — the normal state.

Provide one shared `EmptyState` primitive that renders all non-data variants consistently.

## 17. Error states (surfacing)

Front end shows the API `detail` + `X-Request-ID`; never raw exception objects. High
failure metrics escalate to `--status-error` and to the global notification surface (audit
E9: failing Discord webhook + 91% LLM fail rate were not surfaced prominently).

---

## 18. Component hierarchy

Three layers. Higher layers compose lower ones; never re-implement a lower layer.

1. **Primitives (Radix behavior + BRIEFR CSS tokens)** — Button, Checkbox, RadioGroup,
   Switch, Select, Slider, Tabs, Tooltip, Popover, Dialog/Modal, DropdownMenu, ScrollArea,
   AlertDialog (typed-confirm).
2. **Composites** — Table/DataGrid, StatCard, Badge/Pill, Chip/Filter, Card/Panel,
   Toast/notification, EmptyState, ChartShell (fixed-height wrapper), FormField
   (label+control+error), SidebarNav, PageHeader/Breadcrumbs, DangerZone.
3. **Features** — FEED cards, DetailDrawer + tabs, BRIEF widgets, IOC panels, Forge,
   ARCH pages, Admin pages. Features consume composites/primitives only.

## 19. Component usage rules

- **Do not use native `<input type="checkbox|radio">` or `<select>`** — use the Radix-based
  primitives (audit: raw default checkboxes across Storage/Feed-health/Scheduler/FEED were
  the top "amateur" signal).
- One primitive per pattern; do not fork a second tooltip/button/table implementation.
- Tooltips/popovers are **portaled and collision-aware** (audit UI-BUG-3, plan ticket E2-4: reference tooltip
  overflowed over other content).
- Tables use `DataGrid` with `table-layout: fixed` + shared `<col>` so column resize keeps
  header/body aligned (audit UI-BUG-2, plan ticket E2-3: resize desynced header from body).
- Selected/active state = `--accent-selected` via the shared SidebarNav/Tabs/Chip
  components; do not hand-roll active styling.
- Clickable elements must look clickable (hover + cursor + affordance); non-clickable
  cards must not look interactive (audit UI-15: stat cards/header icons).
- Charts use **Recharts** (the approved engine — ADR-005; shadcn look re-skinned to
  `--chart-*` tokens, no Tailwind), wrapped in `ChartShell` (fixed height) and rendering
  `EmptyState` when series are empty/zero. Chart.js is deprecated (migrating out per plan
  E7-5). Keep the 90-day heatmap + EPSS sparklines as custom SVG.

## 20. Naming conventions

- **CSS tokens:** `--<category>-<role>[-<variant>]` (e.g. `--surface-hover`,
  `--severity-critical-bg`, `--accent-selected`). Never encode a literal color in the name
  (no `--tan`, `--orange`).
- **Components:** PascalCase (`DataGrid`, `StatCard`, `EmptyState`).
- **Component files:** colocated CSS or CSS Modules using token vars only.
- **Data attributes for state:** `data-state`, `data-severity`, `data-status`,
  `data-motion` — style off these, don't inline colors.
- **Icons:** `Icon<Name>`; **test ids:** `data-testid="<component>-<role>"`.

---

## 21. Assumptions & open questions

- **A1:** Radix primitives adopted **without Tailwind**; shadcn used only as a copy/pattern
  reference (ADR-003). The approved/conditional/prohibited library registry is ADR-005.
  Revisit only if the team explicitly requests Tailwind.
- **A2:** `tokens.css` supersedes the ad-hoc token block in `App.css`; legacy raw names
  (`--red`, `--bg2`, `--text3`, …) remain as aliases until migration completes, then are
  removed. **Open:** exact alias-removal cut-line per component.
- **A3:** Light theme is a parity target, not a shipped feature (currently not imported).
- **Open Q1:** final `--text-muted` value validated by an automated contrast lint.
- **Open Q2:** whether the command palette becomes the primary nav (affects sidebar work).
- **Open Q3:** icon library choice (existing inline SVGs vs a set like Lucide).

## 23. Repo-wide UX standards (permanent)

These rules apply to **every surface** — analyst shell, admin, ARCH, Forge, wallboard —
not only the admin control plane. They were introduced after admin UX review (2026-07)
and are enforced repo-wide via `tokens.css` + `.cursor/rules/design-system.mdc`.

### 23.1 Focus and active accent (soft orange)

- **Focus rings** use the global `--focus-ring` token (38% accent mix). Do not
  reintroduce page-scoped overrides or full-strength `4px` accent halos.
- **Active/selected borders** on chips, pills, filters, and cards use
  `--border-active` (45% accent mix), not raw `--accent-selected` as a border color.
- **Inset indicators** (sidebar nav, selected table rows, subtabs) use
  `--accent-indicator` via `--shadow-inset-indicator-*` tokens — never full-strength
  `inset … var(--accent-selected)` bars.
- **Tab underlines / cell selection outlines** use `--accent-indicator` /
  `--outline-active`, not solid full-accent strokes.

Primary nav fills (e.g. header tab with `--accent-selected` background) are the
exception: filled selection is allowed; neon **borders** are not.

**FEED sidebar filter toggles** (KEV, PoC, EPSS, My stack) use accent
(`--surface-selected` / `--border-active`), not red — red is not a filter-on signal.

### 23.2 Date and time inputs

- All user-facing date/time pickers use the shared `DateTimePicker` primitive
  (Radix `Select` for hour/minute + `react-day-picker` dark calendar). Never ship
  native `datetime-local` or unstyled calendar popovers in new code.
- `TimeWindowPicker` (analyst BRIEF charts) and admin ingest filters are the
  reference implementations.

### 23.3 Discrete settings → dropdowns, not sliders

- When a setting has a **finite set of values** (typography px steps, enum
  choices), use `Select` dropdowns — not `Slider` or native `range` inputs.
- `Slider` remains for continuous values only (e.g. a true 0–100 scale).

### 23.4 Reset actions

- Revert-to-default controls are labeled **"Reset to default"** (or **"Reset to
  defaults"** when multiple fields). Never **"Reset draft"** — that implies
  unpublished state the product does not have.

### 23.5 Wayfinding labels

- Breadcrumb and section wayfinding labels use **consistent uppercase** mono
  styling (`letter-spacing`, `text-transform: uppercase`) — see `AdminBreadcrumbs`
  and shared `PageHeader` patterns. Do not mix Title Case and ALL CAPS in one trail.

### 23.6 Health vs freshness (ops surfaces)

- **Circuit/HTTP health "OK"** and **scheduled sync freshness** are different
  concepts. When a feed is healthy but stale, show an explicit callout with a
  concrete action (e.g. link to Scheduler → "Run NVD sync") — never imply "all OK"
  covers data age. `FeedHealthPage` is the reference pattern.

### 23.7 Long-running work

- When backend jobs expose `progress_message` (scheduler locks), the UI must show
  that message plus an indeterminate progress bar while status is `LOCKED`, and
  poll until the lock clears. `JobTable` + `SchedulerPage` are the reference;
  apply the same pattern anywhere else long-running jobs surface.

## 24. Suggested additional documentation (future)

- `docs/design/component-inventory.md` — per-control migration map (raw → primitive → files).
- `docs/design/accessibility-vpat.md` — conformance statement + audit results.
- A Storybook (or equivalent) with visual-regression snapshots for every primitive/composite.
- `docs/design/motion.md` — catalog of approved transitions per component.
