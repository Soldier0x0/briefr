# Planning backlog (open / parked / optional)

**Purpose:** single queue for work that is **not** done — extracted from merged planning
docs so nothing is lost when specs move to [`archive/superseded/`](../archive/superseded/) or stay in [`specs/`](specs/).

**Rules**

| Symbol | Meaning |
|--------|---------|
| 📋 | Ready to implement when maintainer activates |
| 🔶 | Partially shipped — see note |
| 💬 | Needs operator/maintainer decision before build |
| 🅿️ | Parked — explicit signal required |
| ✅ | Shipped — listed only so it is **not** re-queued |

**Authoritative runtime truth:** [`../PRODUCT_STATUS.md`](../PRODUCT_STATUS.md) and
[`../HANDOVER.md`](../HANDOVER.md). **Build order when activated:** add checkboxes to
[`SPRINT_2026-07.md`](SPRINT_2026-07.md) or a future sprint doc.

**Last reconciled:** 2026-07-15 against `main`. Post–UI E2E UX observations master plan added
([`specs/e2e-ux-observations-2026-07-15.md`](specs/e2e-ux-observations-2026-07-15.md)).

---

## 1. Sprint checklist (still open)

| ID | Item | Status | Source |
|----|------|--------|--------|
| **O-3** | `WALLBOARD_TOKEN` in `config_schema` + admin save/rotate (Security copy already points at API keys & config; field is **env-only** today) | ✅ #514 |
| **G0** | Refresh `LEARNING_PATH.md` + `ONBOARDING.md` for final shipped system | 🅿️ end-of-lifecycle | Sprint §G |
| **G1–G4** | Maintainer modules 1–4 (trace + private notes) | 🅿️ end-of-lifecycle | Sprint §G |
| **Phase 4 STIX/Sigma export** | V1.5 tail | 🅿️ | Sprint V1.5 |
| **Detection composer** | Evidence-composed Sigma/KQL/SPL/QRadar/YARA (no LLM default); replace Forge keyword templates; shared drawer Detect + Forge | 🔶 DC-1 shipped — DC-2…DC-4 open | [`specs/detection-composer-design.md`](specs/detection-composer-design.md) |

---

## 2. Correlation engine v3 program — **complete**

