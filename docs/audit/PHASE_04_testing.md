# PHASE 4 - Functional / E2E Workflow / Feature Completeness / Integration / Regression / Data Integrity

*Refresh reviewed for pinned SHA `ff23c18a4925b3b7082a2b1d1600884324d90d02`.
Workspace HEAD during refresh was `267f174ba1f50e0335ad82b28b984f5e46ac5e61` (later docs-only
work). Evidence checked: `.github/workflows/backend-tests.yml`, `.github/workflows/gitleaks.yml`,
`CLAUDE.md`, newest `docs/HANDOVER.md` entries, `docs/PRODUCT_STATUS.md`,
`scripts/verify-local.sh`, `frontend/package.json`, `backend/requirements*.txt`, and current test
file inventory.*

---

## Executive Summary

Testing investment has grown since the prior audit: the repo now has **210 backend `test_*.py`
files** and **56 frontend `*.test.js` files**. The backend suite covers many reliability,
security, DB, admin, detection, retrieval, correlation, backup, and UI-build support paths. The
frontend test suite continues to encode useful product gates (`nativeSelectGate`,
`dataGridStandardGate`, `iconOnlyAriaGate`, URL-state, motion, Recharts, DateTimePicker, and other
design-system rules). `PRODUCT_STATUS.md` remains a strong shipped/planned ledger, and Postgres CI
still declares both a backup round-trip smoke and the full backend suite.

The release signal is still not trustworthy enough for enterprise readiness. The pinned SHA has
verified GitHub failures for `test`, `test-postgres`, `playwright-smoke`, `dependency-audit`, and
`gitleaks`; `CLAUDE.md` only pre-labels `dependency-audit` and `gitleaks` as known-red, so the
backend and Playwright failures cannot be waived from repo policy. GitHub job logs were unavailable
(`gh run view --log` returned `log not found`), so this refresh does **not** claim a root cause.
The CI workflow still omits the 56 frontend unit/gate tests, coverage remains unmeasured, and
integration/E2E coverage remains narrow relative to the product surface.

**Overall Score: 6.5 / 10.**

---

## Status Table

| ID | Status | Priority | Type | Refresh disposition |
|---|---|---:|---|---|
| F4.1 | UPDATED | CRITICAL | Architectural | Pinned-SHA CI failures verified; root cause unknown because logs are unavailable. |
| F4.2 | UPDATED | HIGH | Quick Win | Frontend gate suite grew to 56 files; CI still does not run `npm run test:unit`. |
| F4.3 | OPEN | HIGH | Quick Win | No `pytest-cov`, coverage config, Hypothesis, or mutation tooling found. |
| F4.4 | UPDATED | HIGH | Architectural | More tests exist, but full workflow/pipeline E2E remains thin. |
| F4.5 | UPDATED | HIGH | Architectural | Production is Postgres-first now, but failure-injection integrity tests are still missing. |
| F4.6 | UPDATED | MEDIUM | Quick Win | Old "no `.python-version`" claim is stale; current contract is inconsistent (`3.13` file vs CI/cloud 3.12). |
| F4.7 | UPDATED | MEDIUM | Quick Win | Isolation fixtures remain mature; no structural guard against module-scope env mutation found. |
| F4.8 | UPDATED | LOW | Quick Win | `PRODUCT_STATUS.md` is strong, but shipped feature -> passing test traceability is still manual. |

---

## Findings

### F4.1 — CI is red at the pinned SHA; the primary regression signal is untrustworthy · Status: UPDATED · Priority: CRITICAL · Architectural
- **Location:** `.github/workflows/backend-tests.yml` jobs `test`, `test-postgres`,
  `dependency-audit`, `playwright-smoke`; `.github/workflows/gitleaks.yml` job `gitleaks`;
  `CLAUDE.md` PR workflow notes.
- **Current evidence:** `gh run list --commit ff23c18a4925b3b7082a2b1d1600884324d90d02` returned
  failed workflow runs for **Backend tests** and **Secret scan**. `gh run view` showed failed jobs:
  `test`, `test-postgres`, `playwright-smoke`, `dependency-audit`, and `gitleaks`. `CLAUDE.md`
  explicitly says only `dependency-audit` and `gitleaks` are known-red, not pytest or Playwright.
- **Do not overclaim:** The logs were not retrievable (`log not found`), and the jobs show no step
  detail in `gh run view`; classify this as a verified red baseline/run, not a diagnosed pytest
  failure.
