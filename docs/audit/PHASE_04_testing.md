# PHASE 4 — Functional · E2E Workflow · Feature Completeness · Integration · Regression · Data Integrity

*Reviewed at commit `61c686f`. 187 backend test files (~28.6k LOC), 47 frontend `*.test.js`,
`backend/tests/conftest.py`, CI `.github/workflows/backend-tests.yml`.*

---

## Executive Summary

Test **investment is high and the culture is real**: 187 backend test files spread sensibly
across modules (db 17, security 8, correlation 8, admin 7, detection 6, llm/ai 10, epss 5,
auth 5, backup 4…), plus 47 frontend tests — many of them **"gate" tests** that codify
design-system/UX/accessibility rules (`iconOnlyAriaGate`, `nativeSelectGate`,
`dataGridStandardGate`, `activeStateGate`, `motion`, `safeExternalUrl`…). `conftest.py` shows
mature hygiene: per-test Postgres TRUNCATE isolation and a documented past isolation bug
(`test_db_explorer.py` polluting `os.environ`) that was fixed with a settings-safe resolver.
Feature completeness is high — `PRODUCT_STATUS.md` frames most surfaces as *shipped*, with a
small explicit "planned/open" set and only 7 skipped tests and no meaningful stubs.

But the **testing safety net has three holes that matter at enterprise scale**: (1) **CI is
baseline-red** — every push in this PR (docs-only) produced identical `test` / `test-postgres`
/ `playwright-smoke` / `dependency-audit` / `gitleaks` failures, so the primary regression
signal is currently untrustworthy (a red baseline means real regressions hide in the noise);
(2) the excellent frontend gate-tests are **not run in CI** (Phase 1 F1.11), so the UX/a11y
contracts they encode protect nothing automatically; (3) **coverage is unmeasured** — no
`pytest-cov`/coverage/property/mutation tooling exists, so test *effectiveness* is unknown, and
**E2E/integration depth is thin** (essentially one Playwright smoke + one backup round-trip).
Separately, the suite is **not reproducible off Python 3.12** — `requirements.txt` pins
`numpy==2.5.1` (requires-python ≥3.12), so a contributor on 3.11 cannot install deps (verified:
this sandbox is 3.11.15 and the install failed on numpy).

**Overall Score: 6.5 / 10.**

---

## Findings

### F4.1 — CI is baseline-red; the primary regression signal is untrustworthy · Priority: CRITICAL · Architectural
- **Location:** `.github/workflows/backend-tests.yml` jobs `test`, `test-postgres`,
  `playwright-smoke` (+ known-red `dependency-audit`, `gitleaks`). Observed on PR #661 commits
  `db65e31`, `ea3eab6`, `f7c1fad` — all docs-only, all five jobs `failure`.
- **Description:** A change that touches only `docs/audit/*.md` cannot break pytest, Playwright,
  pip-audit, or gitleaks logic, yet all jobs fail identically on every push. Therefore the base
  pipeline (branch/`main`) is red independent of the diff. CLAUDE.md pre-declares
  `dependency-audit`+`gitleaks` as "known-red," but `test`/`test-postgres`/`playwright-smoke`
  being red is a far stronger problem: green is no longer the expected state, so a genuine
  regression cannot be distinguished from the standing failure.
- **Why it matters:** A red baseline is the single most damaging condition for a test suite —
  it trains everyone to ignore CI, and it means "tests pass" is not a merge gate. For a platform
  meant for thousands of orgs, this must be green-by-default before any correctness claim holds.
- **Evidence:** three consecutive docs-only pushes → identical 5-job failure set; job logs
  returned HTTP 404 via the MCP proxy (could not fetch the stack traces). Independent local
  reproduction was blocked by F4.6 (Python 3.11 vs required 3.12).
- **Risk:** Real regressions merge undetected; CI provides false confidence / is ignored.
- **Recommended solution:** (1) Fetch the failing `test` job log on a GitHub-hosted runner and
  root-cause it (do NOT assume flaky). (2) Get `test`+`test-postgres` green and **keep them
  required**; if a subset is genuinely environmental, quarantine those specific tests with
  `@pytest.mark.xfail(reason=...)` and an issue link rather than tolerating a red job. (3) Move
  `dependency-audit`/`gitleaks` to non-blocking `continue-on-error: true` **only** with tracking
  issues, so "red" always means "action needed." (4) Add branch protection requiring green
  `test`/`test-postgres` before merge to `main`.
