# Phase 1 leftovers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each code task follows **TDD** (failing test → implement → green → commit).

**Goal:** Close the deferred Phase 1 items from program closeout: W7 CVE router package split, F1.5 first FE extract (IOCLookup), graphify attempt, plus the W7 regression (`tokens.py` missing `get_db`).

**Architecture:** Mirror the completed `routers/admin/` package pattern for `routers/cves/` (four sub-routers already exist; preserve OpenAPI identity via `main.py` include order). FE: extract data hook + presentational pieces from `IOCLookup.jsx` toward &lt;600 LOC without behavior change. Graphify: attempt install/update; honest HANDOVER if still missing.

**Tech Stack:** FastAPI routers, React JSX (no Tailwind), pytest, node:test, `./scripts/verify-local.sh` when feasible.

**Spec / prior plan:** `docs/superpowers/specs/2026-07-20-phase1-scoring-debt-design.md`, deferred notes in `docs/superpowers/plans/2026-07-20-phase1-scoring-debt.md` Task 14/16, audit `docs/audit/PHASE_01_repo_code_debt.md` F1.2/F1.5.

## Global Constraints

- Branch: `cursor/phase1-leftovers-91c2` off fresh `origin/main`
- OpenAPI route **method+path+order** for CVE-related routes must stay identical (`tests/test_router_split.py` green)
- `main.py` continues `from routers import cves as cves_router` and includes `changes_router` / `list_router` / `detail_router` / `intel_router` in the same order
- No scoring formula changes; no Catch-up / GPU work in this plan
- Design-system tokens only on any FE CSS touch; no hardcoded colors
- Minimum diff; match existing style; top-level imports (no new inline imports)
- **Parked (explicitly out of this leftovers plan):** repo-wide `ruff format` / full eslint tree; Testcontainers / Postgres-default CI
- Merge gate: targeted pytest + `npm run build`; Gemini disposition before merge
- graphify: attempt; if missing, HANDOVER note — do not invent `graphify-out/`

## File map

| Path | Role |
|------|------|
| `backend/routers/admin/tokens.py` | Add missing `get_db` import |
| `backend/tests/test_display_typography.py` / new admin tokens test | Regression for tokens endpoints |
| `backend/routers/cves.py` → `backend/routers/cves/` | Package split by existing four routers |
| `backend/routers/cves/__init__.py` | Re-export four routers |
| `backend/main.py` | Import path unchanged if package exports same names |
| `backend/tests/test_router_split.py` | Identity gate |
| `frontend/src/components/IOCLookup.jsx` | Shrink via extracts |
| `frontend/src/components/ioc/*` or hooks | New hook/presentational modules |
| `docs/HANDOVER.md`, `PRODUCT_STATUS.md` | Closeout notes |

---

### Task 1: Fix `tokens.py` missing `get_db` (W7 regression)

**Files:**
- Modify: `backend/routers/admin/tokens.py`
- Modify or create: regression test under `backend/tests/` (prefer extending `test_display_typography.py` or `test_ai_operations_admin.py` / new `test_admin_tokens_health.py`)

**Interfaces:**
- Consumes: `database.get_db` (same as other admin modules)
- Produces: `/api/admin/api-keys/health` and related token routes no longer NameError

- [x] **Step 1: Write failing test** that hits `GET /api/admin/api-keys/health` (or typography default path that uses tokens module) with admin_client and asserts **not** 500 / no `get_db is not defined` in body.

- [x] **Step 2: Run test — expect FAIL** (NameError/500).

- [x] **Step 3: Add top-level `from database import get_db`** (or package-equivalent used elsewhere in `routers/admin/`). Remove any accidental inline import. Ensure all handlers in the file that call `get_db` work.

- [x] **Step 4: Run test — PASS.** Also run `pytest tests/test_display_typography.py -q` if that was the original failing file.

- [x] **Step 5: Commit**

```bash
git add backend/routers/admin/tokens.py backend/tests/
git commit -m "fix(admin): import get_db in tokens router (W7 regression)"
```

---

### Task 2: Split `routers/cves.py` into `routers/cves/` package (F1.2 remainder)

**Files:**
- Create: `backend/routers/cves/` package (`__init__.py`, modules for changes/list/detail/intel + shared helpers)
- Delete or shrink: `backend/routers/cves.py` (must not shadow package — remove module file after package exists)
- Modify: only if needed for imports; `main.py` should keep `from routers import cves as cves_router`

