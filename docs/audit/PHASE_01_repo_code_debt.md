# PHASE 1 — Repository Organization, Code Quality & Technical Debt

*Reviewed at commit `61c686f` on `claude/engineering-audit-dzib4j`. Scope: repository
structure, tooling, code-quality signals, and accumulated debt. Backend ~50.4k LOC
(excl. tests), test suite ~28.6k LOC, frontend ~60k LOC.*

> **How to use this doc (for Cursor Composer 2.5):** Each finding carries a concrete
> Location, a Recommended Solution with code sketch, and Acceptance Criteria. Execute
> Quick Wins first (they unblock the guardrails), then Architectural changes. Do not
> merge behavioral changes with formatting changes in the same PR.

---

## Executive Summary

BRIEFR is an unusually disciplined codebase for its size/stage. Backend is cleanly
decomposed into ~34 domain packages; test volume is high (187 backend test files, 0.57
test:source ratio); inline debt markers are essentially nonexistent (1 match, 0 bare
`except:`); no secrets/DBs are committed; `.gitignore` is thorough; docs are large and
curated with a real `archive/` discipline; CI runs the suite against **both** SQLite and
Postgres plus dependency-audit and Playwright smoke.

Weaknesses are concentrated and structural: (1) **no linter/formatter/type-checker for
either language** and no style gate in CI; (2) **god-files** (`admin.py` 2,565 LOC/66
routes; `cves.py` 1,996 LOC/4 sub-routers; `IOCLookup.jsx` 1,379 LOC); (3) two
**dual-maintenance drift surfaces** — risk scoring (backend `risk.py` + frontend
`riskScore.js`) and 401 parallel `_SQLITE`/`_PG` SQL constants. None are emergencies; all
become expensive if left until the codebase doubles.

**Overall Score: 7.5 / 10.**

---

## Findings

### F1.1 — No linter/formatter/type-checker; no style gate in CI  · Priority: HIGH · Architectural
- **Location:** repo-wide. Absent: `backend/pyproject.toml`/`.ruff.toml`/`.flake8`;
  `frontend/eslint.config.*`/`.prettierrc*`. `backend/requirements-dev.txt` = pytest +
  playwright only. `frontend/package.json` has no eslint/prettier dep.
  `.github/workflows/backend-tests.yml` has no lint/type step.
- **Description:** No automated lint (ruff/flake8), format (black/prettier), or static
  typing (mypy/pyright) exists, and CI does not enforce style. The CLAUDE.md safety rules
  (e.g. "never interpolate secrets into log strings") are enforced by convention only.
- **Why it matters:** For software maintained for years by rotating contributors, the
  linter is the institutional memory of the rules; many CLAUDE.md rules are mechanically
  checkable and today rely on human/agent vigilance.
- **Evidence:** `find` for lint configs → none; `grep -i eslint package.json` → none; CI
  YAML lacks lint job.
- **Risk:** Style drift, safety-rule regressions past review, onboarding friction.
- **Recommended solution:**
  1. Add `backend/pyproject.toml`:
     ```toml
     [tool.ruff]
     line-length = 100
     target-version = "py312"
     [tool.ruff.lint]
     select = ["E","F","I","B","BLE","UP","SIM","LOG","S"]
     ignore = ["S101"]  # asserts in tests
     [tool.ruff.lint.per-file-ignores]
     "tests/**" = ["S","B"]
     ```
  2. Add `frontend/eslint.config.js` (flat config) with `eslint`, `eslint-plugin-react`,
     `eslint-plugin-react-hooks`, and `prettier`; scripts `"lint"` / `"format:check"`.
  3. Add a `lint` CI job running `ruff check`, `ruff format --check`, `npm run lint`,
     `npm run format:check`. Land the initial `ruff format`/`prettier --write` in a single
     **formatting-only** PR to avoid a giant mixed diff.
  4. Add `pyright` (or mypy) in non-blocking mode initially.
- **Acceptance criteria:** `ruff check backend` and `eslint frontend/src` both pass in CI;
  a deliberately mis-formatted file fails the `lint` job; no behavioral diffs in the
  formatting PR (verified via `git diff -w` being non-empty only on whitespace).