- **Acceptance criteria:** A no-op PR shows all required jobs green; branch protection blocks
  merge on a red `test`/`test-postgres`.
- **Effort:** Medium (root-cause dependent). **Type:** Architectural (process).

### F4.2 — Frontend gate-tests (47 files) are not executed in CI · Priority: HIGH · Quick Win
- **Location:** `frontend/package.json` `"test:unit": "node --test 'src/**/*.test.js'"`; 47
  `*.test.js` incl. many `*Gate.test.js`; CI has no job invoking it (Phase 1 F1.11).
- **Description:** The frontend encodes real product contracts as tests — accessibility
  (`iconOnlyAriaGate`, `nativeSelectGate`), design-system (`dataGridStandardGate`,
  `selectionAccentGate`, `activeStateGate`), motion (`motion.test.js`), security
  (`safeExternalUrl.test.js`), URL-state (`shellUrlState`, `adminUrlPageClearGate`). None run in
  CI, so a change violating any of these contracts merges silently.
- **Why it matters:** These gates are the automated enforcement of the CLAUDE.md UI/UX/a11y rules
  — the very standards this audit's Phase 5 will assess. Un-run, they are documentation, not gates.
- **Evidence:** CI YAML lacks `npm run test:unit`; 47 test files present.
- **Risk:** Silent regressions of a11y/design-system/security-URL contracts.
- **Recommended solution:** Add a `frontend-tests` CI job: `npm ci --ignore-scripts && npm run
  test:unit`, required on PRs. Pair with the standalone `npm run build` gate.
- **Acceptance criteria:** CI fails if any `*.test.js` fails or the FE build breaks.
- **Effort:** Quick Win (~1h). **Type:** Quick Win.

### F4.3 — Coverage is unmeasured (no coverage/property/mutation tooling) · Priority: HIGH · Quick Win
- **Location:** `backend/requirements-dev.txt` (pytest + playwright only — no `pytest-cov`,
  `coverage`, `hypothesis`, `mutmut`); no coverage config anywhere.
- **Description:** With 28.6k test LOC there is genuine coverage, but it is unquantified. Nobody
  can say which correctness-critical paths (risk math, dialect-specific SQL, auth, backup/restore)
  are actually exercised, or whether new code is tested.
- **Why it matters:** Unmeasured coverage means regressions in untested branches are invisible;
  it also prevents a coverage-ratchet policy that would keep quality from eroding over years.
- **Recommended solution:** Add `pytest-cov`; run `pytest --cov=. --cov-report=xml --cov-report=term`
  in CI; publish the number and set a floor (start at the current measured value, ratchet up).
  Add `hypothesis` property tests for the deterministic engines (risk scoring, IOC
  normalization). Consider `mutmut` on `scoring/` and `detection/` to test the tests.
- **Acceptance criteria:** CI reports coverage %; PRs that drop coverage below the floor fail.
- **Effort:** Quick Win (cov wiring) / Medium (property + mutation). **Type:** Quick Win.

### F4.4 — E2E / integration depth is thin (≈1 smoke + 1 round-trip) · Priority: HIGH · Architectural
- **Location:** only `backend/tests/test_playwright_smoke.py` and
  `test_backup_roundtrip_postgres.py` are true cross-boundary tests; the other ~185 are
  module/unit tests. (`test_intel_snapshot_export.py` adds an export→restore smoke.)
- **Description:** Critical multi-component user workflows — login → feed → filter → open drawer →
  generate detection → export; nightly ingest → enrich → correlate → risk; webhook alert delivery
  end-to-end — are not covered by full-stack integration tests. Most tests mock external feeds and
  exercise one module.
- **Why it matters:** Unit tests can all pass while the *wiring between* correlation, scoring,
  detection, and the API is broken — exactly the failure class integration tests exist to catch.
  For an intelligence platform, the end-to-end pipeline correctness is the product.
