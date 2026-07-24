# ADR-005 — Component library & UI dependency strategy (approved / conditional / prohibited)

## Status

**ACCEPTED — 2026-07-14.** This ADR is the **canonical registry** of which UI
libraries may be used in BRIEFR and how. It operationalizes
[`ADR-003`](ADR-003-ui-design-system.md) (semantic tokens + Radix, no Tailwind) into an
explicit allow/deny list so future work can't silently pull in a conflicting library.
Enforced by [`.cursor/rules/design-system.mdc`](../../.cursor/rules/design-system.mdc);
usage rules live in [`docs/design/design-system.md`](../design/design-system.md).
Continues the `docs/decisions/ADR-00N` sequence.

## Context

ADR-003 set the direction (Radix primitives styled with BRIEFR CSS variables; shadcn as a
pattern reference; Tailwind deferred). Without a concrete registry, a future change is likely
to add a styled component kit "because it solves a problem," reintroducing the exact
inconsistency the design system exists to remove (opinionated themes, global CSS, Tailwind,
heavy/decorative animation). We also need to cover **headless utility** libraries, not just
component kits, and to define a **governance gate** for adding any new UI dependency.

Constraints (from ADR-003 / `docs/CONTRIBUTOR_RULES.md` / the design system):
- No Tailwind or any CSS framework unless the maintainer explicitly requests it.
- Components must be stylable entirely via BRIEFR semantic tokens (no injected theme/global CSS).
- Motion budget: 120–180ms, `transform`/`opacity` only, respect the tool-wide motion toggle.
- Preserve the dark-terminal identity and WCAG 2.1 AA.
- Project license is **Apache License 2.0**; dependencies must carry a permissive
  license (MIT / Apache-2.0 / BSD) so they can be bundled without conflicting terms.

## Decision

### ✅ Approved — behavior/primitive layer (use directly, styled with BRIEFR tokens)
- **Radix UI primitives** — the sanctioned headless behavior/accessibility layer (Checkbox,
  RadioGroup, Switch, Select, Slider, Tabs, Tooltip, Popover, Dialog/AlertDialog,
  DropdownMenu, ScrollArea, etc.). Unstyled; ARIA/focus/portaling handled; React 19 compatible.

### ✅ Approved — headless utilities (no styling; use when Radix/existing don't already cover it)
- **Recharts** — the **sanctioned charting engine** (SVG, MIT, React 19 compatible). Themed
  via CSS variables mapped to the `--chart-*` tokens; wrapped in `ChartShell` (fixed height).
  This is what lets us adopt the shadcn "Charts" look **without Tailwind**: re-create shadcn's
  thin chart wrapper (`ChartContainer`/tooltip/legend) with BRIEFR CSS tokens, not Tailwind
  classes. See the charting decision below.
