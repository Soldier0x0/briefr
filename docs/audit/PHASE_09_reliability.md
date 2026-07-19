# PHASE 9 - Cross-Browser / Cross-Platform / Compatibility / Reliability / Failure & Chaos Testing / Recovery

*Refresh reviewed for pinned SHA `ff23c18a4925b3b7082a2b1d1600884324d90d02`.
Workspace HEAD during refresh was `267f174ba1f50e0335ad82b28b984f5e46ac5e61` (later docs-only
work). Evidence checked: `.github/workflows/backend-tests.yml`, `.github/workflows/gitleaks.yml`,
`CLAUDE.md`, newest `docs/HANDOVER.md` entries, `docs/PRODUCT_STATUS.md`, `frontend/package.json`,
`frontend/vite.config.js`, `backend/resilient_client.py`, `backend/main.py`,
`backend/tests/test_playwright_smoke.py`, and targeted searches for browser matrix, coverage,
chaos/fault-injection, SLO, and DB compatibility markers.*

---

## Executive Summary

The reliability core remains strong and has become easier to observe. `resilient_client.py` still
centralizes outbound HTTP behind one pooled `httpx.AsyncClient`, bounded retries, per-source circuit
breakers, `Retry-After` honoring, queue pacing, and health state. Startup/shutdown sequencing in
`main.py` still stops workers/scheduler, waits for running jobs, drains background tasks, flushes
usage, and closes pools/clients. `PRODUCT_STATUS.md` now documents additional reliability work:
PostgreSQL required in production, Postgres backup/export smokes, API queue status, API metering,
operator/admin health views, feed-health and API-key health surfacing, and durable jobs via
Procrastinate behind a feature flag.

The major gaps remain validation breadth and objective reliability targets. The UI smoke is still
Chromium-only (`playwright install chromium`, fixture launches `playwright.chromium`), and there is
no `browserslist` or Vite `build.target`. Searches found no active chaos/fault-injection harness
for DB restart, provider network partition, disk-full, or pool exhaustion. Linux is the only CI OS,
while `CLAUDE.md` preserves Windows-specific dev caveats. Docs still lack SLO/error-budget language
and scheduled recovery drills. The old "dual-dialect DB" finding needs an evidence update:
production is now Postgres-required and `db/dialect.py` is intentionally deleted, but SQLite remains
the zero-config test/dev fallback and `pg_adapt.py` still represents a compatibility surface for
legacy router SQL.

**Overall Score: 7.1 / 10.**

---

## Status Table

| ID | Status | Priority | Type | Refresh disposition |
|---|---|---:|---|---|
| F9.1 | OPEN | MEDIUM | Architectural | No browser matrix; Chromium-only CI/playwright fixture remains. |
| F9.2 | OPEN | MEDIUM | Architectural | No system-level chaos/fault-injection harness found. |
| F9.3 | UPDATED | LOW | Quick Win | Linux-only CI remains; Windows dev caveats still documented. |
| F9.4 | OPEN | MEDIUM | Architectural | No SLO/error budget or scheduled restore/recovery drill found. |
| F9.5 | UPDATED | MEDIUM | Architectural | Production Postgres reduces scope; SQLite fallback/`pg_adapt.py` still create compatibility risk. |
| F9.6 | UPDATED | LOW | Quick Win | More health surfacing exists, but universal stale-data callouts are not proven. |

---

## Findings

### F9.1 — No browser support matrix; E2E remains Chromium-only · Status: OPEN · Priority: MEDIUM · Architectural
- **Location:** `frontend/package.json`, `frontend/vite.config.js`,
  `.github/workflows/backend-tests.yml`, `backend/tests/conftest.py`,
  `backend/tests/test_playwright_smoke.py`.
- **Current evidence:** No `.browserslistrc` or `browserslist` field was found; `vite.config.js`
  has no `build.target`; CI installs only Chromium with `playwright install chromium --with-deps`;
  the test fixture launches `playwright.chromium`.