**Interfaces:**
- Produces: `cves_router.changes_router`, `.list_router`, `.detail_router`, `.intel_router` (same objects main includes)
- Consumes: existing handlers; mechanical move preferred

- [x] **Step 1: Dump routes before** to `/tmp/cves-routes-before.txt` via TestClient/`app.routes` (method, path, order for all routes or CVE-related subset — full list preferred for identity).

- [x] **Step 2: Failing/guard test already exists** — run `pytest tests/test_router_split.py -q` on current tree (should PASS). After split, same test must still PASS. Optionally add a thin test that `import routers.cves` exposes the four routers.

- [x] **Step 3: Implement package split**
  - Shared helpers/models in `cves/helpers.py` or `cves/_common.py`
  - `changes.py`, `list.py`, `detail.py`, `intel.py` (or equivalent names matching the four routers)
  - `__init__.py` assigns/re-exports `changes_router`, `list_router`, `detail_router`, `intel_router`
  - Each file ideally &lt;800 LOC
  - Preserve registration order in `main.py`

- [x] **Step 4: Dump routes after; diff must be empty vs before. `pytest tests/test_router_split.py tests/test_cve*.py -q` (narrow to relevant) PASS.**

- [x] **Step 5: Commit**

```bash
git add backend/routers/cves backend/routers/cves.py backend/main.py backend/tests/
git commit -m "refactor(phase1): split cves router into package (F1.2)"
```

---

### Task 3: F1.5 — Extract from `IOCLookup.jsx` (first wave)

**Files:**
- Modify: `frontend/src/components/IOCLookup.jsx`
- Create: e.g. `frontend/src/components/ioc/useIocLookup.js` and/or presentational subcomponents under `frontend/src/components/ioc/`
- Test: `frontend/src/components/ioc/*.test.js` or gate test that LOC of IOCLookup.jsx &lt; 600 (or substantially reduced vs baseline ~1379)

**Interfaces:**
- Behavior/visual parity: same props API to parent; no route/API contract changes
- Prefer extract **data hook** + one presentational cluster first

- [x] **Step 1: Baseline LOC** — record `wc -l IOCLookup.jsx`. Write failing test that asserts `IOCLookup.jsx` line count `< 600` (or `< 900` if 600 needs a second wave — **prefer &lt;600** per audit acceptance; if unreachable in one PR without risk, target &lt;900 and document follow-on in HANDOVER).

- [x] **Step 2: Extract hook/components; move logic without behavior change.** No hardcoded colors. Keep imports at top.

- [x] **Step 3: `node --test` for new unit tests + `npm run build` PASS. LOC assertion green.

- [x] **Step 4: Commit**

```bash
git add frontend/src/components/IOCLookup.jsx frontend/src/components/ioc/
git commit -m "refactor(phase1): extract IOCLookup hooks/components (F1.5 wave 1)"
```

---

### Task 4: Graphify attempt + docs closeout

**Files:**
- Modify: `docs/HANDOVER.md`, `docs/PRODUCT_STATUS.md` (brief), tick leftovers in `docs/planning/SPRINT_2026-07.md` / phase1 plan deferred notes if present
- Run: graphify install/update if feasible

- [x] **Step 1: Attempt**

```bash
command -v graphify && graphify update . || (pip install graphifyy 2>/dev/null; command -v graphify && graphify update . || echo GRAPHIFY_MISSING)
```

Result: **succeeded** after installing `graphifyy`; existing `graphify-out/`
rebuilt with `10591` nodes, `20315` edges, `631` communities. Do **not**
invent `graphify-out/` content.

- [x] **Step 2: HANDOVER entry** — leftovers done (tokens fix, cves package, IOCLookup extract); list still-parked (full format, Testcontainers, remaining FE &gt;600 files).

- [x] **Step 3: Commit docs; push branch; parent opens PR.**

```bash
git add docs/
git commit -m "docs: Phase 1 leftovers closeout"
```

---

## Self-review (plan vs leftovers list)

| Leftover | Task |
|----------|------|
| tokens `get_db` | Task 1 |
| CVE package split | Task 2 |
| FE F1.5 (incremental) | Task 3 (IOCLookup first) |
| graphify | Task 4 |
| full ruff format | Parked |
| Testcontainers | Parked |

## Execution handoff

**Subagent-Driven** (user preference: always).
