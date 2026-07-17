# PHASE 9 — Cross-Browser · Cross-Platform · Compatibility · Reliability · Failure & Chaos Testing · Recovery

*Reviewed at commit `61c686f`. `resilient_client.py`, `task_registry.py`, `scheduler.py` shutdown,
`backup/manager.py` restore-on-startup, `tests/test_playwright_smoke.py`, `vite.config.js`.*

---

## Executive Summary

The **reliability primitives are strong**. External-feed access goes through `resilient_client.py`:
a single pooled `httpx.AsyncClient` with **per-source circuit breakers**, bounded retries,
`Retry-After` header honoring (capped at 120s), and default timeouts — textbook resilience against
flaky upstreams. **Graceful shutdown** is real: `task_registry.py` drains fire-and-forget tasks with
a bounded `SHUTDOWN_DRAIN_TIMEOUT_SECONDS` (default 10s), `stop_scheduler()` + `wait_for_running_jobs()`
bound in-flight jobs, and `main.py`'s lifespan sequences worker-stop → scheduler-stop → job-drain →
task-drain → flush → pool-close so an in-flight ingest can finish its commit. **Recovery** is
first-class: SQLite `ensure_db_or_restore` restores from backup on startup and **verifies the
restored DB with an integrity/health check** before serving; there are failure-path unit tests
(`test_resilient_client.py`, `test_llm_router.py` failover, `test_scheduler_next_run_restore.py`,
rate-limit pacing) exercising the degraded paths.