- **Risk:** Firefox/WebKit/Safari rendering, focus, Radix, table, chart, and CSS behavior can drift
  without a failing gate.
- **Recommended solution:** Define a supported browser matrix, set build/browser targets to match,
  and run the smoke across Chromium, Firefox, and WebKit projects. Keep the smoke small and add
  cross-engine checks for the drawer, tables, and chart shells.
- **Acceptance criteria:** Supported browsers are documented; CI runs at least one required smoke
  path on Chromium, Firefox, and WebKit.

### F9.2 — No system-level chaos or fault-injection testing · Status: OPEN · Priority: MEDIUM · Architectural
- **Location:** backend tests, CI workflow, reliability docs.
- **Current evidence:** Targeted searches found no `toxiproxy`, chaos harness, DB-kill test,
  disk-full test, provider partition test, or pool-exhaustion integration test. Unit tests cover
  circuit breakers, pacing, scheduler restore, and failover, but composed infrastructure failures
  are not exercised.
- **Risk:** The most important reliability bugs--partial writes, stuck pools, thundering herd after
  recovery, stale data without callouts--appear under composed failures, not pure mocks.
- **Recommended solution:** Add a nightly or optional full-gate chaos suite against Postgres:
  restart DB mid-write, block one provider, simulate repeated 503/429 with circuit open, and
  exhaust the connection pool. Assert graceful degradation and recovery.
- **Acceptance criteria:** A representative DB restart/provider outage/pool exhaustion scenario is
  automated and fails on partial writes or non-recovery.

### F9.3 — Cross-platform dev support is documented, but only Linux is CI-validated · Status: UPDATED · Priority: LOW · Quick Win
- **Location:** `CLAUDE.md`, `.github/workflows/backend-tests.yml`, deploy docs/scripts.
- **Current evidence:** `CLAUDE.md` still lists Windows-specific hazards (path reset, missing tools,
  blocked foreground sleep), while both workflows run on `ubuntu-latest`. Production/deploy paths
  remain Linux/Postgres-focused.
- **Risk:** Native Windows contributor issues can reach developers before CI catches them; production
  risk is lower because the supported runtime is Linux.
- **Recommended solution:** Either document native Windows as best-effort with WSL2/Linux as the
  supported dev target, or add a small Windows backend smoke if native Windows support is intended.
  Add line-ending normalization if not already covered elsewhere.
- **Acceptance criteria:** Dev-platform support is explicit; CI or docs match that support statement.

### F9.4 — No stated SLO/error budget or scheduled recovery drill · Status: OPEN · Priority: MEDIUM · Architectural
- **Location:** `docs/`, Phase 8 recovery findings, operations docs.
- **Current evidence:** Searches found audit recommendations for SLOs/RPO/RTO/recovery drills, but
  no current operational SLO, error-budget policy, or scheduled restore/recovery drill. `PRODUCT_STATUS.md`
  documents backup/export smokes, not a recurring restore drill against real-ish data.
- **Risk:** Reliability remains qualitative. Enterprise operators cannot evaluate whether uptime,
  recovery time, and data-loss expectations are met.
- **Recommended solution:** Define API availability/latency and RPO/RTO objectives, document an
  error-budget policy, and schedule an automated restore drill to a scratch DB/environment.
- **Acceptance criteria:** Operations docs state SLO/RPO/RTO, and a recurring recovery drill reports
  pass/fail.

### F9.5 — Compatibility risk is narrower but still present around SQLite fallback and `pg_adapt.py` · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `CLAUDE.md`, `docs/PRODUCT_STATUS.md`, `backend/db/pg_adapt.py`, DB tests.
- **Current evidence:** `CLAUDE.md` and `PRODUCT_STATUS.md` now state production is Postgres-only /
  Postgres-required, and `db/dialect.py` was deleted. That closes the old broad "runtime dialect
  translator" framing. However SQLite still survives as the zero-config test/dev fallback, tests
  default to SQLite unless Postgres is selected, and `pg_adapt.py` remains a compatibility layer for
  legacy router SQL at the Postgres connection boundary.
