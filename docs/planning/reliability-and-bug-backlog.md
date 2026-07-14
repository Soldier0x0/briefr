# BRIEFR Reliability & Verified-Bug Backlog

**Status:** DRAFT (v0.1) — companion to [`ui-modernization-plan.md`](ui-modernization-plan.md).
**Last updated:** 2026-07-14
**Type:** Planning only. No code changed.

**Why this exists:** the UI modernization package covers design/UX. This document captures
the **non-UI reliability findings** and the **specific reproduced bugs** from the same
2026-07-14 running-product review (restored **production** DB, 21,679 CVEs, logged in as
admin). Every item here was observed at runtime — via the UI, the API, the database, and the
backend logs — not inferred from code. UI-styling issues live in the UI plan; this is for
bugs and backend/ops behavior. **This doc's `REL-*` numbering is canonical** — the UI plan
cites these ids verbatim (its own finding ids are `UI-*`/`UI-BUG-*`; never renumber either
scheme).

**Cross-refs:** [`ADR-004-correlation-precompute.md`](../decisions/ADR-004-correlation-precompute.md),
[`design-system.md`](../design/design-system.md) (for the UI-side of state handling),
[`PRODUCT_STATUS.md`](../PRODUCT_STATUS.md), [`CLAUDE.md`](../../CLAUDE.md) (danger zones).

**Evidence artifacts:** screenshots referenced below were captured during the review
(`audit_*` / `audit_r_*` / `audit_v_*`). Request-ids are from the live backend log.

---

## Severity legend
**Critical** — flagship feature broken / trust-breaking. **High** — significant defect or
blocks clean setup. **Medium** — degraded behavior / observability gap. **Low/Info** —
environment or data artifact, or cosmetic-adjacent.

---

## REL-1 — Correlation engine times out (~61s) on production-scale data  · CRITICAL
- **Location:** `GET /api/cves/{id}/correlation`; surfaces in the CVE drawer Correlation/Intel tab.
- **Problem:** For CVEs whose IOCs include high-degree "hub" indicators, the correlation
  query exceeds the 60s DB command timeout and returns `{"error":"correlation_unavailable","otx_status":"degraded"}`. It works for low-degree CVEs (Campaign Links render fine — `audit_r_campaign_links.png`), so it is **data-dependent, not universal.**
- **Evidence:** Reproduced at **61.0–61.2s** for `CVE-2023-27350` and `CVE-2024-1708` with the
  scheduler disabled, an idle pool, and **after `ANALYZE`** (so not contention or stale
  stats). Backend log: `Correlation engine failed for CVE-2023-27350: Database command
  timeout` (request-ids `d402be3a60944d2d`, `798ee0970b184e80`). Live `pg_stat_activity`
  showed the running statement is the shared-IOC self-join:
  `SELECT ocp2.cve_id … FROM otx_pulse_iocs oi JOIN otx_cve_pulses ocp … JOIN otx_pulse_iocs oi2 ON oi2.ioc_type=oi.ioc_type AND oi2.ioc_value=oi.ioc_value JOIN otx_cve_pulses ocp2 … GROUP BY …`.
- **Root cause:** self-join of `otx_pulse_iocs` (**132,802 rows**) on `(ioc_type, ioc_value)`
  across `otx_cve_pulses` (**49,209 rows**). Hub IOCs shared by many pulses create O(n²)
  fan-out. Indexes exist on `(ioc_type,ioc_value)` and `pulse_id` — this is a cardinality
  problem, not a missing index. Heavy work is on the **request path** (violates `CLAUDE.md`
  danger zone 6).
- **Impact:** The single most differentiated feature intermittently returns "unavailable";
  also cascades into REL-2.
- **Recommendation:** Move edge computation into a scheduler job that writes precomputed
  correlation edges; degree-cap/suppress hub IOCs (leverage `ioc_degree`) **before** the
  join; push `LIMIT`/degree filters into SQL; request path reads precomputed rows. See
  **ADR-004**. Add an explicit "computing/unavailable" UI state (UI plan E1-3).
- **Effort:** L · **Type:** Architectural · **Owner track:** backend.
- **Caveat:** measured on a single-core VM; production hardware may be faster, but the query
  exceeds the app's own 60s timeout on the real dataset — a genuine scalability defect.

## REL-2 — Operational-Priority hero never renders (cascade of REL-1)  · CRITICAL
- **Location:** CVE drawer → Overview hero (`OverviewTab.jsx` → `OperationalPriorityHero`);
  `POST /api/cves/{id}/risk`.