The gaps are **breadth of validation**, not absence of mechanism: (1) **no defined browser support
matrix** — there's no `browserslist`, and the E2E smoke is **Chromium-only** (CI runs `playwright
install chromium`), so Firefox/Safari/WebKit are untested for a product used across analyst
workstations; (2) **no system-level chaos/fault-injection testing** — failure paths are unit-tested
with mocks, but nothing kills the DB mid-transaction, simulates a network partition, fills the disk,
or pulls a provider mid-batch at the integration level; (3) **cross-platform is dev-on-Windows /
prod-on-Linux** (per CLAUDE.md) but only Linux is CI-validated; (4) **no stated reliability
objectives** (SLO/uptime/error-budget) and no automated recovery drills (ties to Phase 8 F8.3).

**Overall Score: 7 / 10.**

---

## Findings

### F9.1 — No browser support matrix; E2E is Chromium-only · Priority: MEDIUM · Architectural
- **Location:** `frontend/` has no `.browserslistrc`/`browserslist` in `package.json`;
  `vite.config.js` sets no `build.target`; CI `playwright-smoke` runs `playwright install chromium`
  only; React 19 + native ESM + modern CSS.
- **Description:** Browser support is implicit (Vite's modern baseline) and unvalidated beyond
  Chromium. Security analysts commonly run Firefox and Safari; features like the CSS the design
  system uses, `AbortController`, dynamic import, and Radix behaviors need cross-engine
  confirmation. No documented "supported browsers" statement exists for buyers.
- **Why it matters:** A rendering/interaction bug in Firefox/Safari ships undetected; enterprise
  procurement often asks for a supported-browser matrix.
- **Evidence:** no browserslist; chromium-only Playwright install in CI.
- **Recommended solution:** Define and document a supported-browser matrix (e.g. last 2 versions of
  Chrome/Edge/Firefox/Safari); add a `browserslist` and set Vite `build.target` accordingly; run
  the Playwright smoke across `chromium`, `firefox`, and `webkit` projects in CI. Add a couple of
  cross-engine visual/interaction checks for the drawer, tables, and charts.
- **Acceptance criteria:** Documented browser matrix; CI runs the smoke on 3 engines; build target
  matches the matrix.
- **Effort:** Medium. **Type:** Architectural.

### F9.2 — No system-level chaos / fault-injection testing · Priority: MEDIUM · Architectural
- **Location:** failure paths are unit-tested with mocks (`test_llm_router.py`,
  `test_resilient_client.py`, `test_rate_limit_pacing.py`, `test_correlation_lifecycle.py`) but no
  integration-level fault injection (DB kill mid-write, connection drop, disk-full, provider
  timeout mid-batch, pool exhaustion under load).
- **Description:** The circuit-breaker/retry/drain mechanisms are individually tested, but their
  behavior *composed under real failure* isn't. E.g., what happens to a nightly correlation batch if
  Postgres restarts mid-run (given the bespoke `_recover_db_transaction`, Phase 3 F3.8)? What does a
  request see when the pool is exhausted *and* a circuit is open?
- **Why it matters:** Reliability emerges from how mechanisms interact under fault; unit-mocked
  failures don't catch composition bugs (partial writes, deadlocks, thundering-herd on recovery).
- **Evidence:** no chaos/toxiproxy/fault-injection harness; failure tests are unit-scoped.
- **Recommended solution:** Add a small chaos suite against a Postgres Testcontainer: kill/restart
  the DB mid-transaction and assert no partial rows (F3.8/F4.5); block a provider (toxiproxy or a
  stub returning timeouts) and assert circuit-open + graceful degradation; exhaust the pool and
  assert 503 backpressure + recovery. Run nightly, not on every PR.
- **Acceptance criteria:** DB-restart-mid-batch leaves consistent state; provider outage degrades
  gracefully; pool exhaustion recovers — all asserted in CI.
- **Effort:** Medium–Large. **Type:** Architectural.

### F9.3 — Cross-platform: dev-on-Windows / prod-on-Linux, only Linux CI-validated · Priority: LOW · Quick Win
- **Location:** CLAUDE.md documents a Windows dev environment (paths, unavailable `sqlite3`/`psql`);
  CI runs `ubuntu-latest` only; `deploy/` targets Linux/systemd.
- **Description:** The dev/prod platform split means Windows-specific issues (path separators, file
  locking, line endings, `.env` writing in `settings.py`) are only caught by the individual
  developer, not CI. The `set_key`-to-`.env` behavior (Phase 7 F7.1) is exactly the kind of thing
  that behaves differently on Windows/read-only FS.
- **Why it matters:** Contributor-environment drift and OS-specific bugs; low risk since prod is
  Linux-only, but real for the dev workflow.
- **Recommended solution:** Either add a Windows CI job for the backend unit suite, or explicitly
  document "development supported on Linux/macOS/WSL2; native Windows best-effort." Normalize path
  handling via `pathlib` (already largely used) and add a `.gitattributes` for line endings.
- **Acceptance criteria:** Documented dev-platform support statement; line-ending normalization; (optional) Windows CI smoke.
- **Effort:** Quick Win. **Type:** Quick Win.

### F9.4 — No stated reliability objectives (SLO/uptime/error budget) or recovery drills · Priority: MEDIUM · Architectural
- **Location:** no SLO/uptime target in `docs/`; recovery mechanisms exist (`ensure_db_or_restore`,
  circuit breakers, drain) but no scheduled recovery drill (ties to Phase 8 F8.3); no error-budget
  policy.
- **Description:** Reliability is engineered but not *targeted or measured* — there's no stated
  availability goal, no error budget, and no periodic proof that recovery (restore, failover)
  actually works end-to-end on real data.
- **Why it matters:** "Reliable" is unfalsifiable without a target and measurement; enterprise SLAs
  require stated objectives and evidence of recovery testing.
- **Recommended solution:** Define an SLO (e.g. 99.5% API availability, p95 latency budget from
  F6.5) and an error-budget policy; add the scheduled restore drill (F8.3); track availability via
  the `/metrics` endpoint (F8.1). Document in OPERATIONS.md.
- **Acceptance criteria:** Documented SLO + error budget; a passing scheduled recovery drill;
  availability measured.
- **Effort:** Medium. **Type:** Architectural.

### F9.5 — Compatibility: dual-dialect DB is a standing compatibility risk (carries F2.1/F1.4) · Priority: MEDIUM · Architectural
- **Location:** `db/` dual `_SQLITE`/`_PG` (401 constants), `pg_adapt.py`; default tests on SQLite,
  prod on Postgres.
- **Description:** From a compatibility lens, every query must remain compatible with two engines
  whose semantics differ (types, JSONB, regex, `ON CONFLICT`, transactions). The default test path
  validates the *non-production* engine, so Postgres-only incompatibilities can pass CI's primary
  signal — a latent compatibility/reliability hazard.
- **Why it matters:** Compatibility bugs surface as production-only failures (the worst kind),
  amplified by the red CI baseline (F4.1) that hides them.
- **Recommended solution:** Make Postgres the default CI dialect (Phase 2/6) and add the `_PG`/
  `_SQLITE` parity guard (Phase 1 F1.4); once SQLite is truly optional, consider dropping it to
  remove the compatibility surface entirely.
- **Acceptance criteria:** Primary CI validates Postgres; parity guard enforces dual-dialect
  coverage or explicit PG-only markers.
- **Effort:** Large. **Type:** Architectural.

### F9.6 — Reliability of external-dependency degradation is good — surface it to users · Priority: LOW · Quick Win
- **Location:** `resilient_client.py` circuit breakers, `monitoring/api_key_health.py`, feed-health
  in `routers/health.py` + Sidebar `feedHealth` state.
- **Description:** When an upstream (NVD, KEV, OTX, an LLM provider) is down, the circuit opens and
  the system degrades gracefully — but the *user-facing* signal that "this data is stale because
  source X is down" should be explicit and consistent (some feed-health surfacing exists). This is
  the reliability↔UX seam.
- **Why it matters:** Silent degradation erodes trust; analysts must know when intelligence is stale
  due to an upstream outage vs a real "nothing new" state (CLAUDE.md health-vs-freshness rule).
- **Recommended solution:** Ensure every data surface that can be stale from an open circuit shows a
  freshness/health indicator with the reason; reuse the existing feed-health + circuit state. Add a
  gate test that stale data renders a freshness callout.
- **Acceptance criteria:** An open circuit produces a visible, explained staleness indicator on
  affected surfaces.
- **Effort:** Quick Win. **Type:** Quick Win.

---

## Overall Score: **7 / 10**

| Sub-audit | Score |
|---|---|
| Cross-Browser | 5.5 / 10 |
| Cross-Platform | 7 / 10 |
| Compatibility | 6.5 / 10 |
| Reliability | 8 / 10 |
| Failure & Chaos Testing | 6 / 10 |
| Recovery | 8 / 10 |

## Strengths
- Per-source circuit breakers + bounded retries + `Retry-After` honoring via a pooled httpx client.
- Real graceful shutdown: bounded task/job drain and ordered lifespan teardown so in-flight commits
  finish.
- Recovery-first: SQLite restore-on-startup with post-restore integrity/health verification;
  failure-path unit tests (failover, circuit, restore, pacing).
- Feed-health/circuit state already surfaced to the UI.

## Weaknesses
- Chromium-only E2E + no browser matrix (F9.1); no system-level chaos testing (F9.2).
- Dev/prod platform split unvalidated in CI (F9.3); no SLO/recovery-drill (F9.4); dual-dialect
  compatibility risk (F9.5).

## Immediate Action Items
1. Define a supported-browser matrix; run the Playwright smoke on 3 engines (F9.1).
2. Add a `.gitattributes` + dev-platform support statement (F9.3).
3. Ensure open-circuit staleness is always surfaced with a reason (F9.6).

## Long-Term Recommendations
1. Build a nightly chaos/fault-injection suite on a Postgres Testcontainer (F9.2).
2. Define SLO/error-budget + scheduled recovery drills (F9.4, with F8.3).
3. Resolve the dual-dialect compatibility surface (F9.5, with F2.1/F1.4).

## Production-Readiness Assessment (Phase 9 areas)
**Reliable core, unproven breadth — 7/10.** The failure-handling and recovery *engineering* is
genuinely good and above the self-hosted-tool bar. What's missing is *validated breadth*: cross-
browser coverage (F9.1) and composed-failure/chaos testing (F9.2) mean reliability is asserted more
than proven across the matrix of real conditions. For single-node self-host on Chromium/Linux this
is production-ready; for enterprise (multi-browser support statements, SLAs, compliance recovery
evidence) close F9.1, F9.2, and F9.4 first.