- **Risk:** A query or migration can still pass default SQLite tests while failing in production
  Postgres, especially while the pinned CI baseline is red.
- **Recommended solution:** Keep Postgres full-suite CI green and visible; add guard tests for any
  remaining SQLite/PG query pairs or explicit PG-only markers; prefer writing new SQL Postgres-native
  as `CLAUDE.md` requires.
- **Acceptance criteria:** Default local tests are clearly labeled SQLite fallback, Postgres CI is
  green, and compatibility-only SQL paths have guard coverage.

### F9.6 — External-dependency degradation is well-engineered; stale-data UX proof is incomplete · Status: UPDATED · Priority: LOW · Quick Win
- **Location:** `backend/resilient_client.py`, `backend/wallboard/service.py`,
  `backend/routers/admin.py`, `monitoring/api_key_health.py`, frontend feed/admin health surfaces.
- **Current evidence:** Circuit state is exposed through health/admin/wallboard paths, API-key
  probes avoid poisoning shared feed circuits, and `PRODUCT_STATUS.md` documents queue/health
  indicators. That is stronger than the prior state. The refresh did not find a universal gate that
  every stale data surface renders a reasoned freshness callout when a source circuit is open.
- **Risk:** Analysts can still mistake stale/degraded intelligence for genuinely empty or current
  data on surfaces that lack the callout.
- **Recommended solution:** Add a reusable freshness/circuit callout contract and a frontend gate
  test that open-circuit/stale fixtures render an explanation on affected surfaces.
- **Acceptance criteria:** An open upstream circuit produces visible, reasoned stale-data messaging
  everywhere that source contributes data.

---

## Resolved since last audit

None. F9.5 was narrowed materially by Postgres-required production status and deletion of
`db/dialect.py`, but the compatibility class is not fully closed because SQLite fallback and
`pg_adapt.py` remain active.

---

## Overall Score: **7.1 / 10**

| Sub-audit | Score |
|---|---:|
| Cross-Browser | 5.0 / 10 |
| Cross-Platform | 7.0 / 10 |
| Compatibility | 7.0 / 10 |
| Reliability | 8.4 / 10 |
| Failure & Chaos Testing | 5.5 / 10 |
| Recovery | 8.0 / 10 |

## Strengths
- Centralized resilient HTTP client with pooled requests, queue pacing, circuit breakers, retries,
  and `Retry-After` handling.
- Ordered shutdown path drains workers, scheduler jobs, background tasks, usage flushes, and pools.
- Production Postgres requirement plus Postgres backup/export smokes reduce recovery risk.
- Health, queue, API-key, and circuit state are increasingly operator-visible.

## Weaknesses
- Chromium-only browser validation and no browser support matrix.
- No system-level chaos/fault-injection lane.
- No stated SLO/error-budget or scheduled recovery drill.
- Linux-only CI despite documented Windows dev caveats.
- SQLite fallback/`pg_adapt.py` still require compatibility discipline.

## Immediate Action Items
1. Define browser support and run Playwright smoke on Chromium, Firefox, and WebKit.
2. Add a small chaos/fault-injection suite for Postgres restart, provider outage, and pool exhaustion.
3. Document SLO/RPO/RTO and schedule a restore/recovery drill.
4. Make stale-data callouts gate-tested for open-circuit sources.

## Production-Readiness Assessment (Phase 9 areas)

**Reliable core, under-validated breadth - 7.1/10.** BRIEFR has credible resilience mechanisms for
a single-node self-hosted deployment, and recent operator-health work improves observability. The
remaining gap is proof under real operating variety: multiple browser engines, composed
infrastructure faults, explicit reliability targets, and repeatable recovery evidence.
