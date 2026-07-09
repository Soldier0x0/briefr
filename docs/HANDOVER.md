# Session handover log

**Purpose:** running context for AI agents (Cursor, Claude) and the
maintainer. Newest entry first. Each entry answers: what changed, why,
where it was decided, and what comes next — so a fresh agent session can
continue without re-deriving anything. Append a new dated entry per
significant working session; never rewrite old entries.

**Read order for a fresh agent:** `CLAUDE.md` (rules) →
`docs/PRODUCT_STATUS.md` (what's true in prod) → **this file's newest
entry** → `docs/SPRINT_2026-07.md` (checkboxes).

---

## 2026-07-09 — H2 + H4 shipped; continuing Wave 3

**Merged:** #357 H2 — `ui/` primitives (Button, Badge, Tooltip, Skeleton,
ErrorState, EmptyState, AsyncState) + `useAsync`; BriefCharts proof-of-fit.
**Merged:** #358 H4 — `ui/Modal` + `ui/ConfirmModal`; PdfExportModal + admin
ConfirmModal rebased.

**Autonomous next (do not ask):** **C-Evolve-3** → I3/I5/I8/I9 → Phase B backlog.

---

## 2026-07-09 — FR1 provenance shipped; continuing Wave 3

**Merged:** #355 FR1 — per-section provenance (`exploit_provenance`, detection/correlation
`provenance`) with drawer `IntelProvenanceLine` + tooltips.

**Autonomous next (do not ask):** ~~H-verify~~ ✅ → ~~H2/H4~~ ✅ → **C-Evolve-3** → I3/I5/I8/I9 → Phase B backlog.

---

## 2026-07-09 — J4 + J5: release checklist + production restore runbook (docs)

**What:** Wave 1 doc closeout in `docs/OPERATIONS.md`:

- **J4** — pre-release checklist (migrations, API additive, deploy additive,
  verify-local, backup, update/rollback path, smoke, restore runbook).
- **J5** — manual break-glass production restore runbook (safety backup → pick
  archive → stop services → `briefr-restore.sh` → Alembic → health/row-count
  verify → start; failure table).

**Why:** CI backup round-trip ≠ operator-recoverable box; releases need an explicit
compatibility gate before deploy.

**Next:** **Wave 2** — **M1** (ADR-002 scoring surface implementation).

---

## 2026-07-09 — J3: strict Intel smoke gate default (deploy)

**What:** Wave 1 **J3** — `deploy/briefr-update.sh` now **fails the update by default**
when `deploy/smoke-intel.sh` fails (after the J1 health gate passes). Opt-out:
`BRIEFR_STRICT_SMOKE=0` (warn-only) or `BRIEFR_SKIP_SMOKE=1` (skip). Documented in
`docs/OPERATIONS.md`.

**Why:** Broken intel paths were completing deploys silently (warn-only smoke).

**Next:** **Wave 2 — M1** (ADR-002 scoring surface).

---

## 2026-07-09 — J3: strict Intel smoke gate default (deploy)

**What:** Wave 1 production-trust task **J1** shipped in `deploy/briefr-update.sh`
and `deploy/lib.sh`:

- Records `BRIEFR_PRE_UPDATE_COMMIT` before `git pull` (survives re-exec).
- Runs forward-only `alembic upgrade head` as `briefr` while backend is stopped
  (Postgres deployments only).
- Enforces a real **health gate**: curl retries + `deploy/check-backend.sh` +
  nginx `/api/health`; exits non-zero on failure.
- **Automatic rollback** on Alembic or health-gate failure: `git reset --hard` to
  prior commit, reinstall deps, rebuild frontend, restart services. Opt-out:
  `BRIEFR_SKIP_ROLLBACK=1`. Documented partial-migration caveat in
  `docs/OPERATIONS.md`.

**Also merged:** PR #345 (architecture review + ADR-002 Option D CLOSED) with stale
§0/§11–§14 sections aligned to the ADR.

**Why:** Top production risk — upgrades could wedge the box with no Alembic step,
warn-only health checks, and no rollback path.

**Next:** **J3** — strict smoke gate default (`BRIEFR_STRICT_SMOKE=1` behavior as
default). J4/J5 (docs) parallel-safe.

---

## 2026-07-09 — ADR-002 CLOSED: scoring axes + Operational Priority (docs-only)

**What:** `docs/decisions/ADR-002-operational-priority.md` (ACCEPTED). Resolves the
scoring semantic failure verified in code: no-profile asset → `0.5` → **17.5
phantom headline points**, while profile+no-match → `0.0` → 0 points, so UNKNOWN
was fabricated positive evidence. Decision = **Option D** (rejected naive Option C's
arbitrary weighted average):

- **Threat Score** (0–100, asset-independent) = v1.1b components minus asset,
  renormalized over the 5 non-asset weights, with a **KEV floor of 80** (confirmed
  exploitation dominates low EPSS). Bands CRIT≥80 / HIGH 60-79 / MED 40-59 / LOW<40.
- **Environment Relevance** = categorical tier (CONFIRMED / LIKELY / POSSIBLE /
  WEAK / NO_MATCH / UNKNOWN), never folded into the number.
- **Operational Priority** = deterministic **P1–P4 rule table** over (Threat band ×
  Env tier); **Correlation** = bounded one-band escalation (active/emerging campaign
  + high-confidence edge; weak edges never escalate). UNKNOWN → provisional off
  Threat band (no fabricated points); proven NO_MATCH legitimately de-escalates.
- **Investigation Score → DELETED** (orphaned; its formula is the rejected weighted
  average; double-counts OTX recency; re-imports the placeholder via risk_total).