**Canonical spec:** [`specs/correlation-engine-v2.md`](specs/correlation-engine-v2.md)  
**All phases shipped 2026-07-12…2026-07-14 (#473…#513).** [PG-001](#pg-001--cross-file-pytest-pollution-on-real-postgres-found-2026-07-12-fixed-2026-07-12)
is fixed — no longer a blocker.

| PR | Title (phase) | Status |
|----|---------------|--------|
| PR-1 | Rank infrastructure peers by evidence (0) | ✅ #473 |
| PR-2 | Composite index + drop `correlation_infrastructure` (0) | ✅ #476 |
| PR-3 | `ioc_degree` + degree-penalized edge confidence (1) | ✅ #487 |
| PR-4 | Remove severity/size from confidence (1) | ✅ #488 |
| PR-5 | Confidence factor vector in API + drawer (1) | ✅ #489 |
| PR-6 | Capture `observed_at` on pulse IOCs (2) | ✅ #501 |
| PR-7 | Lifecycle + momentum use observation time (2) | ✅ #506 |
| PR-8 | Read-time freshness decay + UI staleness (2) | ✅ #508 |
| PR-9 | Pulse families + campaign dedup + retraction (3) | ✅ #509 |
| PR-10 | ThreatFox corroboration on IOC edges (3) | ✅ #510 |
| PR-11 | Alias-aware attribution + conflict surfacing (4) | ✅ #511 |
| PR-12 | Analyst confirm feedback (4) | ✅ #512 |
| PR-13 | `correlation_metrics` nightly + admin + feed-boost gating (4) | ✅ #513 |

**Maintainer open questions (§21):** confidence regression comms (PR-4+5); pulse-family
thresholds (PR-9); suppression migration on dedup (PR-9); confirm-link UI vs API-only
(PR-12); half-life defaults (PR-8); feed ordering change (PR-13/D9); scale verification
before PR-9.

---

## 3. Codebase security / reliability / performance audit

**Canonical spec:** [`specs/codebase-audit.md`](specs/codebase-audit.md)  
**Shipped in #449:** AUTH-001, AUTH-002, VAL-002, IDEM-001/TXN-001, DB-001, DB-002.

### Remaining remediation PRs (§17)

| PR | Title | Status |
|----|-------|--------|
| PR-P3 | Index `cves.modified` | ✅ #516 |
| PR-P4 | KEV upsert batching | ✅ (this PR) — `upsert_kev_batch` executemany in 500-row chunks; `_run_kev_sync` uses it |
| PR-O1 | Feed empty → scheduler `had_error` | ✅ #517 |
| PR-F1–F4 | Admin gate, safe URLs, fonts, loadStats | ✅ #518 |
| PR-O2 | Correlation GET read-only split (CACHE-001) | ✅ (this PR) |

### API key health & quota clarity (found 2026-07-12)

**Findings doc:** [`specs/api-key-health-and-quota-findings.md`](specs/api-key-health-and-quota-findings.md) — observation/RCA only, no code changes yet.

| PR | Title | Status |
|----|-------|--------|
| **AKH-1** | Fix `api_key_health.py::_ping_json` positional-arg bug (`TypeError: resilient_request() got multiple values for argument 'source'`) — every provider health check has failed on every run since the feature shipped; also fix the notification dedupe key (currently includes a per-run timestamp, so it never dedupes) | ✅ #482 |
| **AKH-2** | Quota-system UI clarity: rename Admin "Rate limit" nav (collides with unrelated outbound provider quota), wire or remove the dead `fetchUsage()`/`GET /api/usage` endpoint (zero frontend callers today), HelpTip explaining quota vs pacing vs inbound throttling. Narrows Issue 21 + folds into UX-J1 | ✅ #486 + #519 |

### QA audit — functionality/UI/ops (found 2026-07-12, live-verified)

**Findings doc:** [`specs/qa-audit-2026-07-12.md`](specs/qa-audit-2026-07-12.md) — observation/RCA only, no code changes yet. Reproduced live against a running dev instance (not static analysis).

| PR | Title | Status |
|----|-------|--------|
| **QA-F1** | DetailDrawer DETECT tab: parallelize external rule-source calls (GitHub Search blocks the whole response 15-30s, unauthenticated in dev); fix frontend/backend timeout mismatch causing a false "request timed out" on every uncached CVE | ✅ #484 — shipped as skip-when-unauthenticated, not parallelization (see PR body: parallelizing would have reintroduced a pool-poisoning regression) |
| **QA-U1** | DetailDrawer header: real 193px clip (not wrap) at 375px width — action button row needs a responsive collapse/overflow menu. Folds into UX-C1/C2 scope | ✅ #520 |
| **QA-U2** | Accent-color design pass for drawer content — token renders correctly but only 2-3 touches per tab, reads as "lost." Design judgment, not a coded fix | ✅ (this PR) |
| **QA-U3** | Global header: 29px real overflow at ~375px width (narrow-device edge case) | ✅ (this PR) |

### QA live audit round 2 (found 2026-07-12, `qa-live-audit-2026-07-12-part2.md`)

Independently re-verified — of 17 Emergent-agent + Emergent-adjacent claims tested live, 6 confirmed real (below), 11 refuted/overstated. See findings doc for the full verification log, including the 11 refutations with evidence.

| PR | Title | Status |
|----|-------|--------|
| **QA-P2-1** | Brief KPI stat tiles: "₀" flat-delta reads as noise next to the large stat number (12px muted number at same baseline as 40px number). Prefix flat/nonzero deltas with `Δ`, or hide when exactly 0 | ✅ #483 |
| **QA-P2-2** | Admin Overview: "DATABASE HEALTH" card only ever says "checked on startup" with no refresh affordance on the card | ✅ #483 |
| **QA-P2-3** | Admin Overview: "NIST CVE FEED" stat card shows a bare em-dash with no explanation of why (sub-label only describes normal cadence, not current blank state). Isolated to this one card, not systemic | ✅ #483 |
| **QA-P2-4** | Forge: GAP/COMMUNITY/YOURS coverage chips have no per-chip `title`/`aria-label` — only a generic group label. Add per-chip tooltips | ✅ #483 |
| **QA-P2-5** | IOC Lookup: input placeholder crams all 3 example formats (IP/hash/domain) into one string, copy-pasteable as a single invalid value. Cycle one example, or move to a hint line below the input | ✅ #483 |

### Restart / durability bundle (§Z)

| PR | Title | Status |
|----|-------|--------|
| PR-R1 | Await scheduler + background tasks on shutdown | ✅ (this PR) |
| PR-R2 | LLM extraction idempotency / response staging | ✅ (this PR) |
| PR-R3 | Webhook claim-before-send (extends IDEM-001) | ✅ verified complete 2026-07-14 — `webhooks/engine.py` claims the dedupe key (committed) **before** the HTTP send and rolls the claim back on failed delivery; shipped as part of IDEM-001 (#449), no remaining gap |
| PR-R4 | Persist migration status to `sync_state` | ✅ (this PR) |

### Runtime validation (9× NEEDS RUNTIME VALIDATION)

Run on production-like Postgres before closing: production CORS origins (TRANS-002) and
other items flagged in audit §6 — see codebase-audit status table.

### PG-001 — Cross-file pytest pollution on real Postgres (found 2026-07-12, fixed 2026-07-12)

**Root cause (confirmed empirically, not the originally-suspected `close_pool()`
timeout or scheduler-job mechanism):** `tests/test_db_explorer.py` had two raw,
non-`monkeypatch` mutations that never revert:

1. A **module-level** `os.environ["DATABASE_URL"] = ""` (module-level code can't use
   `monkeypatch`, so this ran once at import/collection time and stayed wiped for the
   rest of the pytest process). This broke `tests/conftest.py::_postgres_dsn_or_none()`
   (a raw `os.environ.get("DATABASE_URL")` read, unlike the rest of the codebase's
   settings-safe `resolve_database_url()`) — and, verified separately, would have
   collaterally corrupted every *other* test file's `@pytest.mark.skipif(os.environ
   .get("DATABASE_URL", "")...)` decorator collected afterward in the same invocation
   (`test_admin_storage.py`, `test_backup_roundtrip_postgres.py`, `test_forge.py`,
   `test_wallboard.py`, `test_watchlist.py`, and others share this pattern).
2. Inside the `admin_client` fixture, `_main_mod.is_postgres = lambda url=None:
   False` and both `run_postgres_migrations` reassignments used **raw attribute
   assignment** instead of `monkeypatch.setattr(...)` — permanently breaking
   `main.py`'s own Postgres detection for every later `TestClient(app)`-driven test
   in the same process, which is what actually produced the `close_pool(): timed out
   after 5s` warnings and the eventual `duplicate key … cves_pkey` failures (stale
   rows surviving because the isolation `TRUNCATE` step got silently bypassed).

**Fix (`tests/conftest.py`, `tests/test_db_explorer.py`):** `_postgres_dsn_or_none()`
now uses the settings-safe `resolve_database_url()`; the three raw assignments became
`monkeypatch.setattr(...)`; the module-level `os.environ` wipe was removed entirely
(the fixture-level scoped monkeypatches already cover this file's own need to force
SQLite mode).

**Verified:** `pytest tests/test_correlation.py tests/test_db_explorer.py -q` on
Postgres — was 15 failed / 26 passed, now **52 passed / 1 skipped**, and the
`close_pool()` timeout warnings are gone too (confirming they were a symptom, not an
independent bug). Spot-checked `test_db_explorer.py` + `test_forge.py` +
`test_wallboard.py` + `test_watchlist.py` together on Postgres: 43 passed / 5 skipped,
no collateral skip-decorator corruption. Full SQLite suite green (no regressions).

| Item | Status |
|------|--------|
| **PG-001** | Diagnose + fix cross-file Postgres test pollution | ✅ fixed 2026-07-12 |
| **PG-002** | Set up a documented persistent local Postgres for dev/CI (native service already exists on this machine at `localhost:5432`; OR fix `deploy/docker-compose.postgres.yml` port conflict guidance) so the CLAUDE.md dual-DB rule stops being aspirational | ✅ `scripts/postgres-dev.sh` (:5433 disposable) + POSTGRES/ONBOARDING/verify-local |
| **PG-003** | Cross-file **SQLite** test pollution (found 2026-07-13, FR-3 session): full-suite `pytest tests/ -q` showed `test_api_key_health.py` + `test_db_explorer.py::test_unauthenticated_returns_401` failing, but both passed standalone. Same *class* as PG-001 but different files, SQLite backend | ✅ verified not reproducible 2026-07-14 — three full SQLite suite runs green (1245→1262 passed, only corpus-drift failures which were fixed separately in #524). Likely fixed as a side effect of the PG-001 conftest hardening; re-open with a failing seed if it recurs |

### Track M (security/ops audit — mostly shipped)

**Historical source:** [`../archive/superseded/SECURITY_AND_OPS_AUDIT_2026-07.md`](../archive/superseded/SECURITY_AND_OPS_AUDIT_2026-07.md)  
**Shipped:** M-1…M-7, M-5 (#442), partial M-6–M-10 per sprint.

| ID | Item | Status |
|----|------|--------|
| **M-8** | `app_settings` secret policy — encrypted DB when `BRIEFR_SETTINGS_KEY` set (ADR-006); env still primary | ✅ |
| **M-9** | Ingest `next_run_time` from `scheduler.last_run` (no immediate NVD/KEV/EPSS on restart) | ✅ (this PR) — `_restore_ingest_next_runs` re-anchors NVD/KEV/EPSS to last-run + interval; overdue jobs run +2min after boot, never postponed beyond the trigger default |
| **M-10** | Global backup mutex (fcntl) — partial via #431 flock | ✅ verified complete 2026-07-14 — `_create_archive_bundle` + `prune_backups` run only inside `run_backup`'s `.backup.lock` flock; all creators (scheduled job, admin manual) route through `run_backup`. fcntl-less platforms (Windows dev) fall back to no lock by design |

---

## 4. AI operations (conditional tail)

**Canonical spec:** [`specs/ai-operations.md`](specs/ai-operations.md)  
**Shipped:** AI-1…AI-2 (#416–#417), retention #418, filters #419, tokens #420, quota snapshots #432, K5 pacing #433.

| Item | Status | Notes |
|------|--------|-------|
| **AI-3** (PR-AI-6+7+8) | 💬 conditional | Measurable 28-day evidence gate now defined in spec header: fallback rate > 10 %, pacing deferrals ≥ 3 days, or template-served analyst summary. None met → stays parked (good outcome) |
| PR-AI-7 | Model catalog refresh job | 📋 part of AI-3 |
| PR-AI-8 | Routing policy extraction + advisory headroom | 📋 part of AI-3 |
| OpenAI provider | deferred | Not in V1 chain |
| §26 deferred | chat, RAG, agents, STIX-LLM, browser automation | 🅿️ permanent defer |

---

## 5. UX / operator UI (deferred from audit)

**Canonical spec:** [`specs/ux-audit.md`](specs/ux-audit.md)

| ID | Item | Status |
|----|------|--------|
| **28** | Application logs — structured `extra` + expandable row in `IngestLogPage` | ✅ verified shipped — expandable rows with structured extras + tracebacks exist in `IngestLogPage`; `job_log_context` binds job_id/run_id |
| **29** | Audit logs — expandable actor/action context; optional `metadata_json` | ✅ (this PR) |
| **30** | Log search — server-side time range + `job_id` filter | ✅ (this PR) — `since`/`until` ISO bounds added; `job_id` filter already existed |
| **31** | Failure observability — shared `run_id` linking toast → scheduler → logs | ✅ verified shipped — `job_log_context` run_id persisted in last-run history; `JobTable` links to logs filtered by `run_id` |
| **32** | Scheduler manual trigger duplication (`MANUAL_PIPELINES` vs `JobTable`) | ✅ (this PR) — section retitled "Pinned quick triggers" with HelpTip clarifying the single shared run path |
| **33** | Scheduler table — search/filters at ~3 pages of jobs | ✅ (this PR) — status chips existed; job name/id search box added |
| **PR3 follow-up** | Migrate analyst `title=` tooltips on `CVECard` / `DetailDrawer` to `HelpTip` | ✅ complete — CVECard/chrome (#538) + drawer tabs (#539) |
| **37 / UX-C1** | Interactive control consistency — drawer buttons + tabs to `.ui-btn` standard (Issue 37) | ✅ shipped (#474) |
| **37 / UX-C2** | CVE card action row + feed surfaces to `.ui-btn` standard (red = destructive only) | ✅ #475 |
| **38 / UX-J1** | Domain-term explanation sweep (PRODUCT.md principle 6): KEV, EPSS, CVSS, CWE, CAPEC, ATT&CK IDs get HelpTip/ExplainTip coverage on feed, drawer, Forge | ✅ (this PR) — audit found feed mostly covered (FilterBar/StatsRow/CVECard EPSS); filled gaps: drawer CWE tags, ATT&CK section hint, CVECard CVSS badge, Forge KEV badges + CWE/EPSS columns + pack context line |
| **39 / UX-L1** | "Scope & limits" panel in About modal — render PRODUCT.md Scope & Limits content (copy is final, JSX only); browser-verify with the UX-C1 pass | ✅ (this PR) |
| **Issue 21** | API key suffix + provider health ping in UI | ✅ (this PR) — health table + Run check now on API keys page; suffix beside masked secrets |
| **UI overhaul 3a** | Dismissible config banner (not permanent amber) | ✅ verified already fixed — the permanent `load_dotenv` amber banner no longer exists in `ApiKeysPage` |
| **UI overhaul 3b** | Status legend component | ✅ (this PR) — orphan `StatusLegend.jsx` corrected (LOCKED/PAUSED/DISABLED copy now matches scheduler HelpTips) and mounted as a collapsible disclosure in the admin sidebar footer |
| **UI overhaul §6** | Restart dropdown portal (clipped menu) | ✅ verified already fixed — `StatusBar.jsx` renders the restart menu via `createPortal` + `getBoundingClientRect` positioning |

**Shipped (do not re-queue):** PR1–PR11, PR12 (#413–#415), PR13 (#422), notification center (#439), O-1/O-2 (#428), O-3 (#514), wallboard v2 core (#430), K5 (#433), UX-C1 (#474), UX-C2 (#475).

---

## 5b. Active open queue (verified 2026-07-14)

Flat backlog after major programs above — **no strict order**; pick from here or §3–§9:

| Bucket | IDs |
|--------|-----|
| Codebase audit | — complete (PR-P3/P4/O1/O2/F1–F4 ✅) |
| API key health tail | AKH-2 (remove dead `/api/usage`, HelpTip on Inbound limits) |
| QA / UX | QA-U2 (design pass, deferred) | ✅ (this PR) |
| Durability | — (PR-R1/R2/R4 ✅; PR-R3 verified as IDEM-001 overlap in #449 scope — see §3) |
| Ops / test infra | — (M-9 ✅, M-10 verified, PG-002/003 ✅) |
| Resource benchmarking | — (RB-1/RB-2 complete) |
| UX audit deferred | §5: item 29 ✅, PR3 follow-up ✅ (items 28/30–33, UI 3a/3b/§6 ✅) |
| Wallboard optional | §7 optional rows |

---

## 6. Threat Modeling & Security Architecture module — **committed program complete**

**Canonical spec:** [`specs/threat-modeling-security-architecture.md`](specs/threat-modeling-security-architecture.md) (**v2**, #460/#461)  
**TM-0…TM-5 shipped 2026-07-12…2026-07-13 (#491–#497).** TM-6+ framework workspaces remain
evidence-gated (not queued). Execution per [`specs/execution-playbook.md`](specs/execution-playbook.md).

| PR | Title | Status |
|----|-------|--------|
| **TM-0** | Design plan v2 (evidence-gated, self-stack) | ✅ #458 + v2 #460/#461 |
| **TM-1** | Corpus **generator** + loader + drift CI (generated/curated split) | ✅ #491 |
| **TM-2** | Shell UI + Overview evidence tiles (route, header tab ARCH) | ✅ #493 |
| **TM-3** | Live sections: MITRE + Threat Scenarios + Controls + self-stack exposure | ✅ #494 |
| **TM-4** | System Architecture graph + Trust Boundaries + Attack Surface | ✅ #496 |
| **TM-5** | Risk Register + Decisions + Review History + Abuse Cases + Search + PDF | ✅ #497 |
| **TM-6+** | Framework workspaces (STRIDE, OWASP×2, NIST, ASVS, CAPEC, CWE) | 💬 evidence-gated, one PR each — gate in spec §8 |

**Scope (v2):** every committed section must cite a generated or live data source;
hand-authored-YAML-only sections do not ship. No composite grades — drill-through
tiles only.

---

## 6b. Forge redesign program — **complete**

**Canonical spec:** [`specs/forge-redesign.md`](specs/forge-redesign.md) (#460/#461)  
**FR-1…FR-3 shipped 2026-07-12…2026-07-13 (#490, #492, #495).**

| PR | Title | Status |
|----|-------|--------|
| **FR-1** | Hunt pack list + delete API (`GET /api/hunt-packs`, `DELETE /{id}`, audit entry) | ✅ #490 |
| **FR-2** | Three-panel shell + `?view=` URL state + Library view + persistent Hunt Pack rail | ✅ #492 |
| **FR-3** | Live-data enrichment (atlas case studies, KEV notifications, CWE/EPSS) + pack PDF export | ✅ #495 |

---

## 7. Wallboard optional / kiosk tail

**Core v2 shipped #430; kiosk runbook #442.** Historical plan:
[`../archive/superseded/WALLBOARD_V2_PLAN.md`](../archive/superseded/WALLBOARD_V2_PLAN.md).

| Item | Status |
|------|--------|
| **O-3 / N-1** | `WALLBOARD_TOKEN` in `config_schema` (same as §1) | ✅ #514 |
| `?density=compact` layout mode | ✅ (this PR) |
| Campaign tile, EPSS movers, enriched backend tiles | ✅ wallboard v2 core + EPSS delta fix (this PR) |
| QR / one-time setup card on Security page (N-4) | 🔶 docs in OPERATIONS.md; QR card not built |
| `RATE_LIMIT_WALLBOARD_PER_MINUTE` in config schema | ✅ (this PR) — writable under section `app`, restart apply strategy, same pattern as O-3 |

---

## 8. Webhooks / DB explorer follow-ups

**Shipped:** PR12 (#413–#415), PR13 (#422). Historical plan:
[`../archive/superseded/PR12_PR13_IMPLEMENTATION_PLAN.md`](../archive/superseded/PR12_PR13_IMPLEMENTATION_PLAN.md).

| Item | Status |
|------|--------|
| Destination health UI from `webhook_delivery_log` (last success/error) | ✅ optional — Admin → Webhooks card grid + `GET /api/admin/webhooks/health` |
| Encrypting `config_json` at rest | 🅿️ |
| New webhook provider kinds | 🅿️ |

---

## 9. Resource benchmarking program

**Canonical spec:** [`specs/resource-benchmarking.md`](specs/resource-benchmarking.md)

| PR | Title | Status |
|----|-------|--------|
| **RB-1** | `resource_metrics` table + psutil collector job + retention (scheduler-lock mapping entry required) | ✅ #521 |
| **RB-2** | `GET /api/admin/resources` + admin Resources page (Chart.js, 1d/3d/7d/30d windows) | ✅ (this PR) |
| **RB-2** | `GET /api/admin/resources` + admin RESOURCES page (1d/3d/7d/30d windows, peak/avg/low) | ✅ (this PR) |

Out of scope by decision: synthetic load simulation, Prometheus/Grafana export,
per-endpoint latency histograms, alerting — see spec NOT-in-scope list.

---

## 9b. UI modernization + reliability program (added 2026-07-14)

**Canonical roadmap:** [`ui-modernization-plan.md`](ui-modernization-plan.md) (epics E0–E9;
§13 checklist is the ticket state — do **not** duplicate per-ticket rows here).  
**Verified-bug backlog:** [`reliability-and-bug-backlog.md`](reliability-and-bug-backlog.md) (REL-1…REL-7).  
**Decisions:** ADR-003 (tokens + Radix, no Tailwind) · ADR-004 (correlation precompute) ·
ADR-005 (UI library allow/deny). **Design SSOT:** [`../design/design-system.md`](../design/design-system.md).

| Item | Status |
|------|--------|
| ADR-003 / ADR-004 / ADR-005 maintainer acceptance | 💬 gate for Phase 0/1 |
| Plan Phase 0 (E0: tokens, Radix spike, motion toggle, docs sync) | 📋 |
| Plan Phase 1 (E1 correlation precompute, E2 standalone bugs incl. REL-7 PyJWT) | 📋 |
| Plan Phase 2 (E3 primitives, E4 semantics, E6 a11y core) | 📋 after Phase 0 |
| Plan Phase 3 (E5 ARCH re-skin, E7 polish incl. Recharts migration, E8/E9) | 📋 after Phase 2 |

---

## 10. Quality / process

| Item | Status |
|------|--------|
| Gemini Code Assist replacement (reviews cease **2026-07-17**) | 💬 decision needed — Sprint merge gate §4 |
| F3-tail | SPDX header reconciliation · optional trufflehog | 📋 optional |

---

## 10. Parked (explicit maintainer signal)

| Item | Source |
|------|--------|
| V1.5 Phase 4 STIX/Sigma export | Sprint |
| Full V2.0 `docker-compose.yml` | Sprint, operator backlog |
| Track I Phase 3 remainder (if any beyond #436–#438) | HANDOVER |

---

## 11. Recently shipped — do **not** re-queue

| Area | PRs / notes |
|------|-------------|
| Notifications v2 | #452 — `user_notifications`, bell, chime |
| Typography px dropdowns | #453 — per-role 9–20px |
| Operator 12-PR bundle | #428–#439 |
| Session auth middleware | #441 |
| Ops backup/wallboard docs | #442 |
| Feed perf I15/I16 | #443 |
| Multi-worker scheduler flag | #444 |
| Security + N+1 audit bundle | #449 |
| AUTH/VAL/IDEM/DB items | See §3 ✅ list |
| Track M core | #429–#431, #442 |
| Track N/O core | #428–#430, #442 |
| PR12/PR13 | #413–#415, #422 |
| AI-1/2 + retention + filters + tokens | #416–#420 |
| F2 LICENSE/CONTRIBUTING | #423 |
| Correlation v3 PR-1…PR-13 | #473…#513 |
| Forge redesign FR-1…FR-3 | #490, #492, #495 |
| Threat modeling TM-1…TM-5 | #491, #493–#497 |
| UX-C1 / UX-C2 (Issue 37) | #474, #475 |
| O-3 wallboard token in admin config | #514 |

---

## 12. Post–UI E2E UX observations (2026-07-15)

**Canonical spec:** [`specs/e2e-ux-observations-2026-07-15.md`](specs/e2e-ux-observations-2026-07-15.md) —
ordered E2E observations, accent decision (orange `#e85533`), IA locks, and PM-0…PM-4
remediation queue. Supporting artifacts: [`e2e-click-map-2026-07-15.md`](specs/e2e-click-map-2026-07-15.md),
[`e2e-audit-results-2026-07-15.md`](specs/e2e-audit-results-2026-07-15.md),
[`post-ui-audit-2026-07-15.md`](specs/post-ui-audit-2026-07-15.md) (phase detail).

| Phase | Scope | PRs | Status |
|-------|--------|-----|--------|
| **Accent** | Brand orange vs tan | PR #602 | 📋 open |
| **0** | P0 bugs (EPSS severity, sticky tooltips, drawer overlap, admin 500, `detected_at`) | PM-0a…PM-0e | 📋 |
| **1** | Charts + FEED filters + Forge Library toolbar | PM-1a…PM-1d | 📋 after Phase 0 |
| **2** | Accent sweep, DataGrid standard, ARCH layout | PM-2a…PM-2d | 📋 after Phase 1 |
| **3** | Architecture graph viewport/zoom/fit | PM-3a…PM-3d | 📋 after Phase 0 |
| **4** | IA: Admin Security posture, remove ARCH tab, Forge MITRE navigator | PM-4a–e ✅ #636–#640 | ✅ done |

**E2E automation:** `scripts/e2e_audit_exhaustive.py` (276 steps, 2026-07-15 run).

---

## 13. Durable outbound queue, API metering & stack-driven backfill

**Canonical spec:** [`specs/durable-outbound-queue-and-stack-backfill.md`](specs/durable-outbound-queue-and-stack-backfill.md)  
**Why:** Prod corpus ~78% 2026 publishes — fine for feed, blind for legacy stack (e.g. Java 8). Need Postgres-durable outbound jobs (no RabbitMQ), universal API call metering, CPE catalog autocomplete, opt-in Tier-A historical fetch.

| ID | Item | Status |
|----|------|--------|
| **Q1** | Procrastinate foundation (`PROCRASTINATE_ENABLED`, worker, admin job list) | 📋 |
| **Q2** | Universal outbound metering at `resilient_request` + admin quota UI (actor/job/cli) | 📋 after Q1 preferred |
| **Q3** | NVD CPE → `software_catalog` + autocomplete API | 📋 (can parallel Q2) |
| **Q4** | Stack UX (category/typeahead/version) + Agree Tier-A backfill (ETA/progress/checkpoints) | 📋 after Q1+Q3 |
| **Q5** | Optional: EPSS file identity skip (`score_date` + SHA-256) | 📋 optional |

**Locks:** Agree = Tier A only (NVD+KEV+EPSS bulk); no OTX/exploits/correlation inside Agree. Feature flags default off. UPSERT NVD-owned columns only.

**Open questions:** worker in-process vs systemd; event retention (default 30d); activate on sprint — see spec §Open questions.

---

## 14. Embeddings, pgvector & hybrid search

**Canonical design:** [`specs/embeddings-pgvector-hybrid-search-design.md`](specs/embeddings-pgvector-hybrid-search-design.md)  
**Why:** One retrieval engine for humans + agents; prod Postgres 16 has `pg_trgm` but no `vector` — need pgvector image at feature deploy. Keep bge-small; hybrid UI; Admin hashed search token.

| ID | Item | Status |
|----|------|--------|
| **E1** | pgvector pg16 images + `CREATE EXTENSION vector` + `embeddings` table / migrate BLOBs | 💬 design |
| **E2** | Embed pipeline → pgvector (hash, backfill, flags) | 💬 after E1 |
| **E3** | Related + hybrid search API (`mode`, query-shape, fallbacks) | 💬 after E2 |
| **E4** | UI one-box hybrid | 💬 after E3 |
| **E5** | Admin search service token (hash, show-once, scope, rate limit) | 💬 after E3 |
| **E6** | MITRE technique embeddings + typed hits | 💬 after E3–E5 |

**Locks:** No prod image swap until E1 deploy; no request-path model inference; techniques same schema, next slice.

---

## Where to add new items

1. Append a row to the relevant section **here**.
2. If sprint-sized, add a checkbox to `SPRINT_2026-07.md` (or next sprint).
3. Deep design context → extend the matching [`specs/`](specs/) doc, not a new duplicate file.