- **Risk:** Required correctness gates cannot distinguish a real regression from standing CI
  failure.
- **Recommended solution:** Root-cause the workflow/job-start failure first; then require green
  `test` and `test-postgres` before merge. Keep known-red audit/secret jobs either fixed or
  explicitly non-blocking with tracked issues so red means action needed.
- **Acceptance criteria:** A no-op PR at current `main` produces green `test` and `test-postgres`;
  Playwright smoke either passes or is quarantined with an issue and a narrow reason.

### F4.2 — Frontend gate-tests are still not executed in CI · Status: UPDATED · Priority: HIGH · Quick Win
- **Location:** `frontend/package.json` has `"test:unit": "node --test 'src/**/*.test.js'"`;
  `.github/workflows/backend-tests.yml` does not invoke it.
- **Current evidence:** `frontend/src` contains **56** `*.test.js` files, up from 47 in the prior
  audit. The workflow installs/builds the frontend only inside `playwright-smoke`; no job runs
  `npm run test:unit`.
- **Risk:** Design-system, accessibility, URL-state, and frontend security gates are real tests but
  not merge gates.
- **Recommended solution:** Add a required `frontend-tests` job:
  `npm ci --ignore-scripts && npm run test:unit`, alongside the existing build step.
- **Acceptance criteria:** A failing frontend gate test fails CI on PRs.

### F4.3 — Coverage is unmeasured · Status: OPEN · Priority: HIGH · Quick Win
- **Location:** `backend/requirements-dev.txt`, workflow YAML, repo config.
- **Current evidence:** `backend/requirements-dev.txt` still contains only `pytest` and
  `playwright` over app requirements; searches found no `pytest-cov`, coverage config,
  `hypothesis`, or `mutmut` in active test/build config.
- **Risk:** The test suite is large, but the team cannot tell which shipped behavior is untested or
  whether coverage regresses.
- **Recommended solution:** Add `pytest-cov` and publish terminal/XML coverage from CI; start the
  gate at the measured baseline and ratchet. Add property tests where deterministic scoring,
  normalization, and query-building logic makes that cheap.
- **Acceptance criteria:** CI reports coverage and fails when coverage drops below the configured
  floor.

### F4.4 — E2E and integration depth is still thin for the shipped surface · Status: UPDATED · Priority: HIGH · Architectural
- **Location:** `backend/tests/test_playwright_smoke.py`, `backend/tests/test_backup_roundtrip_postgres.py`,
  `backend/tests/test_intel_snapshot_export.py`, API/router tests.
- **Current evidence:** The Playwright smoke now exercises several analyst interactions in Chromium
  (brief cards, filter anchoring, drawer focus restore, IOC input, incidents/news). Postgres CI
  declares a backup round-trip smoke before the full Postgres suite. This is better than the prior
  "one smoke + one round-trip" framing, but it still does not cover complete ingest -> enrich ->
  correlate -> risk -> API -> UI workflows or webhook delivery end-to-end.
- **Risk:** Cross-module wiring can still break while unit and router tests pass.
- **Recommended solution:** Add a small Postgres-backed integration lane for the top product
  workflows: seeded ingest/enrichment/correlation/risk materialization, top API contracts, and one
  full analyst UI journey.
- **Acceptance criteria:** A broken ingest-to-risk pipeline, drawer contract, or webhook delivery
  path fails CI.

### F4.5 — Data integrity failure-injection is still missing for multi-write flows · Status: UPDATED · Priority: HIGH · Architectural
- **Location:** DB/correlation/ingest flows, Postgres CI, Phase 9 chaos coverage.
- **Current evidence:** `PRODUCT_STATUS.md` says production is PostgreSQL-required and Postgres CI
  runs backup/export smokes, which reduces the older "SQLite primary" risk. However the audit found
  no system-level mid-flow failure injection (DB restart, connection drop, partial write assertion)
  for ingest/enrich/correlate/risk materialization.
- **Risk:** Partial writes and transaction-recovery bugs are most likely to appear under composed
  production failures, not unit-level mocks.
- **Recommended solution:** Add Postgres failure-injection tests that abort mid-flow and assert no
  partial materialized state, aligned with F9.2.
- **Acceptance criteria:** A forced DB disconnect/restart during a representative multi-write flow
  leaves a consistent database and fails if partial rows remain.

### F4.6 — Python version contract is inconsistent · Status: UPDATED · Priority: MEDIUM · Quick Win
- **Location:** `backend/.python-version`, `.github/workflows/backend-tests.yml`,
  `backend/requirements.txt`, `CLAUDE.md`.
