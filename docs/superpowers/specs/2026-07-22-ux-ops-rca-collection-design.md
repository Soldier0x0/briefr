# UX / ops RCA collection (2026-07-22) — Design

**Status:** Accepted for planning (maintainer session 2026-07-22)  
**Created:** 2026-07-22  
**Audience:** Implementers (Cursor agents / maintainers)

## 1. Goal

Ship the defects and honesty gaps collected in the 2026-07-22 operator session as **independently mergeable programs** — each with RCA, tests, and docs — without one mega-PR.

## 2. Locked decisions

| # | Decision |
|---|----------|
| 1 | **Factual schedules only** — remove orphaned “auto daily …” claims and config help that imply a job that does not exist. |
| 2 | **Context-aware delta polarity** — PATCHES (and any “more is better” tile) must not use severity-up=red blindly. |
| 3 | **Filter toggles** — Your Filters controls must use the shared switch/checkbox scale (box ≈ thumb / hit target), not an oversized track with a tiny thumb. Prefer shared `Switch` or a square checkbox-style control; do not invent a third toggle. |
| 4 | **Optional chips deselect on re-click** where `aria-pressed` implies toggle (Catch-up duration presets are the exemplar; sweep siblings with the same sticky-radio pattern). Exclusive “All” chips may stay sticky. |
| 5 | **Portaled overlays** — Background Sync (`ApiQueueIndicator`) must use a portaled, collision-aware popover (Radix), matching `UserMenu`. |
| 6 | **Forge ATT&CK empty slab** — fix layout/contrast so empty navigator does not read as a solid black band; keep density-first dark terminal identity. |
| 7 | **Risk Register** — enable wrap on title/summary columns; surface live-row **cap honesty** (showing N admitted / candidate pool). Operator dependency patching stays **manual** (out of product). Dismiss/mute and product-only quarantine stay follow-ups unless cheap. |
| 8 | **AI Ops failure payloads** — opt-in (`off` by default): store failed LLM request messages + empty/error response metadata; admin-only; short TTL; **never** in support pack. Manual **Retry with same payload** on that row. |
| 9 | **14-day publications sparkline** — no product change; education only (counts publications by `DATE(published)`, not concurrent capacity). |

## 3. Programs → plan files

| Program | Plan | Ships alone? |
|---------|------|--------------|
| A — Factual operator schedules | [`../plans/2026-07-22-factual-operator-schedules.md`](../plans/2026-07-22-factual-operator-schedules.md) | Yes |
| B — Polarity, toggles, chip deselect | [`../plans/2026-07-22-ui-polarity-toggles-chips.md`](../plans/2026-07-22-ui-polarity-toggles-chips.md) | Yes |
| C — Background Sync portal + Forge navigator | [`../plans/2026-07-22-overlays-forge-navigator.md`](../plans/2026-07-22-overlays-forge-navigator.md) | Yes |
| D — Risk Register wrap + cap honesty | [`../plans/2026-07-22-risk-register-wrap-cap.md`](../plans/2026-07-22-risk-register-wrap-cap.md) | Yes |
| E — AI Ops failure payload + manual retry | [`../plans/2026-07-22-ai-ops-failure-payload-retry.md`](../plans/2026-07-22-ai-ops-failure-payload-retry.md) | Yes |

Do **not** parallelize Programs that touch the same file without coordinating (B+C both touch header/CSS lightly — prefer serial if conflict).

## 4. RCA index (session)

| ID | Symptom | Root class | Program |
|----|---------|------------|---------|
| S1 | Footer `(auto daily 06:00 IST)` | Orphaned `CACHE_REFRESH_*` / `refresh_schedule` with no APScheduler job | A |
| S2 | PATCHES `+N` delta red | Shared `stat-delta--up` = worse for all tiles | B |
| S3 | Your Filters toggle box ≫ thumb | Custom `Toggle` 36×24 track / 10×10 thumb | B |
| S4 | Catch-up 2h/6h/8h cannot deselect | Sticky `selectPreset` + `aria-pressed` without toggle-off | B |
| S5 | Background Sync clipped | Non-portaled absolute dropdown + overflow containment | C |
| S6 | Forge ATT&CK “black band” | Tall empty `.fg-tactic-col` / contrast | C |
| S7 | Risk Register cells truncated | `DataGrid` hardcodes `whiteSpace: nowrap`; wrap parked in self-stack spec | D |
| S8 | “More” self-stack CVEs / why / how to patch | Cap 50 + score 55/100; no in-app remediate | D (honesty only); patching manual |
| S9 | Groq Feed Health `empty LLM response content` | Real chat empty body → circuit registry; not key-health heartbeat | E (ledger + retry); Feed Health card copy optional small fix in E |
| S10 | No way to see/retry LLM payload | ADR-AI-5 metadata-only by default | E |

## 5. Non-negotiables (all programs)

1. Semantic tokens only — no raw hex/`rgb()` in component CSS.
2. Design-system §23: portaled tooltips/popovers; shared `Switch`/`Checkbox`/`Select`; soft `--focus-ring` / `--border-active`.
3. Red/`--danger` only for destructive / critical / error.
4. Docs in same PR when runtime or API changes: `PRODUCT_STATUS.md`, `API_REFERENCE.md` if endpoints change, prepend `HANDOVER.md`.
5. Merge gate: `./scripts/verify-local.sh`.
6. Migrations forward-only (Program E).
7. Never print secrets; failure payloads must not include API keys; strip `Authorization` if ever logged.
8. Self-hosted opt-in does **not** put bodies in support pack.

## 6. Out of scope (this collection)

| Item | Disposition |
|------|-------------|
| Operator dependency upgrades for self-stack CVEs | Manual / later |
| Live-row dismiss/mute | Follow-up |
| Product-only (55) admission policy change | Follow-up |
| Always-on full prompt transcript store | Rejected — opt-in failures only |
| Changing 14-day sparkline semantics | Rejected — docs/education only |
| Fixing all non-portaled header menus (`NotificationBell`, clock tz) | Optional sibling in C only if cheap; not required |
| Graphify regeneration as planning dependency | Do not block on graphify |

## 7. Suggested merge order

1. **A** (copy/honesty, low risk)  
2. **B** (analyst-visible UI)  
3. **C** (overlays / Forge)  
4. **D** (ARCH Risk Register)  
5. **E** (AI Ops + migration — largest)

## 8. Verification

Each program’s plan lists its pytest / frontend unit / `npm run build` / `verify-local.sh` expectations. No program is done without green local verify for the surfaces it touches.
