# ADR-003 — BRIEFR UI design system: semantic tokens + Radix primitives (no Tailwind)

## Status

**ACCEPTED — 2026-07-14.** Establishes the UI architecture that all future UI work
follows. Companion to [`docs/design/design-system.md`](../design/design-system.md)
(rules), [`frontend/src/styles/tokens.css`](../../frontend/src/styles/tokens.css) (token spec),
and [`docs/planning/ui-modernization-plan.md`](../planning/ui-modernization-plan.md) (roadmap).
Continues the `docs/decisions/ADR-00N` sequence (previous: ADR-001 schema split, ADR-002
operational priority). Reliability track is decided separately in
[`ADR-004`](ADR-004-correlation-precompute.md).

## Context

A 2026-07-14 running-product review (restored production DB) found the UI is capable and
deep but inconsistent and, in places, amateur/broken:

- **Raw browser-default** checkboxes/selects across the app (the top "homemade" signal).
- **"Selected/active" rendered four different ways** (green feed chips, red preference radios,
  red/orange nav tab, faint ARCH sidebar, orange operator sidebar); **red overloaded** for
  neutral links/toggles as well as danger/severity.
- **Sub-AA contrast** on secondary text; **subtle/red-tinted focus rings**.
- **No severity→container mapping** (badge-only, hues too close, no card accent).
- **One whole section (ARCH) shipped essentially unstyled** (11 of 12 pages wall-of-text).
- **Bespoke, non-portaled tooltips/tables** → overflow and header/body resize desync.

`CLAUDE.md` states BRIEFR is "React 19 + Vite frontend, plain JSX/CSS, **no component
library**," and `App.css` already carries an ad-hoc token block (`--bg*`, `--text*`,
`--type-*`, `--red/amber/green`, `--accent #c8b88a`, `--focus-ring`, `--motion-fast`, `--z-*`)
but **no severity/status scale, spacing scale, or single selection token**. We need a real,
governed design system without a disruptive framework migration, and we must preserve the
signature dark-terminal identity and (per maintainer) **not adopt Tailwind**.

## Decision

1. **Semantic design tokens as the single styling contract.** All colors, type, spacing,
   radius, elevation, motion, z-index, and breakpoints are CSS custom properties with
   semantic names (`--surface-hover`, `--severity-critical`, `--accent-selected`,
   `--space-4`, `--motion-normal`). Product code consumes only these — never raw hex, never
   the underlying `--c-*` primitives. Spec: `frontend/src/styles/tokens.css`.
2. **CSS variables (not a CSS-in-JS or utility framework)** as the token mechanism —
   consistent with the existing `App.css` approach, theme-able at runtime (dark/light,
   `data-motion`), and zero new runtime dependency.
3. **Radix UI primitives** as the behavior/accessibility layer (Checkbox, RadioGroup, Switch,
   Select, Slider, Tabs, Tooltip, Popover, Dialog/AlertDialog, DropdownMenu, ScrollArea),
   styled with BRIEFR tokens/CSS. This buys focus management, portaling + collision handling,
   keyboard support, and ARIA "for free" — directly fixing the raw-checkbox, tooltip-overflow,
   focus-trap, and focus-ring findings.
4. **shadcn/ui as a pattern reference only.** We copy shadcn's composition/markup patterns and
   adapt them to BRIEFR's CSS token architecture. We do **not** install shadcn's Tailwind/CVA
   toolchain. The full approved/conditional/prohibited library registry (incl. shadcn, Magic
   UI, and headless utilities) is maintained in [`ADR-005`](ADR-005-component-library-strategy.md).
5. **Tailwind migration intentionally deferred.** No Tailwind is introduced unless the
   maintainer explicitly requests it later. (Enforced by `.cursor/rules/design-system.mdc`.)
6. **One primitive per pattern; three-layer hierarchy** (Primitives → Composites → Features)
   as defined in `design-system.md` §18–19. No duplicate/bespoke implementations.