- **Current evidence:** CI uses Python `3.12`; `CLAUDE.md` says CI/cloud use Python 3.12 and the
  repo is supported there; `backend/.python-version` pins `3.13`; `requirements.txt` pins
  `numpy==2.5.1`, which excludes Python 3.11.
- **Risk:** Contributors and agents can select different Python versions than CI, causing install
  or behavior drift before tests even run.
- **Recommended solution:** Pick and document one supported development/CI range. If 3.12 is the
  contract, change `.python-version` to 3.12 and add an explicit `requires-python >=3.12` note in
  Python packaging/onboarding docs.
- **Acceptance criteria:** A fresh clone selects the same supported Python as CI, and unsupported
  Python versions fail with a clear message.

### F4.7 — Test isolation has strong fixtures but no structural guard for env mutation · Status: UPDATED · Priority: MEDIUM · Quick Win
- **Location:** `backend/tests/conftest.py` and backend tests.
- **Current evidence:** The Playwright/session fixtures and Postgres isolation remain substantial,
  and `conftest.py` still carries guardrails around smoke setup and DB health. The prior class of
  bug--module-scope mutation of `DATABASE_URL`--is not protected by an AST/lint gate found during
  refresh.
- **Risk:** A new test can reintroduce order-dependent environment pollution and create flaky
  SQLite/Postgres behavior.
- **Recommended solution:** Add a guard test that rejects module-scope `os.environ["DATABASE_URL"]`
  mutation in `backend/tests`, and prefer `monkeypatch` in tests that need env changes.
- **Acceptance criteria:** A module-scope `DATABASE_URL` assignment in a test file fails the guard.

### F4.8 — Feature completeness is tracked well, but not machine-verified · Status: UPDATED · Priority: LOW · Quick Win
- **Location:** `docs/PRODUCT_STATUS.md`, sprint/roadmap docs, tests.
- **Current evidence:** `PRODUCT_STATUS.md` is current enough to list v1.5.0, shipped Postgres,
  auth, Track I, UI design-system, LLM, Admin, embeddings, wallboard, and planned/open rows. That
  is useful operational truth, but there is still no generated feature -> test traceability matrix.
- **Risk:** A feature can remain documented as shipped after its implementation or test coverage
  drifts.
- **Recommended solution:** Maintain a lightweight shipped-feature matrix mapping each
  `PRODUCT_STATUS.md` row to one or more backend/frontend test IDs.
- **Acceptance criteria:** Every shipped row has at least one passing test reference or an explicit
  "manual-only" exception.

---

## Resolved since last audit

None. Several findings were narrowed or updated with better evidence, but no F4 finding is fully
closed.

---

## Overall Score: **6.5 / 10**

| Sub-audit | Score |
|---|---:|
| Functional Testing | 7.8 / 10 |
| End-to-End Workflow | 5.5 / 10 |
| Feature Completeness | 8.0 / 10 |
| Integration Testing | 5.5 / 10 |
| Regression Testing | 5.5 / 10 |
| Data Integrity | 6.5 / 10 |

## Strengths
- Large and growing backend suite: 210 `test_*.py` files.
- Strong frontend gate-test culture: 56 `*.test.js` files encoding real UX/a11y/security rules.
- Postgres CI includes a backup round-trip smoke and a full-suite lane by workflow definition.
- `PRODUCT_STATUS.md` remains a useful shipped/planned ledger.

## Weaknesses
- Pinned SHA CI is red across pytest, Playwright, dependency audit, and gitleaks; only the last two
  are documented known-red.
- Frontend unit/gate tests are not run in CI.
- Coverage remains unmeasured.
- Workflow-level integration and failure-injection depth trails the shipped product surface.
- Python version selection is inconsistent (`.python-version` 3.13 vs CI/cloud 3.12).

## Immediate Action Items
1. Root-cause the pinned/main CI workflow failures and make `test` + `test-postgres` green.
2. Add a required frontend unit/gate-test CI job.
3. Add coverage reporting and a starting floor.
4. Align `.python-version` and docs with the supported Python version.

## Production-Readiness Assessment (Phase 4 areas)

**Not release-signoff ready until CI is trustworthy - 6.5/10.** The amount of test code and the
quality of many local gates are real strengths, but the pinned SHA's red CI baseline prevents a
clean regression signal. After F4.1 and F4.2 are fixed, the remaining risk is less about test
culture and more about measured coverage plus a small number of high-value integration workflows.