- **Evidence:** filename scan shows two integration-class files; heavy per-module unit structure.
- **Recommended solution:** Add a small set of high-value integration tests against a Postgres
  Testcontainer: (a) ingest fixture CVEs → assert enrichment+correlation+risk materialize
  consistently; (b) API contract tests hitting real routers with a seeded DB for the top 10
  endpoints; (c) one Playwright E2E of the core analyst journey. Keep them in a separate,
  required-but-tagged CI job so they don't slow the unit lane.
- **Acceptance criteria:** The ingest→enrich→correlate→risk pipeline and top-10 API contracts are
  covered end-to-end; the core UI journey has one green Playwright path.
- **Effort:** Medium–Large. **Type:** Architectural.

### F4.5 — Data integrity for multi-write flows relies on ad-hoc transactions (carries F2.9/F3.8) · Priority: HIGH · Architectural
- **Location:** `backend/correlation/engine.py::_recover_db_transaction` / `run_nightly_correlation`;
  ingest/enrich flows in `feeds/`, `db/*`; no `UnitOfWork`/`@transactional` boundary.
- **Description:** Multi-step writes (ingest+enrich+correlate; nightly correlation materialization)
  don't run under an enforced transaction boundary, and the correlation engine carries bespoke
  transaction-recovery — a sign a partial write can occur. Combined with the dual-dialect layer,
  Postgres-only integrity semantics (FK, `ON CONFLICT`, savepoints) may differ from the SQLite
  default suite.
- **Why it matters:** Data integrity is foundational for an intelligence product — a partially
  applied correlation or a half-ingested CVE produces silently wrong analyst output.
- **Evidence:** `_recover_db_transaction` exists; conftest documents dialect-specific integrity
  checks (`PRAGMA integrity_check` vs `pg_catalog` probes) — integrity behavior differs by backend.
- **Recommended solution:** Introduce explicit transaction/savepoint boundaries for the known
  multi-write flows (Phase 2 F2.9, Phase 3 F3.8) and add integrity regression tests that inject a
  mid-flow failure and assert no partial rows — run on **Postgres** (the production dialect).
- **Acceptance criteria:** Injected mid-flow failure leaves consistent state; integrity tests run
  against Postgres in CI.
- **Effort:** Medium. **Type:** Architectural.

### F4.6 — Dev environment not reproducible off Python 3.12 (`numpy==2.5.1` pin) · Priority: MEDIUM · Quick Win
- **Location:** `backend/requirements.txt` (`numpy==2.5.1`, which is Requires-Python ≥3.12);
  no `.python-version`, no `pyproject`-declared `requires-python`, no lockfile.
- **Description:** `pip install -r requirements.txt` fails on Python 3.11 (verified: this sandbox
  is 3.11.15 → "No matching distribution found for numpy==2.5.1"). The suite is therefore only
  installable on exactly 3.12, but nothing in the repo *declares* that requirement, so a
  contributor discovers it as a cryptic pip error.
- **Why it matters:** Onboarding friction and non-reproducible local runs (this audit could not
  run the suite locally for that reason); "works on CI only" hides environment-coupled bugs.
- **Recommended solution:** Add `requires-python = ">=3.12"` to a `backend/pyproject.toml` and a
  `.python-version` (3.12); document in `CONTRIBUTING.md`. Consider a hash-pinned lockfile
  (`pip-tools`/`uv`) so installs are byte-reproducible.
- **Acceptance criteria:** A fresh clone on the documented Python installs cleanly; wrong Python
  fails with a clear message, not a numpy resolver error.
- **Effort:** Quick Win. **Type:** Quick Win.

### F4.7 — Test isolation has been fragile; enforce it structurally · Priority: MEDIUM · Quick Win
- **Location:** `backend/tests/conftest.py` (session-autouse Postgres TRUNCATE isolation; the
  `_postgres_dsn_or_none` docstring documents a real past cross-test pollution via module-level
  `os.environ["DATABASE_URL"] = ""`).