7. **Tool-wide motion toggle** (`data-motion` on `<html>`, default on, honoring
   `prefers-reduced-motion`, persisted to `user_preferences`) gates all CSS + Radix animation.

## Why these choices

- **Why semantic tokens:** symptoms (dim text, inconsistent selection, overloaded red) all
  trace to un-named, duplicated color decisions. A semantic layer fixes the *cause* once and
  makes future drift lintable ("no raw hex").
- **Why CSS variables:** already the project's idiom (`App.css`); runtime theming (light/dark,
  motion) needs live-swappable values; no bundler/runtime cost; SSR/first-paint safe.
- **Why Radix:** the review's a11y and interaction defects (native controls, tooltip overflow,
  focus traps, focus rings) are exactly what Radix solves; it is unstyled, so the terminal
  aesthetic is fully preserved via tokens; supports React 19.
- **Why shadcn patterns (not the library):** shadcn is the best-documented reference for
  composing Radix + tokens; borrowing its patterns accelerates work without importing Tailwind.
- **Why defer Tailwind:** BRIEFR is plain CSS today; a Tailwind migration is a large, risky
  change to a shared surface (`CLAUDE.md` danger zone) with no benefit that tokens+Radix don't
  already deliver. Deferring keeps blast radius small and honors the maintainer's constraint.

## Migration strategy

- **Phase 0:** land `tokens.css` (import before `App.css`); keep legacy raw names (`--red`,
  `--bg2`, `--text3`, …) as **aliases** so nothing breaks; add lint gates ("no raw hex", token
  contrast). Ship the motion toggle. Build one reference primitive (`Checkbox`).
- **Phase 1:** build the primitive set (Radix + tokens) with visual-regression snapshots.
- **Phase 2:** migrate features surface-by-surface (component-scoped PRs; never parallelize
  `DetailDrawer`), replacing raw controls, unifying selection color, applying severity accents.
- **Phase 3:** re-skin ARCH onto the system; finish polish/a11y; remove now-unused legacy
  aliases at a defined cut-line.
- Each step is additive and independently revertable (see plan §10 Rollback).

## Risks

- **Styling regressions** on a shared surface — mitigated by alias-first tokens + visual
  regression + component-scoped PRs + design review.
- **Radix/React 19 edge cases** — de-risk with an E0-2 spike before broad adoption.
- **Scope creep toward Tailwind** — explicitly forbidden here and in the Cursor rule.
- **Brand feel shift** from contrast/selection changes — keep `--accent #c8b88a`; only raise
  muted text and unify selection; gate on design review.

## Alternatives considered

1. **Full shadcn + Tailwind.** Best DX/velocity, mature ecosystem — **rejected** for now:
   large migration in a plain-CSS codebase, new toolchain, maintainer declined Tailwind.
2. **MUI / Chakra / Mantine (styled libraries).** Fast, but impose their own visual language
   and runtime; fighting them to keep the terminal aesthetic is costly — **rejected**.
3. **Keep plain CSS, hand-build all primitives (no Radix).** Zero deps, but we'd re-implement
   accessibility (focus trap, portaling, keyboard) that Radix gives free and that the audit
   shows we currently get wrong — **rejected** (high a11y risk).
4. **Do nothing / spot-fix.** Leaves the root causes; drift returns — **rejected**.

## Related decisions

- [`ADR-005`](ADR-005-component-library-strategy.md) — canonical component-library & UI
  dependency registry (approved / conditional / prohibited) that operationalizes this ADR.

## Future roadmap

- Component inventory doc (raw→primitive migration map) and a Storybook with visual
  regression. Published VPAT (EN 301 549). Light-theme parity. Revisit Tailwind only on
  explicit request. Token contrast enforced in CI.

## Consequences

- New UI must use tokens + primitives; PRs adding raw hex/spacing or native controls are
  rejected by the Cursor rule and lint. `design-system.md` becomes the UI SSOT. Existing
  components keep working via aliases until migrated. No runtime dependency beyond Radix
  (added when E0-2 lands; not by this doc).