- **Problem:** The ADR-002 headline (Operational Priority P1–P4 + Threat Score 0–100 +
  Environment tier) does not render; the drawer opens straight into "Key exploitation
  signals." The hero returns `null` when `riskScore` is null, and `/risk` takes ~61s because
  it computes correlation-based escalation via the same slow path.
- **Evidence:** `audit_drawer_op_hero.png`; `POST /risk` measured **61.0s**, returning correct
  data when finally resolved (`operational_priority.band=P1`, `threat.score=85.8`,
  `environment.tier=UNKNOWN`). Code path: hero is rendered first but gated on `riskScore`.
- **Impact:** The analyst's primary "what do I do first" signal is invisible in practice.
- **Recommendation:** Compute + render OP/Threat/Environment from cheap signals (KEV/EPSS/
  CVSS/asset) immediately; fold correlation escalation in asynchronously after REL-1.
- **Effort:** M · **Type:** Architectural · **Deps:** REL-1.

## UI-BUG-1 — Admin → Resources chart grows the page infinitely  · CRITICAL
- **Location:** Admin → Resources (CPU utilization chart).
- **Problem:** The chart canvas expands vertically without bound, producing ~1000px+ of empty
  dark space and an ever-growing scrollbar, while plotting **no** data.
- **Evidence:** `audit_v_resources_growing.png`, `audit_v_resources_scrolled.png`.
- **Root cause (hypothesis):** classic Chart.js `responsive:true` + `maintainAspectRatio:false`
  inside an auto-height parent → canvas grows to parent, parent grows to canvas → runaway
  height. Compounded by REL-5 (zero data).
- **Recommendation:** Wrap the chart in a fixed-height container (280–320px) with
  `maintainAspectRatio:false`; render an EmptyState when series are empty/zero. (UI plan E2-1.)
- **Effort:** S · **Type:** Quick win.

## UI-BUG-2 — Column-resize handles wonky (header/body desync)  · HIGH
- **Location:** Admin data grids (Storage "TABLE SIZES", Feed health "Source status").
- **Problem:** Hovering a column divider shows a resize cursor and dragging shows a **red
  guide line**, but the header and body columns **desync** and no clean resize lands. (This
  is the "sliders in tables are wonky" the maintainer reported — it means column resizers.)
- **Evidence:** `audit_v_resize_1.png` (red guide between `TABLE` and `SIZE`).
- **Root cause (hypothesis):** header and body are separate tables (or a colgroup not applied
  to `<td>`); the guide updates but body widths don't.
- **Recommendation:** Single `<table>` with `table-layout:fixed` + shared `<col>` widths set
  on drag (or sync body widths on drag-end); ship via the `DataGrid` primitive. (UI plan E2-3/E3-3.)
- **Effort:** M · **Type:** Quick win (via primitive).