- **cmdk** — command palette (already used for ⌘/Ctrl-K).
- **Floating UI** — positioning for custom tooltips/popovers/menus (note: Radix already uses
  it internally — prefer Radix's built-ins before adding it standalone).
- **TanStack Table (headless)** — table/data-grid logic for the shared `DataGrid` (headless
  only; render with BRIEFR markup + tokens).
- Rule: prefer what Radix or the existing stack already provides before adding a utility.

### ♻️ Deprecated — migrate off
- **Chart.js** — currently in use (`BriefCharts.jsx`, `OpsCharts.jsx`, `chartLoader.js`).
  **Deprecated in favor of Recharts** so we can adopt the shadcn chart aesthetic (re-skinned,
  no Tailwind). Migrate chart-by-chart, each behind `ChartShell` with a visual-regression
  snapshot; **remove Chart.js once the last chart is ported** — never ship both libraries
  long-term. Tracked in the UI modernization program (maintainer notes).
  Custom SVG visuals (90-day heatmap, EPSS sparklines) stay hand-built SVG — do NOT force
  them into Recharts.

### Charting decision (single library)
BRIEFR standardizes on **exactly one charting library as the end state**. Because the
maintainer prefers the shadcn chart look and it is achievable without Tailwind, that library
is **Recharts** (via re-skinned shadcn patterns). During the E7-5 migration both libraries
technically exist in the repo and build artifacts; migration is **page-atomic** (all charts
on a route move in one PR) and chart chunks are lazy-loaded, so any given route loads
Recharts *or* the legacy Chart.js chunk — never both. (The per-route guarantee holds only
because migration is page-atomic; a mixed page would load both chunks.) Delete Chart.js once
the last chart is ported. Chart animations must respect the tool-wide motion toggle and
`prefers-reduced-motion`.

### 🟡 Conditional — pattern/copy reference ONLY (re-implement on BRIEFR CSS; never a runtime dep)
- **shadcn/ui registry** — copy component *patterns/markup* and adapt to BRIEFR tokens.
  **Do not** install its Tailwind/CVA toolchain or ship its class names.
- **Magic UI (selected components only)** — reference for specific interactions/visuals, but
  it is **Tailwind + Framer-Motion and animation-heavy**: strip Tailwind, re-skin with tokens,
  and cut motion to the BRIEFR budget (120–180ms, transform/opacity, honor the motion toggle).
  Not a blanket "copy freely" source; each use is case-by-case and design-reviewed.
- Rule for both: **no Tailwind at runtime**, no Framer-Motion for decorative effects, output
  must pass the design-system rules as if hand-written.

### ⛔ Prohibited — styled/opinionated component or CSS frameworks
Do **not** add: **Mantine, MUI (Material UI), Ant Design, Chakra UI, Bootstrap, DaisyUI**, or
**Tailwind CSS** as a framework (deferred by ADR-003). More generally, prohibit any library
that ships its own theme/design language, injects global CSS, or cannot be styled purely via
BRIEFR tokens. These would fight the terminal identity, duplicate the token system, and
reintroduce inconsistency.

## Governance (adding or changing any UI dependency)

A new UI dependency (or promoting a Conditional one) requires **all** of:
1. An update to this ADR (move it into the correct list with rationale).
2. Design-review sign-off against `docs/design/design-system.md`.
3. **License** check (MIT/Apache-2.0/BSD; bundlable under Apache-2.0) and **React 19** compatibility.
4. **No Tailwind / no injected global CSS**; must be themable via BRIEFR semantic tokens.
5. **Bundle-size** justification (prefer headless/tree-shakeable; note gzip cost).
   Current budgets (recorded in PR bodies): primitives layer ≤ 35 kB gzip incremental
   (plan E0-2); TanStack Table ≤ 15 kB (E3-3); Recharts lazy chunk ≤ 110 kB (E7-5);
   entry bundle stays ≤ 105 kB gzip (sprint I8 baseline: 99 kB).
6. Accessibility parity (keyboard, focus, ARIA) at least equal to the Radix baseline.

If a library isn't on the Approved/Conditional lists, it is Prohibited by default until this
ADR is updated.

## Risks
- **Over-restriction** slows a genuine need — mitigated by the governance path (update the ADR
  rather than bypass it).
- **Conditional creep** (shadcn/Magic UI copied without re-skinning) — mitigated by design
  review + the `.mdc` rule (no Tailwind/raw hex/native controls).

## Alternatives considered
1. **No registry (rely on ADR-003 prose).** Rejected — too easy to drift; not enforceable.
2. **Radix-only, ban all references.** Rejected — too rigid; shadcn/Magic UI patterns are
   useful when adapted.
3. **Adopt a full styled kit (MUI/Mantine).** Rejected — see ADR-003; imposes a foreign visual
   language and runtime.

## Consequences
- One authoritative list to check in review and in `.cursor/rules/design-system.mdc`.
- shadcn and Magic UI are explicitly "reference, re-skinned, no Tailwind" — not runtime deps.
- Headless utilities (Recharts, cmdk, Floating UI, TanStack Table) are sanctioned so the
  charts/DataGrid/palette/positioning work doesn't require a styled kit.
- Charting standardizes on **Recharts** (shadcn look, no Tailwind); **Chart.js is deprecated**
  and removed after the E7-5 migration. Both may coexist in the repo during migration; the
  page-atomic + lazy-loading rule keeps any given route on a single charting library.
- Adding anything new is a deliberate, documented decision.