**Verified in code:** headline `total` still banks the 17.5 even though the exposure
*card* already shows NOT_LOADED/NO_MATCH; `fetchCVEInvestigationScore` has **zero
component callers**; risk inputs are persisted `cves` columns (a provider blip can't
move the score); backend/frontend weights mirror. Adversarial pass (12 challenges)
drove the KEV floor (#1/#3) and the "P1 reserved for CONFIRMED version / genuine
CRIT" rule (#6). Full scenario matrix S1–S10 in the ADR.

**Correction:** the 2026-07-09 review's "loading a profile must never lower priority"
claim is **superseded** — a proven NO_MATCH may de-escalate; only UNKNOWN-as-fabricated-
evidence is forbidden. Review §4.5 updated to RESOLVED.

**M1 is now DETERMINISTIC** (STANDARD coding agent) — full executable prompt in
`BRIEFR_ARCHITECTURE_REVIEW_2026-07.md` Appendix A Prompt 6. No FRONTIER-reasoning
scoring work remains.

**Next:** **J1** (production update safety) remains the exact next execution task;
M1 is the Wave-2 scoring implementation once picked up.

---

## 2026-07-09 — Architecture review + wave replan (docs-only)

**What:** Repository-wide principal-architect review. New durable artifact
[`BRIEFR_ARCHITECTURE_REVIEW_2026-07.md`](BRIEFR_ARCHITECTURE_REVIEW_2026-07.md)
(the primary output — read it before re-investigating correlation, scoring,
freshness, scheduler, or production). `SPRINT_2026-07.md` execution queue
replaced with a **wave model**; the linear J→H→I→F→G queue is kept but marked
superseded. `CORRELATION_V2_PLAN.md` given a SUPERSEDED header (code is at
~phase 3, the plan still reads "v1").

**Verdicts (evidence in the review):**
- **Correlation = INCREMENTALLY EVOLVE.** Deterministic pipeline is mature
  (phases 1–2 shipped, phase 3 partial). The `evidence[]/confidence/why_not_higher`
  model already satisfies the relationship+evidence abstraction — **no generic
  graph, no Neo4j, no `correlation_campaign_edges` persistence**. Real gaps:
  `lifecycle` hardcoded `"active"`, no feed campaign badge, `correlation_infrastructure`
  is dead schema. Fix via three small PRs (C-Evolve-1/2/3).
- **Risk scoring = PRESERVE MATH, FIX PRESENTATION via ADR-002.** v1.1b is sound
  and deterministic. The failure is the blended headline + the `0.5` asset
  placeholder (folded into the headline, it *inverts* real weak matches — a
  profile match of 0.45→15.75 scores below no-profile 0.5→17.5). Recommend
  Option C **in principle**; the remedy is analyst-facing, so it is **ADR-002**,
  not a decision this PR makes. The fused **Investigation Score** is **orphaned**
  (backend route + `api.js` `fetchCVEInvestigationScore`, no UI caller) — ADR-002
  decides adopt-or-delete. Do NOT wire it by default meanwhile.
- **Scheduler = PRESERVE** (APScheduler sufficient; no Celery/Redis/Kafka).
- **Detection = PRESERVE** (deterministic class router; LLM overlay can't author rules).
- **Production = top priority.** `briefr-update.sh` has no Alembic step, health
  check only warns, no rollback; smoke warn-only by default. CI round-trip ≠
  production recovery — J1/J3/J4 + a written restore runbook (J5) are Wave 1.
- **Track H:** Track E shipped toast/states/tooltips/tiles without `ui/`; H1/H3/H5/H6
  are done indirectly — H-verify to close them; H2/H4 conditional; no UI rewrite.
- **Perf:** only gzip (I2) is an unambiguous quick win; I1 obsolete; measure the rest.

**Parallel-safe:** J-track (deploy) ‖ correlation lifecycle/badge (C-Evolve-1/2)
‖ I2 gzip ‖ FR1 provenance. **Not parallel-safe:** M1 scoring-surface,
C-Evolve-3 drawer chip, and H2/H4 all touch `DetailDrawer` — sequence them.

**Frontier-reasoning outstanding:** ~~ADR-002~~ **none** — ADR-002 was **closed
2026-07-09** (see the newer HANDOVER entry above). All remaining work is
deterministic implementation.

**Next:** **J1** — Alembic + health gate + rollback in `deploy/briefr-update.sh`.

---

## 2026-07-08 — Sprint queue reordered (J → H → I → F → G)

**What:** `docs/SPRINT_2026-07.md` execution queue rewritten after Post-B4.
Delivery first: **J** deploy → **H** ui/ (audit, H2/H4) → **I** perf.
**F** license/open-core and **G** learning/onboarding **last**.

**Next:** **J1** — update path + Alembic + health gate + rollback.

---

## 2026-07-08 — Post-B4: CI backup round-trip

**Branch:** `cursor/post-b4-backup-roundtrip-64e9`

**What:** `tests/test_backup_roundtrip_postgres.py` — seeds core tables,
runs production backup path (`run_backup` / `briefr.pgdump`), wipes DB,
`restore_backup(..., force=True)`, asserts `cves` and `kev_deadlines`
row counts. Dedicated step in `test-postgres` CI job.

**Next:** **J1** per reordered sprint queue (see HANDOVER 2026-07-08 reorder entry).

---

## 2026-07-08 — Docs sync: Track E closed, Post-B4 next

**What:** Sprint execution queue, E7 tick (#330–#331), I1 cancelled (Post-B3),
`POSTGRES_NATIVE_PLAN.md` status header, HANDOVER entries for #339–#341,
`PRODUCT_STATUS` API queue observability (#341).

**Next:** merge Post-B4 PR; then J1 or I2 per sprint queue.

---

## 2026-07-08 — #341: API queue task-level observability

**Merged:** `cursor/api-queue-observability-d43d` → `main` (#341).

**What:** Per-source API queue task status in admin/health; indicator redesign;
release-stack corruption fix.

**Next:** Docs sync, then Post-B4.

---

## 2026-07-08 — #340: UI/UX hierarchy pass

**Merged:** `cursor/ui-ux-hierarchy-pass-d43d` → `main` (#340).

**What:** Score placement, exploitation clarity, correlation UX, readability
follow-ups on drawer/Overview after Track E.

**Next:** #341 API queue observability.

---

## 2026-07-08 — #339: Analyst Overview workflow (12-point review)

**Merged:** `cursor/analyst-overview-improvements-d43d` → `main` (#339).

**Branch (historical):** `cursor/analyst-overview-improvements-d43d`

### Implementation plan (points → files → risk)

| # | Files | Backend | Change | Regression risk |
|---|--------|---------|--------|-----------------|
| 1 | `OverviewTab.jsx`, `riskScore.js`, `DetailDrawer.css` | `scoring/asset_match.py`, `scoring/risk.py` (`DEFAULT_ASSET_UNKNOWN=0.5`) | UI: EXPOSURE UNKNOWN when no profile; match tiers when loaded. **Formula unchanged.** | Low — display only |
| 2 | `docs/HANDOVER.md` (this entry) | `scoring/risk.py` | Document v1.1b math; explain 62.9 example; evaluate options (no weight change yet) | None |
| 3 | `OverviewTab.jsx` | — | Collapse breakdown under **WHY THIS SCORE?** (default closed) | Low |
| 4 | `OverviewTab.jsx`, `DetailDrawer.css` | — | Signal strength vs `X / max pts` contribution columns | Low |
| 5 | `OverviewTab.jsx` | — | Reorder sections for analyst decision flow | Low — no data removed |
| 6 | `OverviewTab.jsx`, `patchReferences.js`, `DetailDrawer.css` | `templates/intelligence.py` (`patch_sentence`) | REMEDIATION block with PATCH AVAILABLE / NO PATCH / UNKNOWN + advisory link | Low |
| 7 | `observableExtraction.js`, `extractIndicatorsFromCve.js` | — | Staged extract→validate→classify→prioritize; filter vendor/.html false positives | Medium — IOC prefill set may shrink (intended) |
| 8 | `InvestigationContext.jsx`, `InvestigationPanel.jsx`, `DetailDrawer/index.jsx`, `CVECard.jsx`, `App.jsx` | — | **Start investigation**, session notice, sidebar capture hint | Low |
| 9 | `CVECard.css`, `CVECard.jsx`, `CVEFeed.jsx`, `App.jsx` | — | `cve-opened` vs `cve-selected` vs `cve-card-in-thread` | Low |
| 10–11 | `App.css`, `DetailDrawer.css` | — | Brighter `--text2`/`--text3`; typography scale tokens | Low — global token shift |
| 12 | All above | — | Preserve dark terminal aesthetic; no scoring formula change | — |

### Point 1 — Asset match fallback (documented, not changed)

When `profile is None`, `resolve_asset_component()` → `asset_match_info()` returns **`DEFAULT_ASSET_UNKNOWN = 0.5`** (`backend/scoring/asset_match.py:7`, `risk.py:16`). `calculate_risk_score()` sets `hasProfile: false` and contributes **17.5 pts** (0.5 × 35% × 100). Tests expect this (`test_risk_score_v11b.py`). UI now labels this as a **neutral formula placeholder**, not exposure probability.

### Point 2 — Why BRIEFR 62.9 for a “should be urgent” CVE

**Formula:** `total = round(Σ raw[k] × weight[k] × 100, 1)` — pure weighted sum, no amplification.

**Example decomposition (matches user numbers):**

| Component | Raw | Weight | Points |
|-----------|-----|--------|--------|
| Asset (no profile) | 0.500 | 35% | 17.5 |
| KEV | 1.000 | 25% | 25.0 |
| EPSS | ~0.007 | 15% | ~0.1 |
| Exploit (PoC) | 0.550 | 10% | 5.5 |
| CVSS 9.8 | 0.980 | 10% | 9.8 |
| Momentum (maxed) | 1.000 | 5% | 5.0 |
| **Total** | | | **62.9** |

**Why it feels low:** (1) **Additive model** — KEV+CVSS+PoC do not compound; each caps at its weight slice. (2) **EPSS near zero** contributes almost nothing despite KEV. (3) **Asset placeholder** adds 17.5 without meaning exposure. (4) **Max without profile ≈ 82.5** even if every other signal is 1.0.

**Options for future (not implemented):** KEV severity floors; compound multipliers when KEV+weaponised+high CVSS align; split Threat vs Environment scores; operational P1–P4 band from deterministic rules. Any change needs new tests and HANDOVER sign-off.

**Next:** optional follow-up PR for scoring model revision after analyst review
of #339/#340 in the browser (formula unchanged in #339).

---

## 2026-07-08 — E-PR10: E6 Cmd+K command palette

**What:** `CommandPalette` — ⌘/Ctrl+K for tab jump, CVE open, IOC lookup, refresh stats.

**Next:** Track E complete (E-PR1–10).

---

## 2026-07-08 — E-PR9: E4 IOC paste auto-detect

**What:** Removed manual IP/hash/domain tabs from IOC lookup; type auto-detected
on paste/input with detected-type badge; lookup disabled until type resolves.

**Next:** E-PR10 Cmd+K palette.

---

## 2026-07-08 — E-PR8: E2 stat tile deltas + click-to-filter

**What:** `/api/stats` returns 24h-vs-prior-24h deltas; hero tiles show Δ;
click switches to FEED with matching filter (`patch_only` added for patches tile).

**Next:** E-PR9 IOC auto-detect.

---

## 2026-07-08 — E-PR7: E3 tooltip/badge pass

**What:** `ExplainTip` component; EXPLOITED IN WILD stat tile explain; feed quick
filter chips use discoverable ? tooltips (not raw `title=`).

**Next:** E-PR8 stat tile deltas.

---

## 2026-07-08 — E-PR6: header de-clutter + timezone labels + E5 craft

**What:** My Stack moved to user menu (overflow when logged out); shortcuts/legal
in header ··· overflow; timezone popover shows IST/EDT/PDT + UTC offset column;
heatmap legend accessible; removed dead light-theme toggle CSS; tighter nav tabs
on medium viewports.

**Next:** E-PR7 tooltip/badge pass.

---

## 2026-07-08 — E-PR5: E1 states audit + BRIEF heatmap dead zone

**What:** Documented BRIEF-tab component × state table in sprint (E1); fixed
layout dead zone beside heatmap (`brief-intel-row` `align-items: flex-start`);
wired `TimelineHeatmap` empty state (no activity in window).

**Next:** E-PR6 header de-clutter + timezone labels + E5 craft fixes.

---

## 2026-07-08 — E-PR4: GreyNoise on-demand (quota-safe)

**What:** Removed auto GreyNoise from CVE detail; added
`GET /api/cves/{cve_id}/greynoise-scans`; Intel tab load button + weekly quota.

**Next:** E-PR5 states audit.

---

## 2026-07-08 — E-PR3: drawer readability (exploits table, EPSS, contrast)

**What:** Public exploits table; EPSS sparkline only when variation ≥0.02; drawer
label contrast/size; tighter section padding.

**Next:** E-PR4 GreyNoise on-demand.

---

## 2026-07-08 — E-PR2 merged: Intel tab CSS + compact infrastructure

**What:** Missing correlation CSS; shared-infra compact table (3 + expand);
`drawer-investigate-btn` in `DetailDrawer.css`; dismiss controls styled.

**Next:** E-PR3 drawer readability.

---

## 2026-07-08 — Track E started: UI/UX automation (10 PRs)

**Decision:** Track D closed. Post-B Phase 0–3 done. Primary code track is now
**Track E** (10 PRs, E-PR1–E-PR10 in `docs/SPRINT_2026-07.md`).

**Workflow (automated):** implement → `./scripts/verify-local.sh` → commit
(docs + graphify in same PR) → push → PR → Gemini review (~1 min; `/gemini
review` if silent) → fix → merge → next PR. **Do not block on GitHub Actions**
(quota exhausted).

**Scope highlights:** Intel tab missing CSS + density; GreyNoise off auto detail
(quota UI); header de-clutter; IST/EDT/PDT timezone labels; E1–E6 per sprint.

**Next:** E-PR1 sprint plan merge, then E-PR2 Intel tab fixes.

---

## 2026-07-08 — Post-B Phase 3 merged to `main`: deleted `db/dialect.py`

**Merged:** `cursor/delete-dialect-postgres-native-6fd2` → `main` @ `bff60a5`
(local `./scripts/verify-local.sh` green; no GitHub CI).

**What:** `db/dialect.py` removed; `db/pg_adapt.py` + `db/timeutil.py` added;
imports updated; `test_db_pg_adapt.py` replaces `test_db_dialect.py`.

**Next:** optional router/auth native SQL cleanup; Post-B4 backup CI when Actions resets.

---

## 2026-07-08 — Post-B Phase 2 merged: unified DB exceptions

**What:** Added `db/errors.py` with `DatabaseError` / `DatabaseLockedError`;
connection wrappers translate sqlite3/asyncpg failures at the boundary.
Updated `scheduler.py`, `tracking.py`, `backup/manager.py` to stop catching
`sqlite3.*` outside `db/`. Added `tests/test_db_errors.py`.

**Verified:** `./scripts/verify-local.sh` green (806 passed SQLite suite).

**Next:** convert router/auth SQL to native `$n`/`?` (optional cleanup); Post-B4 backup CI when Actions resets.

---

## 2026-07-08 — Post-B Phase 3: deleted `db/dialect.py`

**What:** Removed `db/dialect.py`. Translation for legacy router SQL now lives in
`db/pg_adapt.py` (used only by `PostgresConnection`). `utcnow_str()` moved to
`db/timeutil.py`. All `db/*.py` modules already use native SQL constants.

**SQLite dev path retained** — only the standalone dialect module is gone.

**Verified:** `./scripts/verify-local.sh` green.

---

## 2026-07-08 — Local verify replaces GitHub Actions (quota exhausted)

**Decision:** GitHub Actions monthly free-tier is exhausted for the foreseeable future.
Development must not block on green CI badges. Use `./scripts/verify-local.sh` from repo
root as the pre-merge gate instead (mirrors CI `test`, `dependency-audit`, frontend build).
`--full` adds Postgres pytest, gitleaks, Playwright smoke when available.

**Workflow going forward:** implement → `./scripts/verify-local.sh` → commit/push → merge
without waiting for GitHub. Re-run Actions on `main` only after quota resets, if desired.

**Next:** Post-B2 — unified DB exceptions in `db/connection.py`.

---

## 2026-07-08 — Post-B Phase 1 PR 8 merged (#328): `init` — Phase 1 complete

**Merged:** #328 without GitHub CI (Actions monthly free-tier exhausted). Verified
locally before merge: full SQLite suite `801 passed, 8 skipped`; init smoke tests
34 passed; `npm run build` green. Runtime SQL extracted to dialect-neutral
constants; `_normalize_epss_scores()` shared across dialects.

**Phase 1 module conversion is complete.** All 10 SQL modules now use explicit
`$n`/`?` dispatch — no `db/dialect.py` translation needed per module.

**Next:** Post-B2 — unified DB exceptions in `db/connection.py`.

---

## 2026-07-08 — Post-B Phase 1 PR 8: `init` Postgres-native

**What:** Converted `backend/db/init.py` — final Phase 1 module — runtime fixup SQL
extracted to dialect-neutral constants (`_NORMALIZE_EPSS_SCORES_SQL`,
`_CREATE_IDX_CVES_HAS_POC_SQL`, `_ALEMBIC_VERSION_SQL`); shared
`_normalize_epss_scores()` helper; `DbConnection` type hints. SQLite bootstrap
DDL unchanged (Alembic owns Postgres schema). Added `tests/test_db_init.py`.

**Verified:** `pytest tests/test_db_init.py -q` (4 passed, SQLite); full suite
`801 passed, 8 skipped` (SQLite).

**PR:** #328 — merged without GitHub CI (Actions quota exhausted); local verification only.

---

## 2026-07-08 — Post-B Phase 1 PR 7 merged (#327): `cve`

**Merged:** #327. CI green on first push (all 5 jobs). Full suite: `797 passed, 8 skipped`
(SQLite); Postgres CI green.

**Next:** solo `db/init.py` (Post-B Phase 1 PR 8 — last module).

---

## 2026-07-08 — Post-B Phase 1 PR 7: `cve` Postgres-native

**What:** Converted `backend/db/cve.py` to the locked `sync_state` pattern — parallel
`_SQLITE` / `_PG` constants for upsert, change history, embeddings, related-CVE
lookups, LLM product extraction, and additive enrichment updates; named-param upsert
SQL rewritten to positional; UTC cutoffs replace `DATE('now', …)` /
`datetime('now', …)` in SQL. Added `tests/test_db_cve.py`.

**Verified:** `pytest tests/test_db_cve.py tests/test_rejected_cves.py tests/test_intel_feeds.py -q`
(18 passed, SQLite); full suite `797 passed, 8 skipped` (SQLite).

**Next:** open PR, CI green, merge; then solo `db/init.py` (PR 8).

---

**Merged:** #326. CI green after Postgres fix: timeline filter uses `published >= $1`
(TEXT) instead of binding a string to `published::date >= $1` (asyncpg requires
`date` objects for `::date` params). Full suite: `789 passed, 8 skipped` (SQLite);
`780 passed, 17 skipped` (Postgres CI).

**Next:** solo `db/cve.py` (Post-B Phase 1 PR 7).

---

## 2026-07-08 — Post-B Phase 1 PR 6: `metadata` + `correlation` Postgres-native

**What:** Converted `backend/db/metadata.py` and `backend/db/correlation.py` to
the locked `sync_state` pattern — parallel `_SQLITE` / `_PG` constants; connection-type
dispatch; Python-computed UTC date/datetime cutoffs; explicit `ON CONFLICT` on
Postgres for upserts/ignores; chunked dynamic `IN` lists in correlation
prioritization queries. Added `tests/test_db_metadata.py` and
`tests/test_db_correlation.py`.

**Verified:** `pytest tests/test_db_metadata.py tests/test_db_correlation.py tests/test_cve_detail_atlas.py -q`
(15 passed, SQLite); full suite `789 passed, 8 skipped` (SQLite).

**Next:** open PR, address Gemini, CI green, merge; then solo `db/cve.py` (PR 7).

---

## 2026-07-08 — Post-B Phase 1 PR 5 merged (#325): `enrichment`

**Merged:** #325 at 2026-07-08T09:09:02Z. CI green after fix for Postgres
`insert_epss_history_rows` rowcount on `ON CONFLICT DO NOTHING`. All three
Gemini comments addressed (UTC dates, quote-aware placeholder renumbering).

**Next:** batch `db/metadata.py` + `db/correlation.py` (Post-B Phase 1 PR 6).

---

## 2026-07-08 — Post-B Phase 1 PR 5: `enrichment` Postgres-native

**What:** Converted `backend/db/enrichment.py` to the locked `sync_state`
pattern — parallel `_SQLITE` / `_PG` constants for audit log, KEV/EPSS
updates, change-history queries, KEV upsert, and stack filtering; Python-computed
date/datetime cutoffs replace `datetime('now', …)` / `DATE('now', …)` in SQL.
Added `tests/test_db_enrichment.py`.

**Verified:** `pytest tests/test_db_enrichment.py tests/test_kev_fields.py tests/test_epss_*.py tests/test_audit_log.py -q`
(42 passed, SQLite); full suite `779 passed, 8 skipped` (SQLite).

**Gemini fixes (pre-merge):** UTC dates in `_cutoff_date_days_ago` / `snapshot_epss_scores`;
quote-aware `_renumber_qmark_placeholders`; per-row execute in
`insert_epss_history_rows` for accurate Postgres rowcount on conflict.

**Next:** `db/metadata.py` + `db/correlation.py` (batched PR 6).

---

## 2026-07-08 — Post-B Phase 1 PR 4 merged (#324): `cache`

**Merged:** #324 at 2026-07-08T08:43:30Z. CI green (test, test-postgres, gitleaks,
dependency-audit, playwright-smoke). Both Gemini inline comments addressed
(chunked `get_ioc_cache_batch`; import `_insert_cve_changes_batch` from `db.cve`).

**Next:** `db/enrichment.py` (Post-B Phase 1 PR 5).

---

## 2026-07-08 — Post-B Phase 1 PR 4: `cache` Postgres-native

**What:** Converted `backend/db/cache.py` to the locked `sync_state` pattern —
parallel `_SQLITE` / `_PG` constants for IOC/feed cache, exploit CRUD, CIRCL
gap query, and `mark_has_poc_additive`; TTL comparisons use Python-computed
cutoff timestamps (replacing `datetime('now', …)` in SQL). Added
`tests/test_db_cache.py`.

**Verified:** `pytest tests/test_db_cache.py tests/test_exploit_sources.py -q`
(23 passed, SQLite); full suite `773 passed, 8 skipped` (SQLite).

**Gemini fixes (pre-merge):** chunk `get_ioc_cache_batch` at `_SQLITE_IN_CHUNK`;
import `_insert_cve_changes_batch` from `db.cve` directly.

**Next:** `db/enrichment.py`.

---

## 2026-07-08 — Post-B Phase 1 PR 3 merged (#323): `cache_retention`

**Merged:** #323 at 2026-07-08T08:22:56Z. CI green (test, test-postgres, gitleaks,
dependency-audit, playwright-smoke). All three Gemini inline comments addressed
(unconditional placeholder assertions; native `$n` seed SQL in Postgres tests).

**Next:** `db/cache.py` (Post-B Phase 1 PR 4).

---

## 2026-07-08 — Post-B Phase 1 PR 3: `cache_retention` Postgres-native

**What:** Converted `backend/db/cache_retention.py` to the locked `sync_state`
pattern — parallel `_SQLITE` / `_PG` constants for all purge queries,
`DbConnection` type hints, Postgres-safe `_rows_deleted` (skips SQLite
`changes()` fallback on Postgres). Added `tests/test_db_cache_retention.py`.

**Verified:** `pytest tests/test_db_cache_retention.py tests/test_cache_retention.py -q`
(7 passed, SQLite); full suite `769 passed, 8 skipped` (SQLite).

**Gemini fixes (pre-merge):** unconditional placeholder assertions; native
`$n` seed SQL in Postgres integration tests.

**Next:** `db/cache.py`.

---

## 2026-07-08 — Post-B Phase 1 PR 2 merged (#322): `watchlist` + `webhooks`

**Merged:** #322 at 2026-07-08T08:04:34Z. CI green (test, test-postgres, gitleaks,
dependency-audit, playwright-smoke). All three Gemini inline comments addressed
(bool `enabled` on Postgres, unique `destination_id` in delivery-log test,
watchlist expired-snooze cleanup).

**Next:** `db/cache_retention.py` (Post-B Phase 1 PR 3).

---

## 2026-07-08 — Post-B Phase 1 PR 2: `watchlist` + `webhooks` Postgres-native

**What:** Converted `backend/db/watchlist.py` and `backend/db/webhooks.py` to
the locked `sync_state` pattern — parallel `_SQLITE` / `_PG` constants,
`type(db).__name__ == "PostgresConnection"` dispatch, `DbConnection` type
hints. Added `tests/test_db_watchlist.py` and `tests/test_db_webhooks.py`.

**Why:** Post-B Phase 1 batched PR per `POSTGRES_NATIVE_PLAN.md` — small,
independent modules with no cross-module SQL dependencies.

**Key decisions:**
- Watchlist active-snooze filter: SQLite keeps `datetime(snooze_until) >
  datetime('now')`; Postgres uses `snooze_until::timestamp > (NOW() AT TIME ZONE
  'utc')` inline (no bound param needed for list queries).
- Webhook alert insert: Postgres uses explicit `ON CONFLICT (alert_type, target)
  DO NOTHING` instead of dialect regex `INSERT OR IGNORE` translation.
- Dynamic `IN (...)` and `UPDATE ... SET` builders use `_in_placeholders()` /
  `_placeholder()` helpers with per-dialect numbering.

**Verified:** `pytest tests/test_db_watchlist.py tests/test_db_webhooks.py
tests/test_watchlist.py tests/test_webhooks_*.py -q` (26 passed, SQLite);
full suite `765 passed, 8 skipped` (SQLite).

**Gemini fixes (pre-merge):** Postgres `enabled` bool param in
`update_webhook_destination`; unique `destination_id` filter in delivery-log
test; watchlist expired-snooze test cleanup in `finally`.

**Next:** `db/cache_retention.py` (solo PR per plan).

---

## 2026-07-08 — Session handoff: program status, agent workflow, Post-B plan

**Purpose of this entry:** everything a fresh agent session needs to continue
as technical co-founder — mindset, automated PR workflow, what's merged, what's
next. **Read this entry first** after `CLAUDE.md` and `PRODUCT_STATUS.md`.

### Co-founder / autonomous-agent mindset

1. **Execute the locked program in order** — open-core waves first where
   incomplete, then Post-B, then deferred items. Do not invent parallel scope.
2. **Specs over supervision** — decisions live in `PROGRAM_PRODUCT_OPEN_CORE.md`,
   `POSTGRES_NATIVE_PLAN.md`, sprint appendix specs. If code and spec disagree,
   verify code; if spec is stale, update the doc in the same PR.
3. **CI + reviewers are the quality gate** — you cannot merge red. Gemini inline
   comments are mandatory to read and address (or explicitly defer with reason).
4. **Minimum correct diff** — match existing style; every changed line traces
   to the task. No speculative features.
5. **Production truth** — `docs/PRODUCT_STATUS.md` wins over older docs.
6. **Batch small PRs only when independent** — see Post-B batching rules below.

### Mandatory per-PR workflow (agreed automated process)

Every code change, no exceptions:

| Step | Action |
|------|--------|
| 1 | Branch off fresh `main`: `cursor/<descriptive-name>-6fd2` |
| 2 | Implement; verify locally — **`./scripts/verify-local.sh`** (or `pytest` + `npm run build` for tiny changes) |
| 3 | Push; open **non-draft** PR (optional when merging direct to `main`) |
| 4 | Wait for **Gemini** when available; address actionable comments |
| 5 | **CI green** when GitHub Actions quota allows; otherwise **`./scripts/verify-local.sh` green is sufficient** |
| 6 | Update docs when runtime behavior changes (`PRODUCT_STATUS.md`, `HANDOVER.md`, sprint checkboxes) |
| 7 | **Merge when local verify (+ Gemini if available) satisfied** — do not idle waiting for Actions |

Cloud-agent note: commit and push before testing; update PR after each iteration.

### Program status (merged on `main`)

| Area | PRs | Status |
|------|-----|--------|
| Wave 1 — config Save + toast/restart | #308–#309 | Merged |
| Wave 2 — stack API, prefs, profile remember | #310–#314 | Merged |
| Wave 3 — DATA_SNAPSHOT + export script | #315–#317 | Merged |
| D4 — Nuclei parser + Sigma artifact injection | #312 | Merged |
| Post-B Phase 0 — full-suite `test-postgres` gate | #318 | Merged |
| F3 — `SECURITY.md` + gitleaks CI | #319 | Merged |
| Post-B Phase 1 — `db/sync_state.py` native | #320 | Merged |

**Waves 1–3 and D4 are complete.** Wave 4 (monitor, onboarding, `briefr doctor`,
external Postgres compose) remains deferred.

### Post-B remaining work (authoritative: `POSTGRES_NATIVE_PLAN.md`)

| Phase | Scope | PRs left |
|-------|-------|----------|
| **1** | Postgres-native `db/*.py` modules | **~4** (`sync_state`, `watchlist`+`webhooks`, `cache_retention` done/in-flight) |
| **2** | Unify DB exception handling | 1 |
| **3** | Delete `db/dialect.py` (+ optional SQLite drop — needs operator OK) | 1–2 |
| **4** | CI backup dump → restore round-trip | 1 |

**Phase 1 next PR:** batch `db/metadata.py` + `db/correlation.py` (after `enrichment` merges).

**Phase 1 batching rule:** batch small independent modules; **solo PRs** for
`cve.py` and `init.py`.

### F3 follow-ups (before open-core flip, not blocking Post-B)

- [x] `SECURITY.md` + gitleaks CI (#319)
- [ ] Optional trufflehog pass
- [ ] F2 — AGPL decision + header/LICENSE reconciliation

### Ops (non-code, when ready)

Publish `briefr-intel-YYYY-MM.pgdump.gz` via `scripts/export_intel_snapshot.py`.

### Fresh-session read order

1. `CLAUDE.md` — rules and danger zones
2. `docs/PRODUCT_STATUS.md` — production truth
3. **This entry** — context and workflow
4. `docs/POSTGRES_NATIVE_PLAN.md` — Post-B execution detail
5. `docs/SPRINT_2026-07.md` — sprint checkboxes
6. `docs/PROGRAM_PRODUCT_OPEN_CORE.md` — open-core waves and locked decisions

### Environment reminders (Cursor Cloud)

- Postgres CI: `DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5432/briefr`
- Local SQLite tests: move `backend/.env` aside if it sets `DATABASE_URL`
- `graphify` may be unavailable — use grep/read after oriented
- Restart backend after secret changes (env vars win over `.env`)

---

## 2026-07-08 — Post-B Phase 1 PR 1: `db/sync_state.py` Postgres-native

**Session:** First module conversion — explicit `$n` / `?` SQL per backend in
`db/sync_state.py`; `DbConnection` typing; `tests/test_db_sync_state.py`. Merged #320.

### Next steps

**Post-B Phase 1 PR 2** — batch `db/watchlist.py` + `db/webhooks.py`.

---

## 2026-07-08 — F3: pre-flip security pass (SECURITY.md + gitleaks CI)

**Session:** Added root `SECURITY.md` (disclosure policy via harsha@projectjupiter.in),
`.gitleaks.toml` allowlist for placeholders/tests, and `.github/workflows/gitleaks.yml`
(full-history scan on push + PR). Historical scan clean except known test fixtures.
Merged #319.

### Next steps

**Post-B Phase 1** — module conversion (#320+).

---

## 2026-07-08 — Post-B Phase 0: logging ring-buffer fix (same PR as CI gate)

**Session:** `test-postgres` runs `pytest tests/ -q` (Phase 0 gate). CI initially
failed six logging tests: Alembic `fileConfig` during session migrations stripped
BRIEFR's ring-buffer handler after collection-time `from main import app`. Fix:
re-call `configure_logging()` after migrations in `conftest.py`, autouse ring-buffer
isolation (`clear_log_buffer` + `ensure_ring_buffer_attached`), and
`disable_existing_loggers=False` in `alembic/env.py`. Merged #318.

### Next steps

**F3** — pre-flip security pass (`SECURITY.md`, gitleaks CI).

---

## 2026-07-08 — Post-B Phase 0: Postgres full-suite CI gate

**Session:** `test-postgres` CI job now runs `pytest tests/ -q` against live
Postgres 16 (replaces pool-only + intel smoke subset). Gates module conversion.

### Next steps

**F3** — pre-flip security pass (`SECURITY.md`, gitleaks CI).

---

## 2026-07-08 — Wave 3 PR 9: export_intel_snapshot.py + CI smoke

**Session:** Added `scripts/export_intel_snapshot.py` (allowlisted `pg_dump`, manifest,
operator/sync_state guards). Postgres CI job runs `test_intel_snapshot_export.py`
round-trip restore smoke (Track J2).

### Next steps

**Wave 4 / parallel** — Post-B, F3 security pass, or operator settings in DB (deferred).

---

## 2026-07-08 — Wave 3 PR 8: DATA_SNAPSHOT spec + ADR-001

**Session:** Added `docs/DATA_SNAPSHOT.md` (INTEL vs OPERATOR table/key allowlists,
bundle format, verification rules) and `docs/decisions/ADR-001-intel-app-schema-split.md`.
Export script is Wave 3 PR 9.

### Next steps

**Wave 3 PR 9** — `scripts/export_intel_snapshot.py` + CI restore smoke (Track J2).

---

## 2026-07-08 — Wave 2 PR 6: asset profile persistence toggle

**Session:** My Stack inventory stays session-only by default; signed-in users can
toggle “Remember on server” (`remember_profile_on_server` on preferences). Server
profile hydrates on login; `PUT /api/me/stack` preserves `profile` when omitted.

### Next steps

**Wave 3 PR 8** — `DATA_SNAPSHOT.md` ADR + intel/operator table split.

---

## 2026-07-08 — Wave 2 PR 5: user preferences API + frontend migration

**Session:** Added `GET/PATCH /api/me/preferences` (display prefs + timezone);
migration `007_user_display_prefs`; frontend `userPreferences.js` migrates legacy
`briefr_*` localStorage on login. Privacy + Display admin copy updated.

### Next steps

**Wave 2 PR 6** — asset profile persistence (remember-on-server toggle).

---

## 2026-07-08 — D4: Nuclei parser + Sigma artifact injection

**Session:** Added deterministic `nuclei_parser.py`; `exploit_sync` enriches
`detection_ctx` for Nuclei-touched CVEs; generated Sigma merges artifact
keywords/paths (`briefr_artifacts`). Tests: parser fixture, sigma injection.

### Next steps

**Wave 2 PR 5** — `GET/PATCH /api/me/preferences` (display prefs migration).

---

## 2026-07-08 — Wave 2 PR 4: unified frontend stack

**Session:** Feed stack reads/writes `GET/PUT /api/me/stack`; legacy `briefr_stack`
localStorage migrates on login. KEV-on-stack + wallboard use saved user stack when
`BRIEFR_STACK_TERMS` env is unset. Privacy copy updated.

### Next steps

**D4** — Nuclei parser + Sigma artifact injection (sprint Track D).

---

## 2026-07-07 — Wave 1 PR 2 merged (#309); Wave 2 PR 3 in progress

**Session:** Merged toast policy + restart banner (H1a). Started Wave 2 PR 3 —
`user_preferences` table + `GET/PUT /api/me/stack` (terms + optional profile JSON
per user).

### Next steps

**Wave 2 PR 4** — frontend unified stack (remove `briefr_stack` localStorage split).

---

## 2026-07-07 — Wave 1 PR 2: toast policy + restart banner (H1a)

**Session:** Toast tray pauses auto-dismiss on hover/focus; errors/warnings persist;
success/info 8s; max 4 toasts; copy-ref “Copied” feedback. Admin restart paths
(config Save & restart, DATABASE_URL apply, backup schedule, manual restart/drain)
dispatch `notifyBackendRestarting()` and show a top **RestartBanner** (polls
`/api/health`) instead of a short restart toast.

### Next steps

**Wave 2 PR 3** — `user_preferences` + `GET/PUT /api/me/stack` migration.

---

## 2026-07-07 — Wave 1 PR 1: admin config Save UX (#308)

**Session:** Replaced queue-based Admin → API keys & config with per-field **Save**
/ **Save & restart**; bool toggles save inline; updated help copy. Gemini: use
`adminApi.postJson` for error handling.

### Next steps

**Wave 1 PR 2** — toast policy + restart banner (H1a). Then Wave 2 stack API.

---

## 2026-07-07 — Product / open-core program (PR #0)

**Session:** Planning session distilled into
[`PROGRAM_PRODUCT_OPEN_CORE.md`](PROGRAM_PRODUCT_OPEN_CORE.md) — SaaS-grade
admin UX (config Save, toast policy), user stack/prefs on Postgres, intel vs
operator table split, Postgres-only database FAQ, and phased PR waves for
open-core launch. July sprint **Track L** added as cross-links (E7, H1a, F1,
J2); sprint closed for new scope outside D4 + Post-B + program waves.

**Also:** PR #306 Gemini review — alphabetical sort fixes in Database, API
keys, and ML sections of `.env.example`.

### Next steps

1. Merge **#306** (env example reorder + Gemini fixes).
2. Merge **program doc PR #0**.
3. **Wave 1 PR 1–2** — config Save UX + toast policy (parallel with **D4**).

---

## 2026-07-07 — K4 DetectionContext LLM artifact extract

**Session:** Implemented **K4** — scheduler job `detection_context_llm` extracts
`{paths, params, keywords, method}` artifacts from CVE description + exploit
metadata (optional Nuclei YAML fetch) into `detection_ctx:{cve_id}` via the
LLM router (`detection_context` task chain: Groq → Gemini → OpenRouter).
Env-gated (`DETECTION_CONTEXT_LLM_ENABLED=0` default). Vision path (Cerebras
`gemma-4-31b`) deferred until image inputs exist.

### Next steps

**D4** — deterministic Nuclei parser + inject artifacts into generated Sigma
+ regen on `exploit_sync`. Post-B Postgres-native `db/` in parallel (Claude).

---

## 2026-07-07 — K1–K3 free-tier LLM router

**Session:** Implemented **K1–K3** — Groq model migration (`openai/gpt-oss-20b` /
`openai/gpt-oss-120b` for PDF summaries); new `ai/llm_router.py` with failover
Groq → Gemini Flash-Lite → Cerebras → OpenRouter `:free`; wired
`ml/product_extraction.py` and `ai/summary.py` through the router; dropped
Anthropic from the PDF chain; `feed_cache` provenance now records
`{provider, model}`.

### Next steps

**D4** unblocked for deterministic Nuclei slice; full LLM extract (K4) can follow.
Post-B Postgres-native `db/` before D4 if not started.

---

## 2026-07-07 — D5 Detect tab UI framing

**Session:** Implemented **D5** — Detect tab reframed as class-aware hunt
starters; `generated_sigma` always returned (supplement when community rules
exist); `generated_sigma_meta` API field; `briefr_basis` / experimental
tooltips in `DetectTab.jsx`.

### Next steps

**D4** blocked on K1–K3 (LLM router). Post-B Postgres-native `db/` before D4.

---

## 2026-07-07 — D3 unified class router

**Session:** Implemented **D3** — `_resolve_detection_class(cve)` in
`class_router.py`; class-keyed SIEM/log-pattern templates in
`class_queries.py`; wired through `sigma_generator`, `get_siem_queries`,
detection + forge endpoints. Sigma, SIEM, and log patterns now agree on
detection class when no ATT&CK technique is mapped.

### Next steps

**D4–D5** (D4 blocked on K1–K3 for LLM extract). Post-B Postgres-native
`db/` before D4.

---

## 2026-07-07 — D2 DetectionContext scaffold

**Session:** Implemented **D2** — `DetectionContext` cache scaffold for the
detection compose pipeline. New modules `detection/context.py` and
`detection/context_sync.py`; scheduler job `detection_context_sync`
(env-gated, default off); `generate_sigma_rule` reads cached envelope
(product/CWE/class); detection API returns `detection_context`; retention
prefix `detection_ctx:` in `cache_retention.py`.

### Next steps

Per execution queue: **K1–K3** (Groq migration deferred by user until closer
to Aug 2026), then **D3–D5**. Post-B Postgres-native `db/` after D1 (before
D4).

---

## 2026-07-07 — Sprint doc + D1 CWE Sigma templates

**Session:** Updated `docs/SPRINT_2026-07.md` with execution queue, expanded
Track D (detection compose pipeline), Track K (free-tier LLM), Post-B
Postgres-native note, C2 runner-up ticks. Implemented **D1**: CWE class
templates in `sigma_generator.py`, `briefr_basis` on generated rules,
`cwe_ids` wired through detection + forge endpoints.

### Next steps

Per execution queue: **K1–K3** (Groq migration + free-tier LLM router), then
**D2–D5**. Post-B Postgres-native `db/` after D1 (before D4).

---

## 2026-07-06 — Sprint topics reconciled; Track J (deployment) added

**Session:** docs only — no code changed. Four planning sessions on
`Soldier0x0/briefr` ended abruptly; this session recovers their topics
into `docs/SPRINT_2026-07.md` so nothing is lost. Branch
`claude/sprint-document-topics-i1xvjp`.

### What changed

- **Reconciliation note** (top of the sprint doc): maps each abrupt
  session to its track — *Codebase architecture review* → Track B
  (closed, B1–B5), *Production performance optimization* → Track I,
  *Production UI component architecture* → Track H, *Production
  deployment planning* → new Track J.
- **Track J — Production deployment / release planning** (new). Records
  the grounded deploy surface to plan against (`deploy/` scripts +
  systemd units + the OPERATIONS/ROADMAP compatibility promise), not
  fabricated specs — the originating session was cut off before its
  decisions were written down. Items: J1 update/rollback safety audit,
  J2 backup→restore round-trip in CI, J3 post-deploy smoke gate, J4
  release/version phasing checklist. Cross-references (not duplicated):
  multi-worker → I Phase 3, nginx gzip → I2, CI Postgres round-trip →
  "After Track B" note.

### Verified against code (`main` @ `5713682`) before writing

- Track B: `backend/database.py` is a 45-line shim, `backend/db/` split
  is in code → B correctly closed.
- Track H: `frontend/src/components/ui/` does not exist yet; `Toast.jsx`
  already at `components/` → H open items stand as written.
- Track I: `db/` files present, no gzip in `deploy/nginx-briefr.conf`
  → I open items stand. No adjustments needed to A–I.

### Next steps

Track J needs a real spec once the deployment-planning session's
decisions are recovered — until then J items are plan/audit only, per
the doc's "verify code first" convention. Open code work per sprint:
**Track D — D1** (CWE→Sigma mapping, spec ready) or **Track H/I** items.

---

## 2026-07-06 — Track C closed (C1–C3); C2 fields shipped

**Session:** C3 retention/TTL audit + implementation. C2 PRs #279–#281 merged on `main`
before this session (CAPEC drawer, SSVC parser/drawer, KEV ransomware feed badge).

### What merged / shipped

- **C2 — PRs #279–#281.** CIRCL `capec_ids` chips in drawer; Vulnrichment SSVC
  parsed to `feed_cache` + drawer section; `kev_ransomware_use` on feed cards.
- **C3 — PR pending.** Retention map in `docs/SPRINT_2026-07.md`; new
  `backend/db/cache_retention.py` + daily `cache_retention_cleanup` scheduler job;
  admin `change_history_old` purge fixed (`detected_at` column, was broken).

### Next steps

Track C (C1–C3) is complete. Next per sprint plan: **Track D — D1**
(CWE→Sigma template mapping in `sigma_generator.py`), or interleave **Track I**
(performance) / **Track H** (UI primitives) per maintainer preference.

---

## 2026-07-06 — Track A closed out (A4–A7); Track B is next

**Session:** docs sync only — no code changed this session. Confirmed
against `origin/main` (local `main` was 5 commits stale) that Track A
finished since the 2026-07-05 entry below, via PRs #265–#267. Two more
commits landed after that, outside the sprint tracks: #268 (Mermaid
architecture diagrams refreshed) and #269 (graphify knowledge-graph
integration added for Cursor — `.cursor/rules/graphify.mdc`,
`.graphifyignore`, `graphify-out/` now committed).

### What merged

- **A4 + A5 — PR #265.** `PoolExhaustedError` handler now returns a fixed
  "Server is busy..." message instead of `str(exc)` (exception stays in the
  log only; the old test asserting `str(exc)`-in-response was updated).
  A5 was an inventory-then-fix pass over every analyst-facing async view
  (`CVEFeed`, `MorningBrief`, `IOCLookup`, `CaseStudies`, `DetailDrawer`/
  `openCveDrawer.js`, `BriefCharts`, `TimelineHeatmap`, `WhatChangedPanel`,
  `Sidebar`, `StatsRow`, `Forge`) — each now has message + `ref:<request-id>`
  + retry, no silent failures. Full per-component before/after inventory is
  in `docs/SPRINT_2026-07.md` under A5. Explicitly left silent:
  `FeedRefreshStatus` and DetailDrawer's best-effort secondary tabs
  (momentum, detection sparkline) — documented rationale, not an oversight.
- **A6 — PR #266.** `settings.production_posture_warnings()` reports every
  unsafe flag (`RATE_LIMIT_ENABLED=0`, `AUTH_COOKIE_SECURE=0`,
  `WALLBOARD_TOKEN` unset) as one warning per flag at startup when
  `BRIEFR_ENV=production`; `GET /api/admin/security` surfaces the same list
  in the existing Security panel as amber callouts. Also fixed a stale
  "Auth: None on any endpoint" line in `API_REFERENCE.md` left over from
  pre-A0.
- **A7 — PR #267.** Wallboard token now header-only
  (`X-BRIEFR-Wallboard-Token`); `?token=` query param rejected (leaked into
  access logs/history). Dropped the deprecated `X-XSS-Protection` header
  from backend middleware and all nginx configs. CSP tightened to
  self-only for `style-src`/`font-src` — fonts turned out to already be
  self-hosted via `@fontsource` (`main.jsx`), so the Google Fonts CSP
  allowances were dead weight, not an active dependency the item expected
  to remove. Fixed the stale "SQLite pins us to one worker" docstring in
  `rate_limit.py`; documented in `briefr-backend.service` that
  `--workers 1` is deliberate (in-memory rate-limit buckets are per-worker).

### Next steps

Track A (A0–A7) is fully closed. Next is **Track B — structural refactor**,
starting with **B1** (CVE ID validator helper, ~25 lines) per
`docs/REFACTOR_PLAN.md`. Rules unchanged: one phase = one PR = one deploy,
full `pytest` + `npm run build` green before advancing, B3 (`database.py`
split) is the risky phase and needs a careful diff review, B4–B5
additionally need hand verification in the browser (drawer tabs, PDF/XLSX
export).

---

## 2026-07-05 — Security architecture review; sprint gains A0/A6/F3

**Session:** maintainer + AI security review. **Docs-only — no code
changed.** Findings verified by reading `dependencies.py`, `routers/auth.py`,
`settings.py`, `rate_limit.py`, `db/connection.py`, `utils/exportXlsx.js` —
not from docs. Since the 2026-07-03 entry, main also picked up PR #257
(DETECT tab 500 on Postgres — a live danger-zone-#1 hit) and PR #258
(admin log search); branch `fix/deploy-npm-ci-not-install` (npm ci for
production frontend builds) was open at session time.

### Findings (verified against code)

1. **`require_admin` fails open by default.** `allow_legacy_admin_key`
   defaults true; with `BRIEFR_ADMIN_API_KEY` unset (the normal case since
   built-in login shipped) every admin route is **unauthenticated** unless
   CF Access happens to sit in front. Decision: **delete the legacy key
   path entirely** — not gate it. Sprint A0 + Spec A0.
2. `require_admin` never checks the JWT `role` claim — any authenticated
   user is admin. Latent until a second user exists; folded into A0.
3. `audit()` catches only `sqlite3.OperationalError`; the Postgres wrapper
   raises raw asyncpg errors, so an audit-write failure can 500 a valid
   admin action in production (danger zone #1 in exception space, not SQL
   space). Immediate fix in A0; class fix added to the post-Track-B
   native-SQL conversion notes.
4. Wallboard token accepted via query string (leaks into access logs /
   history; low severity, read-only surface). Sprinted as **A7** together
   with the deprecated `X-XSS-Protection` header, Google-Fonts CSP
   allowance (vendor the fonts for air-gap credibility), and the stale
   single-worker rate-limit docstring.
5. **Clean checks — no action:** XLSX export uses ExcelJS string cells
   (no formula injection from upstream CVE text), no
   `dangerouslySetInnerHTML` anywhere, webhook SSRF tests exist, refresh
   rotation + reuse detection solid, rate-limit proxy trust solid.

### Plan changes (edited `docs/SPRINT_2026-07.md` this session)

- Track A: new **A0** (delete legacy key + role check + audit fix +
  security-invariant tests; one PR, mostly deletions — do **before**
  A2/A3), **A6** (production posture self-check), and **A7** (security
  hygiene: wallboard header-only, drop X-XSS-Protection, vendor fonts,
  worker-pin note). A1 ticked (PR #255).
- After-Track-B notes: one app-level DB exception type, no `sqlite3.*`
  handling outside `db/`, CI dump→restore round-trip for backups.
- Track F: new **F3** pre-flip security pass (gitleaks over full history,
  rotate any committed key, `SECURITY.md`, reconcile "All rights reserved"
  headers with AGPL) — blocks the open-source flip.
- Appendix: **Spec A0** with the verified removal scope. Gemini review of
  PR #260 caught that the legacy key is **runtime-rotatable** (SecurityPage
  Rotate flow → `POST /config/apply-all` → `APPLY_ALL_EXTRA_KEYS`) and that
  `api.js` still attaches `X-BRIEFR-Admin-Key` on adminApi requests — spec
  expanded to delete the whole rotation chain, frontend included.

### Explicitly rejected (don't re-litigate)

2FA/OIDC, CSRF tokens, Redis-backed rate limiting — wrong size for a
single-operator self-hosted app with `SameSite=Strict` cookies and
optional CF Access. Scoped API tokens only when a real machine consumer
appears.

### Next steps

1. **A0** per Spec A0 (check the production crontab/systemd timers for
   `X-BRIEFR-Admin-Key` callers before merging).
2. A2+A3 per spec; A4 rides along. Then Track B unchanged.

---

## 2026-07-03 — Strategy, repo cleanup, error-loop plan, July sprint

**Session:** maintainer + AI planning/execution session. All output landed
on branch `claude/briefer-tool-strategy-0mj158` → **PR #246-era main, PR
#255**. Commits: strategy doc → embeddings dead-code fix → learning path →
CLAUDE.md/doc cleanup → sprint checklist → this handover.

### What changed and why

| Change | Where | Why |
|---|---|---|
| Product strategy written | `docs/STRATEGY.md` | Define the path from late-beta personal project to adopted community tool: detection-quality ladder (templates → CWE mapping → exploit-artifact injection → pySigma validation → proof bench), measured "minutes saved" metric, adoption plan (license → Docker → launch), interview-readiness (ADRs). Explicitly rejects training a custom rule-generation ML model. |
| Dead `sqlite-vec` path removed | `backend/ml/embeddings.py` + live docs | The accelerator could never run: not in requirements, and the Postgres connection wrapper exposes no `enable_load_extension`. Docstring/docs claimed vectors lived "in SQLite" — false in production. Tests: 25 passed. |
| Learning curriculum | `docs/LEARNING_PATH.md` | Maintainer must be able to defend every subsystem without AI help (career goal). Eight modules, trace exercises, interview self-checks. |
| `CLAUDE.md` rewritten project-specific | `CLAUDE.md` | Was generic LLM advice. Now: commands, source-of-truth order, six danger zones (SQL dialect translation #1), error-handling conventions, UI rules (incl. **no wide side margins / no centered narrow columns** — repeated agent failure mode), docs rules. |
| Snapshot banners + stale-claim fixes | `CODEBASE_CONTEXT.md`, `FOLDER_STRUCTURE_GUIDE.md`, `APPLICATION_EXECUTION_MAP.md`, `TECHNICAL_INVENTORY.md` | These lag the code (CODEBASE_CONTEXT claimed SQLite storage; TECHNICAL_INVENTORY claimed React 18). Banner: `docs/PRODUCT_STATUS.md` and the code win. |
| Root cleanup | deleted `Beta V*.md` stubs, `SYSTEM_DESIGN.pdf`, `TECHNICAL_INVENTORY.xlsx`, `architecture-map.html` (now gitignored) | Redirect stubs served their purpose; binary artifacts are generated on demand by `scripts/` and only drift in git. All referencing docs updated. |
| July sprint checklist | `docs/SPRINT_2026-07.md` | Single execution list; tracks A–G with per-item acceptance criteria. |

### Key findings about the codebase (verified, not assumed)

1. **SQLite is not fully gone.** Production is Postgres-only, but all SQL in
   `database.py` is SQLite-dialect, translated at runtime by regex in
   `db/dialect.py`; tests run SQLite. This layer is the highest-risk code.
2. **`docs/REFACTOR_PLAN.md` is accurate as of 2026-07-03** — line tables
   verified against code (11 CVE-ID duplications, 14 locks, `database.py`
   = 3,197 lines, function line numbers exact). Safe to execute.
3. **Error handling backend is done, frontend is half-done.** Backend:
   request_id middleware, `X-Request-ID` header, generic 500 + full
   traceback logged, secret redaction. Admin log viewer **already filters
   by request_id**. Missing: `frontend/src/api.js` drops the header, so
   users can't quote the ref id; no app-wide error toast (one exists under
   `pages/admin/shared/Toast.jsx` only); `PoolExhaustedError` handler
   returns `str(exc)`.
4. **CI is strong:** backend tests, a Postgres services job, pip/npm
   audits, Playwright smoke that builds the frontend. No lint config.
5. Detection generation is **template-based** (14 ATT&CK-technique Sigma
   templates + hash-led YARA); the only ML is optional embeddings +
   optional LLM product extraction. Describe it accurately everywhere.

### Decisions with rationale (agreed by maintainer)

1. **Order of operations: structural refactor FIRST, Postgres-native SQL
   second.** The plan is fresh now; moves are behavior-neutral and safe
   under SQLite tests; post-split modules convert to native SQL one PR at
   a time; delete `db/dialect.py` last.
2. **Refactor execution rules:** one phase = one PR = one deploy; full
   `pytest` + `npm run build` between phases; never proceed past red.
3. **Future DB boundary: Postgres schemas `intel` (shareable CVE/KEV/EPSS/
   ATT&CK + own-derived data) vs `app` (users, sessions, caches, audit).**
   NOT a return to a separate SQLite file. Third-party API caches
   (VT/AbuseIPDB/GreyNoise/OTX) must stay private — upstream ToS forbid
   redistribution, which also rules out selling enriched DB dumps.
4. **Monetization reality:** career ROI first; then open-core, managed
   hosting (customers' own API keys), self-authored detection content
   packs, GitHub Sponsors (`.github/FUNDING.yml` at open-source flip).
   License recommendation: AGPL-3.0, decided at flip time (Track F).
5. **No custom-trained ML for rule generation** — deterministic synthesis
   from exploit artifacts + validation is the differentiator.
6. **UI direction:** keep terminal identity; polish = designed
   loading/empty/error/data states, stat-tile deltas, tooltip coverage,
   IOC auto-detect, restrained motion (120–180ms) — not margins, not
   decoration. Screenshots reviewed were a few days old; re-verify
   individual critique items against the live app before fixing.

### Next steps (in order — see `docs/SPRINT_2026-07.md` for full detail)

1. Merge **PR #255** (contains everything above).
2. **Track A:** A2 (capture `X-Request-ID` in `api.js`) + A3 (app-wide
   error toast, ref id links to admin log viewer pre-filtered) — smallest
   visible win, do before the refactor.
3. **Track B:** refactor phases 1–5 per `docs/REFACTOR_PLAN.md`.
4. Tracks C–G per sprint doc; weekly rhythm at its bottom.
