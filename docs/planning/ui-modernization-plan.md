# BRIEFR UI Modernization Plan

**Status:** DRAFT (v0.2) — master implementation roadmap for the UI/design-system effort.
**Last updated:** 2026-07-14
**Type:** Planning only. No application code is changed by this document.
**Execution wiring:** this plan is the **UI-M track** in
[`docs/planning/SPRINT_2026-07.md`](SPRINT_2026-07.md); the progress checklist (§13) is
the authoritative ticket state (tick items here, add PR numbers, per the sprint loop in
`AGENTS.md`). Ticket id scheme: `E*-*` (this plan), `UI-*`/`UI-BUG-*` (findings §2),
`REL-*` (backlog doc ids — always cited with the backlog's numbering).

**Companion documents (authoritative inputs / keep in sync):**
- Design SSOT: [`docs/design/design-system.md`](../design/design-system.md)
- Tokens spec: [`frontend/src/styles/tokens.css`](../../frontend/src/styles/tokens.css)
- Architecture decision: [`docs/decisions/ADR-003-ui-design-system.md`](../decisions/ADR-003-ui-design-system.md)
- Non-UI + verified-bug backlog: [`docs/planning/reliability-and-bug-backlog.md`](reliability-and-bug-backlog.md)
- Correlation redesign decision: [`docs/decisions/ADR-004-correlation-precompute.md`](../decisions/ADR-004-correlation-precompute.md)
- Component-library registry: [`docs/decisions/ADR-005-component-library-strategy.md`](../decisions/ADR-005-component-library-strategy.md)
- Cursor enforcement: [`.cursor/rules/design-system.mdc`](../../.cursor/rules/design-system.mdc)

> This plan consolidates a full running-product review conducted 2026-07-14 against a
> restored **production** database (21,679 CVEs), logged in as admin. Findings come from
> black-box product exploration (UI + API + DB + logs), **not** a source-code audit.
> UI concerns are owned here; backend/reliability concerns and specific reproduced bugs are
> tracked in the reliability-and-bug backlog and cross-referenced by ticket id.

---

## 1. Executive summary

BRIEFR is a deep, opinionated, dark terminal-grade analyst console. Its **content and
capability are strong**; its **UI execution is uneven** and, in a few places, broken. The
product today reads as an excellent internal tool, not yet a premium enterprise SaaS
(Linear/Vercel/Wiz/Cloudflare tier). The gap concentrates in five root causes (see §3):
no governed component layer (raw browser controls), inconsistent "selected/active" color
language with red overloaded, sub-AA contrast on secondary text, weak micro-interactions,
and one whole section (ARCH) shipped essentially unstyled. Two items are genuine
**reliability** defects (correlation timeout → operational-priority hero absent) and one is
a genuine **layout** bug (Resources chart grows the page infinitely).

The strategy: **establish the token layer + primitive library + motion toggle first**
(Phase 1), then **roll primitives + semantics across surfaces** (Phase 2), then
**re-skin ARCH and finish polish** (Phase 3). Reliability bugs run on a **parallel track**
(they don't depend on the design system). "Quick win" (QW) vs "Architectural" (ARCH) is
marked per ticket.

---

## 2. Current UI/UX audit findings

Severity uses Critical / High / Medium / Low. Each finding: Location · Problem · Evidence ·
Impact · Fix ticket. Backend/reliability items live in the backlog doc; the highest-impact
ones are listed here for completeness and cross-referenced.

Relationship to prior audits: the UX-audit correction pass
([`specs/ux-audit.md`](specs/ux-audit.md), PR1–PR11 = #396–#408) and the QA audits
(2026-07-12) are **shipped history** — nothing below re-opens a closed ticket. All
findings here were independently reproduced on 2026-07-14 against the restored
production DB.

### Critical
- **[REL-1] Correlation engine times out (~61s)** for hub-IOC-heavy CVEs → `correlation_unavailable`. *Backlog REL-1.* Impact: flagship feature intermittently dead. → epic **E1**.
- **[REL-2] Operational-Priority hero never renders** (drawer Overview) because `POST /risk` shares the slow correlation path. Evidence: `audit_drawer_op_hero.png`; API returns P1/85.8/UNKNOWN when given 61s. Impact: ADR-002 headline invisible. → **E1**.
- **[UI-BUG-1] Resources chart grows page infinitely** with no plotted data. Evidence: `audit_v_resources_scrolled.png`. → **E2-1**.

### High
- **[UI-1] Raw browser-default checkboxes** app-wide (Storage/Feed-health `Wrap`/`Center`, Scheduler "Show technical IDs", FEED filters). Evidence: `audit_r_checkbox_wrapcenter.png`. → **E3-1**.
- **[UI-2] Inconsistent "selected/active" color**: green feed chips vs red preference radios vs red/orange nav tab vs faint ARCH sidebar vs orange operator sidebar. → **E4-1 / E5-3**.
- **[UI-3] Red overloaded** for neutral use (red CVE links in Campaign Links `audit_r_campaign_links.png`, red "UTC" toggle, red radios). → **E4-2**.
- **[UI-4] Low-contrast secondary text** below WCAG AA (metadata, table headers, AI-ops text, placeholders). Evidence: `audit_p4_*`, `audit_admin_ai_ops.png`. → **E6-1**.
- **[UI-5] No CVSS severity accent on cards**; badge hues too close to separate at a glance. Evidence: `audit_r_feed_severity.png`. → **E4-3**.
- **[UI-6] ARCH section is barebones/unstyled** — 11 of 12 pages are wall-of-text lists (only Risks is tabled); Overview boxes non-uniform/jammed. Evidence: `audit_r_arch_attack_surface.png`, `audit_v_arch_overview_boxes.png`. → **E5**.
- **[UI-BUG-2] Column-resize handles wonky** — drag guide moves but header/body desync; no clean resize. Evidence: `audit_v_resize_1.png`. → **E2-3 / E3-3**.
- **[REL-4/REL-6] Failing Discord webhook (HTTP 500) not globally surfaced**; **91% LLM fail-rate shown as dim gray** not an alert. *Backlog REL-4/REL-6.* → **E9**.

### Medium
- **[UI-7] Weak/absent hover feedback** on cards, vendor chips, filter chips (~3–5% delta / none; no transition). Evidence: `audit_p1_hover.png`. → **E7-1**.
- **[UI-8] Subtle focus rings** (esp. admin); focus ring is red-tinted, not accent. → **E6-2**.
- **[UI-9] Icon-only controls lack accessible names** (bell, "…", pin, close-X). → **E6-3**.
- **[UI-10] Keyboard shortcuts scope-conflict** with the search field (`/`,`F`,`g d` type into it). → **E6-4**.
- **[UI-11] Empty vs error vs loading not distinguished** (correlation timeout looks empty; Resources looks empty when failing). → **E1-3 / E7-2**.
- **[UI-12] No feedback on "Copy markdown"; no progress on large exports.** → **E7-3**.
- **[UI-BUG-3] Reference tooltip overflows** over other drawer content (not clamped/flipped). Evidence: `audit_r_ref_tooltip.png`. → **E2-4 / E3-2**.
- **[UI-BUG-4] ARCH graph pan selects text** instead of panning. *Backlog REL-3.* Evidence: `audit_r_arch_pan_selection.png`. → **E2-5**.
- **[UI-13] ARCH graph max-zoom (2.5×) insufficient** — labels ~10–11px on 93 nodes. → **E2-6**.
- **[UI-14] Spacing/borders**: cramped FEED filter panel; borderless BRIEF stat cards; tight degraded-source card padding. Evidence: `audit_r_spacing.png`. → **E7-4**.
- **[UI-15] Hidden/low-affordance clickables** (stat cards, header icons). Evidence: `audit_r_hidden_clickable.png`. → **E7-1 / E3-7**.
- **[UI-16] Table header hierarchy weak; status badges lack first-encounter legends.** → **E4-4**.
- **[REL-5] Resources per-process CPU metric = 0** (collector), so chart is flat even once bounded. *Backlog REL-5.* → **E2-2**.

### Low
- **[UI-17] ARCH filter tabs dim instead of hide** non-matching columns. → **E2-7**.
- **[UI-18] ARCH Overview uses literal `→` text arrows** instead of connectors. → **E5-1**.
- **[UI-19] Trust Boundaries badge wording** ("CRITICAL RISK: LOW"). → **E5-4**.
- **[UI-20] Threat Scenarios: interactive tabs over a single empty state.** → **E5-5**.
- **[UI-21] EPSS "+X%" rendered green** can read as "good." → **E4-3**.
- **[UI-22] Admin vs analyst density/typography drift** (must share the type scale). → **E6-1 / design-system §5**.

Positives to preserve: command palette (⌘/Ctrl-K), intentional FEED empty state, typed-confirm danger zones, custom toggles/radios, digest/PDF modals, responsive survival at 960/700px, real Postgres integrity check, structured logs, provider-health control plane.

---

## 3. Root cause analysis

Most findings collapse into **eight** shared causes; fix the cause, not each symptom:

1. **No governed component layer** → raw browser checkboxes/selects, bespoke buttons/tooltips/tables. (UI-1, UI-BUG-2/3, UI-6.)
2. **No single "selected/active" token; red overloaded** → four different active-state treatments; red used for neutral. (UI-2, UI-3.)
3. **No AA-guaranteed text tokens** → dim secondary text everywhere. (UI-4, UI-22.)
4. **No severity→container mapping** → badge-only severity, hues too close, no card accent. (UI-5, UI-21.)
5. **Overlays not portaled/clamped; canvases not `user-select:none`** → tooltip overflow, pan selects text. (UI-BUG-3, UI-BUG-4.)
6. **Charts unbounded / states conflated** → infinite-growth chart, empty≈error. (UI-BUG-1, UI-11, REL-5.)
7. **ARCH built outside the (nascent) system** → unstyled tables, jammed boxes. (UI-6, UI-18/19/20.)
8. **Reliability heavy work on the request path** → correlation/OP-hero timeouts. (REL-1/2 → ADR-004.)

---

## 4. Complete remediation plan (epics & tickets)

Ticket format: **id · title — effort (S/M/L) · type (QW/ARCH) · deps.** Acceptance criteria
are summarized; full Problem/Evidence/Impact are in §2 and the backlog.

### E0 — Design-system foundation
- **E0-1** Wire `tokens.css` + reconcile with `App.css`; add severity/status/spacing/motion layers — M · ARCH · —. *Accept:* tokens imported; CI "no raw hex" + contrast lint pass.
- **E0-2** Adopt Radix primitives (no Tailwind; shadcn as reference); ship reference `Checkbox` — M · ARCH · E0-1, ADR-003. *Accept:* ADR-003 accepted; one primitive on tokens; incremental gzip cost of the primitives layer ≤ 35 kB (measured in the PR body; ADR-005 governance).
- **E0-3** Tool-wide motion toggle (default on, honor `prefers-reduced-motion`, persist) — S/M · QW · E0-1. *Accept:* toggling kills all animation app-wide; OS pref respected; persists.
- **E0-4** Docs sync on ADR acceptance — S · QW · ADR-003/005 accepted. Update `CLAUDE.md` ("plain JSX/CSS, **no component library**" → tokens + Radix per ADR-003), `AGENTS.md` cloud notes, and `docs/PRODUCT_STATUS.md` in the same PR that lands E0-2, so the always-applied agent rules never contradict `.cursor/rules/design-system.mdc`. *Accept:* no repo doc still claims "no component library".

### E1 — Reliability: correlation & operational priority  *(parallel track; see ADR-004 + backlog)*
- **E1-1** Correlation off request path (precompute edges; degree-cap hubs) — L · ARCH. *Accept:* p95 < 2s on prod dataset; no `correlation_unavailable` on sampled hubs.
- **E1-2** OP hero renders from cheap signals immediately; correlation escalation async — M · ARCH · E1-1. *Accept:* hero < 1s on every CVE.
- **E1-3** Distinct loading/empty/degraded/error states for correlation & risk — M · QW · E7 EmptyState.

### E2 — Standalone bugs *(parallelizable)*
- **E2-1** Bound Resources chart height + empty state — S · QW.
- **E2-2** Fix per-process CPU sampling or labeled fallback — S/M · QW.
- **E2-3** Column resize via `table-layout:fixed` + shared `<col>` — M · QW · E3-3.
- **E2-4** Portaled/collision-aware reference tooltip — S · QW · E3-2.
- **E2-5** `user-select:none` + pointer-drag on ARCH graph — S · QW.
- **E2-6** Raise graph max-zoom (~4×) + fit/reset control — S · QW.
- **E2-7** ARCH filter hides (not dims) non-matching columns — S · QW.
- **E2-8** Add `PyJWT` to `requirements.txt` — S · QW *(setup/CI; backlog REL-7)*.
- **E2-9** Correct PG16 → PG17 in `AGENTS.md` / `docs/PRODUCT_STATUS.md` / `docs/POSTGRES.md` — S · QW *(docs-only; backlog "Environment / data artifacts" note: production backup is pg_dump v1.16 = PG17)*.

### E3 — Primitive component library *(depends on E0)*
- **E3-1** Checkbox / Switch / Radio — M · ARCH. *Accept:* zero native checkboxes (grep gate).
- **E3-2** Tooltip / Popover (portaled, collision-aware) — M · ARCH.
- **E3-3** Table / DataGrid (fixed layout, sticky header, sortable, resize, wrap/center) — L · ARCH. *Accept:* if TanStack Table is used, headless only, incremental gzip ≤ 15 kB (ADR-005 governance).
- **E3-4** Dialog / Modal / AlertDialog (focus trap, scroll-lock, Esc/return-focus) — M · ARCH.
- **E3-5** Tabs / DropdownMenu / Select — M · ARCH.
- **E3-6** Slider/range primitive — S · QW.
- **E3-7** Badge / Pill / Card / StatCard / EmptyState / Toast — M · ARCH.

### E4 — Color & severity semantics
- **E4-1** One `--accent-selected` across nav/sidebar/chips/rows/radios — M · QW · E0-1 only (token/CSS change; does **not** wait for E3 — highest-visibility quick win).
- **E4-2** Reserve red for destructive/critical; recolor neutral links/toggles/radios — S · QW · E0-1 only.
- **E4-3** Card severity left-accent + wider badge hue separation + EPSS direction fix — S/M · QW · E0-1 (+E3-7 where Badge/Card primitives already exist).
- **E4-4** Status/severity legends & tooltips everywhere — M · QW · E3-2 (portaled Tooltip).

### E5 — ARCH re-skin *(depends on E3/E4)*
- **E5-1** Overview → uniform responsive StatCard grid; real connectors — M · QW.
- **E5-2** Port all ARCH lists to `DataGrid` — L · ARCH · E3-3.
- **E5-3** ARCH sidebar active-state → `--accent-selected` — S · QW · E4-1.
- **E5-4** Trust-Boundaries badge wording — S · QW.
- **E5-5** Threat-Scenarios empty state (drop placeholder tabs) — S · QW.

### E6 — Accessibility
- **E6-1** Text contrast → AA (tokens) + admin/analyst type parity — S · QW · E0-1.
- **E6-2** Standard high-contrast focus ring — S · QW · E0-1.
- **E6-3** `aria-label` on icon-only controls — S · QW.
- **E6-4** Document-level shortcut scoping + palette listing — S · QW.
- **E6-5** Target sizes ≥24px; chart text/table fallback; color-not-alone — M · QW.

### E7 — Micro-interactions & polish
- **E7-1** Hover/press states via motion tokens; clarify clickable vs static — M · QW · E0.
- **E7-2** Loading skeletons over spinners/jumps — M · QW.
- **E7-3** Copy/export feedback (toast + progress) — S · QW.
- **E7-4** Spacing/border pass (filter panel, stat cards, degraded cards) — M · QW · E0-1.
- **E7-5** Chart migration Chart.js → **Recharts** (shadcn look, no Tailwind; ADR-005) — L · ARCH · E0-1, E2-1. *Scope:* re-create shadcn's chart wrapper on `--chart-*` tokens; migrate **every Chart.js chart** chart-by-chart behind `ChartShell` (fixed height) with visual-regression — including `BriefCharts`, the admin `OpsCharts`, **and the Admin → Resources chart** (the infinite-growth offender, UI-BUG-1); wire animations to the motion toggle; keep the 90-day heatmap + EPSS sparklines as custom SVG. Migrate **page-atomically** (all charts on a page/route in one PR) and lazy-load chart chunks, so any given route loads Recharts *or* the legacy Chart.js chunk — never both (a per-page guarantee is only enforceable if migration is page-atomic; mixed pages would load both); **remove Chart.js once the last chart is ported**. *Accept:* no `import` of Chart.js remains; Chart.js dependency removed from `package.json`; Recharts ships as a lazy chunk ≤ 110 kB gzip (measured in the PR body); no chart grows unbounded; parity or better visuals.

### E8 — Navigation / IA
- **E8-1** Unify active-state across shells (rides E4-1) — S · QW.
- **E8-2** Admin breadcrumbs / "you are here" — M · QW.
- **E8-3** Admin "needs attention" landing aggregating failures — M · QW.

### E9 — Observability UX
- **E9-1** High failure rates render as `--status-error` alerts — S · QW.
- **E9-2** Surface failing webhooks/keys in the global notification bell/StatusBar — M · QW.
- **E9-3** Fix `AI_OPERATIONS_RECORD=…` label wrap/truncation — S · QW.

---

## 5. Prioritized implementation phases

- **Phase 0 — Groundwork:** E0-1, E0-2, E0-3, E0-4, ADR-003/005 accepted. Nothing user-visible except the motion toggle.
- **Phase 1 — Trust/reliability (parallel):** E1-1, E1-2, E2-1, E2-2, E2-8, E2-9; ADR-004 accepted. Early visible wins: E4-1, E4-2 (token-only, need just E0-1).
- **Phase 2 — Primitives + semantics:** E3-1…3-7, E4-3/4-4, E6-1/2/3, E2-3/4.
- **Phase 3 — ARCH + polish + IA + observability:** E5-*, E7-*, E8-*, E9-*, E2-5/6/7, E6-4/5, E1-3.
- **Phase 4 (future):** §14.

---

## 6. Dependencies between tasks

```
E0-1 ─┬─ E0-2(+E0-4) ─ E3-1..3-7 ─┬─ E4-3/E4-4 ─ E5-1..5-5
      ├─ E0-3                      ├─ E6-1/6-2
      ├─ E4-1, E4-2 (token-only)   └─ E7-1/7-4
      └─ E6-1/6-2
E3-2 ─ E2-4, E4-4    E3-3 ─ E2-3, E5-2
E4-1 ─ E5-3, E8-1    E7(EmptyState/E3-7) ─ E1-3
E1-1 ─ E1-2 (ADR-004)     [E2-1,E2-2,E2-5,E2-6,E2-7,E2-8,E2-9: independent]
```
Critical-path (design system): **E0-1 → E0-2 → E3 → E4-3/4 → E5**. Reliability path
(**E1-1 → E1-2**) is independent and can start immediately. E4-1/E4-2 are token-only
and can land right after E0-1 (early visible wins).

---

## 7. Risk assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Token migration regresses styling (shared surface — `CLAUDE.md` danger zone) | Med | High | Land tokens as aliases first; visual-regression snapshots; migrate per-component behind review. |
| DetailDrawer contention (sprint tickets M1/H2/H4/C-Evolve-3 all touched it) | Med | Med | Never parallelize DetailDrawer work (per `AGENTS.md`). Serialize E3-4/E4-3 there. |
| E1-1 correlation redesign changes data semantics | Med | High | ADR-004; keep API shape; before/after latency evidence on restored prod DB; feature-flag precompute. |
| Radix + React 19 interop issues | Low | Med | Radix supports React 19; spike in E0-2 before broad adoption. |
| Scope creep into a full Tailwind migration | Med | Med | ADR-003 explicitly defers Tailwind; `.mdc` rule forbids introducing it unprompted. |
| Contrast/token changes alter brand feel | Low | Med | Keep `--accent #c8b88a`; only raise muted text + unify selection. Design review gate. |
| Light theme drift | Low | Low | Treat as parity target; not shipped until explicitly scheduled. |

---

## 8. Technical considerations

- **No Tailwind.** Radix primitives styled with BRIEFR CSS variables/CSS Modules; shadcn is
  a *pattern reference* only (ADR-003).
- **Token wiring:** import `tokens.css` before `App.css`; keep legacy raw names as aliases
  during migration; enforce "no raw hex / no raw spacing" via lint (proposed CI job).
- **Motion toggle:** `data-motion` on `<html>`; persists via `GET/PATCH /api/me/preferences`
  (existing) with localStorage fallback; consolidates the current partial Display toggle.
- **Charts:** wrap every chart in `ChartShell` (fixed height) to permanently prevent the
  infinite-growth class of bug. Charting standardizes on **Recharts** (SVG, no Tailwind;
  shadcn look re-skinned to `--chart-*` tokens) — **Chart.js is deprecated and removed** after
  the E7-5 migration. Both libraries may coexist in the repo during migration; migration is
  **page-atomic** with lazy-loaded chart chunks so any given route loads only one charting
  library. Keep the heatmap/sparklines as custom SVG. Ref: ADR-005.
- **DataGrid:** single `<table>` with `table-layout:fixed` + shared `<col>` widths so resize
  keeps header/body aligned; virtualize large tables (Attack Surface 157, epss_history-scale).
- **Performance:** animate transform/opacity only; memoize heavy rows; keep feed windowing
  (`content-visibility`); no expensive layout animations.
- **Backend (E1):** move correlation edge computation into a scheduler job (heavy work off
  the request path — `CLAUDE.md` danger zone 6); request path reads precomputed edges.

---

## 9. Testing strategy

- **Visual regression:** Storybook (or equivalent) snapshots per primitive/composite; diff
  on PR. Mandatory for E3.
- **Accessibility:** automated axe/pa11y run per page (contrast, names, roles, focus); manual
  keyboard pass per surface; target-size check. Gate on AA.
- **Unit:** token contrast lint; "no native checkbox/select" grep test; formatter tests.
- **Interaction/E2E:** extend the Playwright smoke (`backend/tests/test_playwright_smoke.py`,
  `PLAYWRIGHT_SMOKE=1`) for: motion toggle, modal focus-trap/Esc, tooltip no-overflow, table
  resize alignment, empty/error/loading states, keyboard shortcuts.
- **Reliability (E1):** before/after latency of `/correlation` and `/risk` on the restored
  production DB; assert p95 budgets; assert OP hero renders < 1s.
- **Manual review gate:** `./scripts/verify-local.sh` green (local merge gate per `AGENTS.md`);
  design review sign-off for visual changes.

---

## 10. Rollback strategy

- **Tokens/primitives:** additive — legacy raw tokens/components remain until a component is
  fully migrated, so any single migration PR reverts cleanly. Keep PRs component-scoped.
- **Motion toggle:** default-on but inert if reverted (no data migration).
- **E1 correlation:** ship precompute behind a flag; if regressions appear, flip back to the
  (slow but known) on-request path without a deploy.
- **General:** every phase is independently revertable; no destructive migrations. Chart
  height + `user-select` fixes are trivially revertable CSS.
- Follow `CLAUDE.md`: migrations are forward-only; never edit an applied Alembic migration
  (E1 precompute uses a new additive table/migration if persistence is needed).

---

## 11. Definition of Done (per ticket)

1. Consumes semantic tokens only (no raw hex/spacing); passes lint gates.
2. Meets WCAG AA (contrast, focus, names, target size, keyboard) — axe clean.
3. Uses/produces a shared primitive; no duplicate pattern introduced.
4. Respects the motion toggle + `prefers-reduced-motion`; transitions 120–180ms, transform/opacity only.
5. All four states implemented where async.
6. Visual-regression snapshot added/updated; Playwright/interaction test where applicable.
7. `./scripts/verify-local.sh` green; design review approved.
8. Runtime docs updated (`PRODUCT_STATUS.md`, `API_REFERENCE.md`) if behavior changed;
   this plan's checklist ticked; `design-system.md` updated if a rule/primitive changed.

---

## 12. Milestones

Named `UI-M*` to avoid colliding with sprint ticket ids (the sprint's closed **M1**
is a DetailDrawer ticket — see §7).

- **UI-M1 — Foundation & trust:** E0-1/2/3/4, E1-1/2, E2-1/2/8/9, ADR-003/004/005 accepted. *Exit:* tokens live, motion toggle shipped, app feels reliable (correlation/OP hero fast).
- **UI-M2 — Primitives & semantics:** E3-1…3-7, E4-1…4-4, E6-1/2/3, E2-3/4. *Exit:* no native controls; one selection color; AA contrast; portaled tooltips; aligned resizable tables.
- **UI-M3 — ARCH & polish:** E5-*, E7-*, E8-*, E9-*, E2-5/6/7, E6-4/5, E1-3. *Exit:* ARCH on the system; hovers/skeletons/feedback consistent; failures surfaced; states honest.

**Measured exit criteria (scriptable, not vibes)** — each milestone's exit is checked by
numbers recorded in the closing PR body:

| Metric | How measured | UI-M1 | UI-M2 | UI-M3 |
|---|---|---|---|---|
| Native `<input type=checkbox\|radio>` / `<select>` count | grep gate (E3-1) | baseline recorded | **0** | 0 |
| Raw hex occurrences in `frontend/src` component code | lint gate (E0-1) | no new | declining | **0** (aliases removed per cut-line) |
| axe critical/serious violations per audited page | axe/pa11y run (§9) | baseline recorded | 0 on migrated surfaces | **0 app-wide** |
| `/correlation` p95 on restored prod DB | timing harness (§9) | **< 2s** | < 2s | < 2s |
| OP hero first render | timing harness (§9) | **< 1s** | < 1s | < 1s |
| Entry bundle gzip (guard: sprint I8 baseline 99 kB) | `npm run build` output | ≤ 105 kB | ≤ 105 kB | ≤ 105 kB |
| Distinct "selected/active" treatments | manual sweep + snapshots | — | **1** | 1 |

---

## 13. Progress checklist

**Foundation (E0)**
- [x] E0-1 tokens wired + reconciled + lint gates
- [x] E0-2 Radix adoption + reference Checkbox
- [x] E0-3 tool-wide motion toggle
- [x] E0-4 docs sync on ADR acceptance (CLAUDE.md / AGENTS.md / PRODUCT_STATUS)

**Reliability (E1) — see backlog**
- [x] E1-1 correlation precompute (ADR-004) — #560
- [x] E1-2 OP hero decoupled from correlation — PR TBD
- [ ] E1-3 four-state correlation/risk

**Standalone bugs (E2)**
- [x] E2-1 Resources chart bounded + empty state
- [x] E2-2 per-process CPU metric
- [ ] E2-3 column resize alignment
- [ ] E2-4 reference tooltip portaled
- [ ] E2-5 ARCH pan `user-select:none`
- [ ] E2-6 ARCH max-zoom raised
- [ ] E2-7 ARCH filter hides not dims
- [x] E2-8 PyJWT in requirements.txt
- [x] E2-9 PG16 → PG17 doc correction

**Primitives (E3)**
- [ ] E3-1 Checkbox/Switch/Radio  [ ] E3-2 Tooltip/Popover  [ ] E3-3 Table/DataGrid
- [ ] E3-4 Dialog/AlertDialog  [ ] E3-5 Tabs/Dropdown/Select  [ ] E3-6 Slider  [ ] E3-7 Badge/Card/StatCard/EmptyState/Toast

**Semantics (E4)**
- [x] E4-1 one selection accent  [x] E4-2 red reserved  [ ] E4-3 card severity accent  [ ] E4-4 legends

**ARCH (E5)**
- [ ] E5-1 Overview grid  [ ] E5-2 lists→DataGrid  [ ] E5-3 sidebar active  [ ] E5-4 badge wording  [ ] E5-5 empty state

**A11y (E6)**
- [ ] E6-1 contrast/type  [ ] E6-2 focus ring  [ ] E6-3 aria-labels  [ ] E6-4 shortcuts  [ ] E6-5 target size/charts

**Polish / IA / Observability (E7/E8/E9)**
- [ ] E7-1 hover/press  [ ] E7-2 skeletons  [ ] E7-3 copy/export feedback  [ ] E7-4 spacing/borders  [ ] E7-5 charts → Recharts (remove Chart.js)
- [ ] E8-1 unify active  [ ] E8-2 breadcrumbs  [ ] E8-3 needs-attention landing
- [ ] E9-1 failure alerts  [ ] E9-2 global webhook/key surfacing  [ ] E9-3 AI-ops label fix

---

## 14. Future enhancements

- Light-theme parity (ship the `[data-theme=light]` map).
- Command palette as primary navigation + fuzzy CVE search + actions.
- Saved views/filters, bulk CVE actions, triage assign/ack state.
- Notification center (persisted, grouped, severity-ranked).
- Correlation graph visualization (post E1-1).
- Storybook design site + published VPAT.
- Chart configurability (per-user widget prefs).
- RBAC-scoped views / super-admin tier for DB explorer.

---

## 15. Assumptions & open questions

- **A1** Radix without Tailwind; shadcn reference only (ADR-003).
- **A2** `tokens.css` supersedes `App.css` token block; aliases removed post-migration.
- **A3** Light theme is a parity target, not shipped now.
- **A4** ADR numbering continues the repo's `docs/decisions/ADR-00N` sequence (003/004).
- **Open** contrast-lint tool choice; icon library; whether to introduce Storybook now or later;
  final alias-removal cut-line; whether correlation precompute needs a new table (ADR-004).