## REL-3 — ARCH System-Architecture graph: pan-drag selects text  · HIGH (UX-breaking)
- **UI-plan id:** UI-BUG-4 (this doc's `REL-3` is canonical for cross-referencing).
- **Location:** ARCH → System Architecture (node graph).
- **Problem:** Click-dragging the canvas triggers browser text selection (node labels
  highlight blue) instead of panning.
- **Evidence:** `audit_r_arch_pan_selection.png`.
- **Recommendation:** `user-select:none` on the canvas + proper pointer-drag handling. Also
  raise max zoom (~4×) since labels are ~10–11px at the current 2.5× cap. (UI plan E2-5/E2-6.)
- **Effort:** S · **Type:** Quick win.

## REL-4 — Failing webhook / key health not surfaced globally  · HIGH
- **Location:** Admin → Webhooks (Discord destination shows **HTTP 500**); Feed health shows
  gemini/openrouter "NEEDS ATTENTION".
- **Problem:** A configured alert destination is failing, but this is only visible if you open
  the Webhooks page — not raised in the global notification bell/StatusBar. For a security
  product whose value is timely alerting, a silent alerting failure is serious.
- **Evidence:** `audit_p3_webhooks.png`; `audit_r_arch_barebones.png` (feed health degraded).
- **Recommendation:** Surface failing destinations/keys in the admin StatusBar notification
  bell (already exists for job errors/unhealthy keys — extend). (UI plan E9-2.)
- **Effort:** M · **Type:** Quick win.

## REL-5 — Resources per-process CPU metric records 0.00  · MEDIUM
- **Location:** `resource_metrics` collector / Admin → Resources.
- **Problem:** `briefr_cpu_pct` and `pg_cpu_pct` are recorded as **0.00** (max & avg) while
  `sys_cpu_pct` reaches 100 — per-process CPU sampling is not working in this environment, so
  the chart would be flat even once its height is bounded (see UI-BUG-1).
- **Evidence:** DB query over `resource_metrics` (273 rows, recent): `max_briefr_cpu=0.00,
  max_pg_cpu=0.00, max_sys_cpu=100.00, avg_briefr_cpu=0.000`.
- **Recommendation:** Fix per-process sampling (interval-based `psutil.Process.cpu_percent`)
  or fall back to system CPU with a labeled caveat; render "metric unavailable" when zero.
- **Effort:** S/M · **Type:** Quick win · **Caveat:** may be container-specific; verify on prod host.

## REL-6 — High LLM failure rate under-alerted  · MEDIUM
- **Location:** Admin → AI operations → Overview.
- **Problem:** A **91% LLM fail rate** (166/180 attempts) is rendered as dim gray metadata,
  not as a warning/error. `AI_OPERATIONS_RECORD=on` label also wraps/drops its `=`.
- **Evidence:** `audit_r_aiops_truncation.png`, `audit_admin_ai_ops.png`. (The failures are
  Gemini rate-limit retries from `llm_product_extraction` / `detection_context_llm`.)
- **Recommendation:** Render high failure rates as `--status-error` with a tooltip; fix the
  label wrap. (UI plan E9-1/E9-3.) *Note:* the underlying rate-limiting is expected given the
  provider quota; the defect is the **surfacing**, not the failures themselves.
- **Effort:** S · **Type:** Quick win.

## REL-7 — `PyJWT` missing from `requirements.txt`  · HIGH (setup/CI)
- **Location:** `backend/requirements.txt` / `backend/auth/tokens.py`.
- **Problem:** `auth/tokens.py` does `import jwt`, but `PyJWT` is in **neither**
  `requirements.txt` nor `requirements-dev.txt`. A clean install cannot import the backend or
  collect the auth test suite (18 collection errors) until `PyJWT` is installed manually.
- **Evidence:** `ModuleNotFoundError: No module named 'jwt'` on fresh venv; installing
  `PyJWT==2.10.1` resolved it and login worked.
- **Recommendation:** Add `PyJWT` (pin a current 2.x) to `requirements.txt`. (UI plan E2-8.)
- **Effort:** S · **Type:** Quick win · **Note:** the only item here that is a repo change
  rather than runtime behavior; still gated behind maintainer approval per session rules.

---

## Reference tooltip overflow (UI-BUG-3)  · MEDIUM
Tracked in the UI plan (E2-4/E3-2) — reference URL tooltip overflows over AFFECTED PRODUCTS
in the drawer (`audit_r_ref_tooltip.png`). Listed here for completeness since it's a
reproduced bug; fix ships with the portaled Tooltip primitive.

---

## Environment / data artifacts (INFO — NOT product bugs; do not "fix")

These were observed but are byproducts of running a restored production snapshot on a fresh
VM. Documented so future reviewers don't mis-file them as defects.

- **Production runs PostgreSQL 17, not 16.** The backup is pg_dump **custom format v1.16**
  (PG17). `AGENTS.md`/`PRODUCT_STATUS.md` say PG16 — a **doc inaccuracy** worth correcting,
  but not a runtime bug. (Restore required installing PG17.)
- **Backup archive was plaintext `.tar.gz`** (not `.age`-encrypted) despite the manifest's
  `encrypted:true`/`age_public_key` fields; extracted directly with no key. Worth confirming
  the production backup encryption path actually encrypts.
- **Stale scheduler lock display:** `llm_product_extraction` showed "LOCKED / running 13h" —
  a `started_at`/lock value carried in from the restored `sync_state`, not a genuinely stuck
  13h job. Consider clamping/annotating lock-age after a restore.
- **NVD `503`s** from `services.nvd.nist.gov` are upstream/transient (per-source circuit
  breaker handles them) — not a product fault.

---

## Suggested tracking
When converting to issues: label `reliability` vs `bug` vs `ops`, link each to its UI-plan
epic (E1/E2/E9) and to ADR-004 for REL-1/2. Keep before/after latency evidence on the
restored production dataset attached to REL-1/REL-2.