- **Description:** The fixtures are well-built, but the documented incident shows module-level env
  mutation can defeat isolation for every subsequent test. There's no guard preventing a new test
  file from re-introducing the same class of bug.
- **Why it matters:** Order-dependent test pollution produces flaky, hard-to-debug failures and
  can *mask* real regressions — dangerous given F4.1.
- **Recommended solution:** Add a lint/guard test that fails if any test module mutates
  `os.environ["DATABASE_URL"]` at module scope (AST/grep check), and prefer `monkeypatch`
  everywhere. Consider `pytest-randomly` to surface order-dependence deliberately.
- **Acceptance criteria:** A module-level `os.environ["DATABASE_URL"]=...` fails the guard;
  suite passes under randomized order.
- **Effort:** Quick Win. **Type:** Quick Win.

### F4.8 — Feature completeness is high but not machine-verified against a spec · Priority: LOW · Quick Win
- **Location:** `docs/PRODUCT_STATUS.md` ("Shipped vs planned" table), `docs/planning/ROADMAP.md`.
- **Description:** Completeness is tracked in prose (mostly "shipped," small "planned/open" set, 7
  skipped tests, no real stubs). There's no automated link between the shipped-feature list and a
  test proving each shipped feature exists/works, so drift between "documented as shipped" and
  "actually working" is possible.
- **Why it matters:** For release/enterprise readiness (Phase 11), each advertised capability
  should map to a passing test.
- **Recommended solution:** Maintain a lightweight feature→test traceability matrix (even a table
  in `docs/audit/` or a `@pytest.mark.feature("...")` marker) so "shipped" is provable.
- **Acceptance criteria:** Every "shipped" row maps to at least one passing test id.
- **Effort:** Quick Win–Medium. **Type:** Quick Win.

---

## Overall Score: **6.5 / 10**

| Sub-audit | Score |
|---|---|
| Functional Testing | 7.5 / 10 |
| End-to-End Workflow | 5 / 10 |
| Feature Completeness | 8 / 10 |
| Integration Testing | 5 / 10 |
| Regression Testing | 6 / 10 |
| Data Integrity | 6.5 / 10 |

## Strengths
- Large, well-distributed unit suite (187 files) with mature isolation (per-test Postgres
  TRUNCATE) and documented, fixed isolation incidents.
- Strong "gate test" culture encoding a11y/design-system/security contracts in the frontend.
- Real backup/restore and intel-snapshot round-trip smokes on Postgres; dialect-aware integrity
  probes (`pg_catalog` vs `PRAGMA`).
- High feature completeness with an explicit shipped-vs-planned ledger.

## Weaknesses
- CI baseline-red → untrustworthy regression signal (F4.1).
- FE gate-tests not CI-run (F4.2); coverage unmeasured (F4.3); thin E2E/integration (F4.4).
- Ad-hoc multi-write transactions (F4.5); non-reproducible off 3.12 (F4.6).

## Immediate Action Items
1. **Root-cause and green the `test`/`test-postgres` jobs; add branch protection (F4.1).**
2. Add `frontend-tests` + `build` CI jobs (F4.2).
3. Add `pytest-cov` and publish coverage with a floor (F4.3).
4. Declare `requires-python>=3.12` + `.python-version` (F4.6); add env-mutation guard test (F4.7).

## Long-Term Recommendations
1. Build a focused E2E/integration layer on a Postgres Testcontainer (pipeline + top-10 API +
   one UI journey) (F4.4).
2. Add transaction boundaries + integrity regression tests on Postgres (F4.5).
3. Add property tests for deterministic engines and mutation testing on `scoring/`+`detection/`
   (F4.3).
4. Feature→test traceability matrix (F4.8).

## Production-Readiness Assessment (Phase 4 areas)
**Not ready until CI is green — 6.5/10.** The suite is substantial and the culture is strong, but
a **red baseline (F4.1) is a release blocker**: no correctness claim is verifiable while the
required jobs fail by default, and the best regression protection (FE gate-tests) doesn't run in
CI (F4.2). Once CI is trustworthy again, the next-order gaps are E2E/integration depth (F4.4) and
measured coverage (F4.3). Fix F4.1 + F4.2 before any release-readiness sign-off.