- **Effort:** Medium (1–2 days incl. reformat PR). **Type:** Architectural.

### F1.2 — God-file routers: `admin.py` (2,565 LOC/66 routes), `cves.py` (1,996 LOC/4 routers) · Priority: MEDIUM · Architectural
- **Location:** `backend/routers/admin.py`, `backend/routers/cves.py:101-104` (declares
  `changes_router`, `list_router`, `detail_router`, `intel_router`).
- **Description:** 66 handlers in one 2,565-line admin module; `cves.py` already splits
  into four internal routers — a signal it wants to be four files. Combined 4,561 LOC.
- **Why it matters:** Highest-churn, highest-conflict, hardest-to-review surfaces.
  CLAUDE.md couples admin routes to scheduler-lock strings ("job `id=` strings in
  `scheduler.py` must stay in sync with `routers/admin.py`") — risky inside a 2.5k-line file.
- **Evidence:** `wc -l`: admin 2565, cves 1996; `grep -c '@router.'` admin=66.
- **Risk:** Merge conflicts, reviewer fatigue → bugs in the admin/scheduler-lock coupling.
- **Recommended solution:** Convert `routers/admin.py` → `routers/admin/` package split by
  concern (`feeds.py`, `ai_ops.py`, `database.py`, `api_keys.py`, `webhooks.py`,
  `users.py`), each exposing an `APIRouter`; `routers/admin/__init__.py` re-exports one
  aggregate `router` so `main.py` import is unchanged. Split `cves.py`'s four routers into
  four files under `routers/cves/`. Pure structural move; existing tests are the safety net.
- **Acceptance criteria:** No route path/method changes (diff the OpenAPI schema before/after
  — must be identical); full test suite green both dialects; each new file <600 LOC.
- **Effort:** Medium (~1 day each, mechanical). **Type:** Architectural.

### F1.3 — Dual risk-scoring implementation with duplicated weight constants · Priority: HIGH · Architectural (Quick-Win guard available)
- **Location:** `backend/scoring/risk.py:9-14` (weights) and
  `frontend/src/scoring/riskScore.js:10-17` (`DEFAULT_WEIGHTS`) + fns `calculateThreatScore`
  (line ~360), `kevScoreRaw`, `exploitScoreRaw`, `threatBand`, `classifyEnvironment`,
  `correlationEscalation`, `deriveOperationalPriority`, `applyCorrelationEscalationToRiskScore`.
- **Description:** FE documents "canonical scoring runs on the backend" and fetches weights
  via `GET /api/config/risk`, yet hardcodes the same weight literals AND ships parallel
  scoring/classification logic that can silently diverge from `risk.py`.
- **Why it matters:** Risk score is the product's headline output. Two implementations will
  drift; a backend threshold change not mirrored produces a UI/PDF that disagrees with the
  API — the highest-consequence correctness-drift surface in the repo.
- **Evidence:** identical weight literals (0.35/0.25/0.15/0.10/0.10/0.05) in both files; FE
  function inventory shows raw component computation, not just formatting.
- **Risk:** UI/API/PDF divergence in the headline metric; user-trust erosion.
- **Recommended solution:**
  - **Quick-Win guard (do now, ~2h):** add `frontend/src/scoring/riskScore.weights.test.js`
    asserting FE `DEFAULT_WEIGHTS` equals values fetched from a fixture snapshot of
    `GET /api/config/risk`; and a backend test asserting the config endpoint returns exactly
    the `risk.py` constants. Fail CI on drift.
  - **Architectural:** make FE render only server-provided `components`/`score`/`band`;
    delete client-side recomputation, or generate a single shared JSON contract
    (`risk_contract.json`) emitted by backend and imported by FE.
- **Acceptance criteria:** Changing a weight in `risk.py` without updating the FE fails a
  test; FE displays the same numeric score the API returns for a fixed CVE fixture.
- **Effort:** Small (guard) / Medium–Large (unify). **Type:** Architectural + Quick-Win guard.

### F1.4 — 401 parallel `_SQLITE`/`_PG` SQL constants across 15 files · Priority: MEDIUM · Architectural
- **Location:** `backend/db/**` (15 files; ~401 `_SQLITE`/`_PG` matches; 9 `is_postgres()`
  branches in the db layer).
- **Description:** `db/` is Postgres-native but keeps parallel SQLite constants so the
  **default** (SQLite) test suite stays green. Default CI job therefore exercises the
  non-production dialect; a query can pass the primary signal and break prod Postgres
  (mitigated by the separate `test-postgres` CI job).
- **Why it matters:** Asymmetric coverage — the fast/default path tests the wrong dialect;
  401 occurrences is a large dual-maintenance surface.
- **Evidence:** `grep -c '_SQLITE|_PG' backend/db` → 401 across 15 files; CI default job = SQLite.
- **Risk:** Postgres-only prod bugs escaping the primary signal; growing maintenance tax.
- **Recommended solution:** Long-term: make Postgres the default test target via
  Testcontainers so prod dialect is the primary signal, letting SQLite become opt-in.
  Short-term: add a test that every `_PG` constant has a matching `_SQLITE` (or an explicit
  `# pg-only` marker), and track the count as a ratchet that may only decrease.
- **Acceptance criteria:** A new `_PG` const without a sibling fails the guard test; CI
  documents which dialect each job covers.
- **Effort:** Large (infra) / Small (ratchet). **Type:** Architectural.

### F1.5 — Oversized frontend components · Priority: MEDIUM · Architectural
- **Location:** `IOCLookup.jsx` (1379), `App.jsx` (1088), `DetailDrawer/index.jsx` (1002),
  `DetailDrawer/IntelTab.jsx` (944), `DetailDrawer/OverviewTab.jsx` (833); 13 files >500 LOC.
- **Description:** Large components bundle fetching + state + presentation, defeating
  memoization and making the required loading/empty/error/data discipline hard to audit.
- **Recommended solution:** Extract data hooks (`useIocLookup`, etc.) and presentational
  subcomponents; target <400 LOC. Add ESLint `max-lines` warn (after F1.1).
- **Acceptance criteria:** No component >600 LOC; `npm run build` green; visual parity.
- **Effort:** Medium (incremental). **Type:** Architectural.

### F1.6 — 28 silently-swallowed `except Exception: pass/continue` · Priority: MEDIUM · Quick Win + guard
- **Location:** backend non-test code (28 sites; grep `except Exception` + next line `pass`/`continue`).
- **Description:** Blanket-swallowing hides real failures, contradicting the RCA-first mandate.
- **Recommended solution:** Per site, narrow the exception type and add at least
  `logger.debug/warning(..., exc_info=True)` with context. Enable ruff `BLE001` to block new ones.
- **Acceptance criteria:** `ruff check --select BLE001` clean; each remaining broad catch has a log line.
- **Effort:** Small–Medium. **Type:** Quick Win.

### F1.7 — Documentation sprawl vs the "no new top-level docs" rule · Priority: LOW · Quick Win
- **Location:** `docs/` — 20 top-level `.md`, 85 total, 29 archived; 5 root `.md`.
- **Description:** Overlapping user docs (`USE`/`HOW_IT_WORKS`/`LEARNING_PATH`/`ONBOARDING`)
  and a declared precedence hierarchy make the single-source-of-truth spread across files.
- **Recommended solution:** Make `docs/index.md` an authoritative map with explicit
  "authoritative vs snapshot" labels; consolidate overlapping user docs. Defer deep work to Phase 10.
- **Acceptance criteria:** `index.md` lists every doc with an authority label; no orphan docs.
- **Effort:** Quick Win (index) / Medium (consolidation). **Type:** Quick Win.

### F1.8 — `AGENTS.md` and `CLAUDE.md` near-duplicate dual-maintenance · Priority: LOW · Quick Win
- **Location:** root `AGENTS.md` (153 LOC) + `CLAUDE.md` (144 LOC).
- **Recommended solution:** Make one canonical; the other a thin pointer (or generate one
  from the other) to prevent divergence.
- **Acceptance criteria:** Only one file contains the rules; the other references it.
- **Effort:** Quick Win. **Type:** Quick Win.

### F1.9 — Config/settings module sprawl (5 modules) · Priority: LOW · Quick Win
- **Location:** `backend/settings.py`, `config_schema.py`, `operator_settings.py`,
  `db/config.py`, `routers/config.py`.
- **Recommended solution:** Add a header comment to each stating its single responsibility;
  verify no overlapping keys. Deep treatment in Phase 8 (Configuration Audit).
- **Acceptance criteria:** Each module's docstring states what it owns; no key defined twice.
- **Effort:** Quick Win. **Type:** Quick Win.

### F1.10 — `correlation/copy.py` shadows the stdlib `copy` module name · Priority: LOW · Quick Win
- **Location:** `backend/correlation/copy.py` (analyst-facing narrative text helpers).
- **Recommended solution:** Rename to `correlation/narrative.py`; update imports.
- **Acceptance criteria:** No module named `copy.py`; tests green.
- **Effort:** Quick Win. **Type:** Quick Win.

### F1.11 — Frontend unit tests not CI-gated; stray `console.*` in prod · Priority: MEDIUM · Quick Win
- **Location:** `frontend/package.json` `test:unit` (47 `*.test.js` files); CI lacks the job;
  5 `console.*` calls in non-test `*.jsx`.
- **Recommended solution:** Add a `frontend-tests` CI job (`npm run test:unit`) plus a
  standalone `npm run build` gate (currently only implicit inside `playwright-smoke`).
  Add ESLint `no-console` (allow `warn`/`error` if intentional).
- **Acceptance criteria:** CI fails if a FE unit test fails or the FE build breaks; no stray `console.log`.
- **Effort:** Quick Win (CI wiring ~1h) + Small (cleanup). **Type:** Quick Win.

---

## Overall Score: **7.5 / 10**

| Sub-audit | Score |
|---|---|
| Repository Organization | 8 / 10 |
| Code Quality | 7 / 10 |
| Technical Debt | 7.5 / 10 |

## Strengths
- Clean modular backend (~34 focused packages); real router/db/domain separation.
- High test investment; CI runs both SQLite and Postgres + pip-audit + npm audit + Playwright smoke.
- Near-zero inline debt markers, 0 bare `except:`; no committed secrets/DBs/artifacts; thorough `.gitignore`.
- Strong doc/archive discipline with explicit precedence.
- Security-conscious conventions codified (redacting structured logging, SSRF-aware webhook client, `redact.py`, `settings_crypto.py`).

## Weaknesses
- No lint/format/type gate (F1.1) — biggest gap.
- God-files (F1.2, F1.5); two silent-drift surfaces (F1.3, F1.4); swallowed exceptions (F1.6);
  FE tests not CI-gated (F1.11).

## Immediate Action Items (Quick Wins, ~1–2 days)
1. Wire `npm run test:unit` + standalone `npm run build` into CI (F1.11).
2. Add scoring-weight contract test (F1.3 guard).
3. Rename `correlation/copy.py` (F1.10); collapse `AGENTS.md`/`CLAUDE.md` duplication (F1.8).
4. Triage the 28 swallowed exceptions (F1.6).

## Long-Term Recommendations
1. Introduce ruff + eslint/prettier (+ pyright) with a required CI gate via a formatting-only PR (F1.1).
2. Unify risk scoring to one authoritative implementation (F1.3).
3. Split `admin.py`/`cves.py` into packages; drive components <400 LOC (F1.2, F1.5).
4. Move CI default DB target to Postgres via Testcontainers (F1.4).

## Production-Readiness Assessment (Phase 1 areas)
**Conditionally ready — 7.5/10.** Organization and test coverage meet the production bar.
Blockers for an *enterprise, multi-year, multi-org* posture are process-level, not
defect-level: the missing lint/format/type gate (F1.1) and the two drift surfaces (F1.3,
F1.4). None block launch today; all should be scheduled before the codebase doubles again.
