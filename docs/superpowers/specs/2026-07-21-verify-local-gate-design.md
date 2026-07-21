# Restore local verify-local merge gate — Design

**Date:** 2026-07-21  
**Status:** Approved for planning (brainstorming)  
**Branch (implementation):** `cursor/verify-local-gate-91c2`

## 1. Goal

Restore a trustworthy local merge gate on `main` by fixing confirmed red failures in `./scripts/verify-local.sh`, without starting parked Phase 1 leftovers.

**Success criteria:**
- `tests/test_posture.py::test_security_readout_includes_posture` passes
- `tests/test_support_pack.py::test_support_pack_returns_redacted_bundle` (and sibling redaction test if it shares the same import) passes
- `tests/test_security_architecture_corpus.py::test_committed_corpus_has_no_drift` and `test_committed_architecture_graph_has_no_drift` pass
- Related admin drift endpoint tests that assert corpus match pass when included in the suite
- `./scripts/verify-local.sh` exits 0 for the project’s intended local gate (known-red external CI jobs such as gitleaks / dependency-audit remain non-blockers per existing project norms)

## 2. Scope

### In scope (single PR)

1. **Missing imports in** `backend/routers/admin/diagnostics.py`
   - `from datetime import datetime, timedelta, timezone` (used by `get_security` auth-cutoff window)
   - `Response` on the FastAPI import line (used by `export_support_pack`)
2. **Security corpus regeneration** via `python scripts/generate_security_corpus.py`
   - Commit only **generated** layer outputs under `backend/security_architecture/corpus/` that the script rewrites (e.g. `components.yaml`, `api_inventory.yaml`, scheduler/DB/self-stack YAML, `graphs/architecture.json` as produced)
   - Do **not** hand-edit curated YAML (`controls.yaml`, `trust_boundaries.yaml`, `abuse_cases.yaml`, etc.)
3. **Docs:** newest-first `docs/HANDOVER.md` entry with RCA + fix; touch `docs/PRODUCT_STATUS.md` only if needed for a one-line operator-visible note that Security / support-pack endpoints were broken and are restored
4. **Verification:** targeted pytest → `./scripts/verify-local.sh`; Gemini disposition before merge

### Explicitly out of scope

| Item | Disposition |
|------|-------------|
| Repo-wide `ruff format` / full formatting sweep | Parked (Phase 1 leftover) |
| Testcontainers / Postgres-default CI | Parked (Phase 1 leftover) |
| FE >600 LOC splits (`App.jsx`, `DetailDrawer/*`, …) | Parked (Phase 1 leftover) |
| Delete/quarantine unrouted `SecurityArchitecturePage` + gate rewrites | **Follow-up PR** (separate from this gate fix) |
| Wallboard / watchlist suite-order flakes | Not reproduced in isolation; not part of this fix |
| Behavior/API contract changes beyond restoring callability | Out of scope |

## 3. Root cause analysis

### 3.1 Admin Security readout (`test_posture`)

- **Symptom:** `GET /api/admin/security` returns HTTP 500; posture test asserts 200.
- **Why:** `get_security` in `diagnostics.py` evaluates `(datetime.now(timezone.utc) - timedelta(hours=24))` but after the admin package split those names are not imported → `NameError: name 'datetime' is not defined`.
- **Class of bug:** incomplete import restoration when moving code into `routers/admin/diagnostics.py`.

### 3.2 Support pack export (`test_support_pack`)

- **Symptom:** `GET /api/admin/diagnostics/support-pack` returns HTTP 500.
- **Why:** `export_support_pack` returns `Response(content=..., media_type=..., headers=...)` but `Response` is not imported → `NameError`.
- **Class of bug:** same incomplete-import class as §3.1.

### 3.3 Security architecture corpus drift

- **Symptom:** `test_committed_corpus_has_no_drift` fails: committed `components.yaml` (and related generated artifacts) disagree with a fresh generator run.
- **Why:** Live router/module inventory changed (admin splits, new endpoints) without regenerating the generated corpus layer. Drift test is working as designed.
- **Fix:** regenerate with the project script; commit generated outputs. Not a test waiver.

## 4. Architecture / approach

**Surgical restore, no redesign.**

1. Add missing **top-level** imports in `diagnostics.py` (project rule: no new inline imports).
2. Prefer `from fastapi import …, Response` to match FastAPI usage elsewhere; do not introduce Starlette-only imports unless required for compatibility.
3. Run corpus generator from repo root: `python scripts/generate_security_corpus.py` (script lives under `scripts/`, corpus under `backend/security_architecture/corpus/`).
4. Diff review: only generated corpus files + `diagnostics.py` + docs should change.

No new broker, migration, feature flag, or UI work.

## 5. Error handling & operator impact

- Once fixed, Admin → Security and “Export support pack” stop 500ing.
- Responses remain the existing shapes; no new error envelopes.
- Unexpected errors continue to hit the global 500 + `request_id` handler.

## 6. Testing strategy

| Step | Command / action | Expected |
|------|------------------|----------|
| Baseline red | `pytest tests/test_posture.py::test_security_readout_includes_posture tests/test_support_pack.py -q` | FAIL (NameError / 500) |
| After imports | Same command | PASS |
| Baseline corpus red | `pytest tests/test_security_architecture_corpus.py tests/test_security_architecture_corpus_drift_admin.py -q` | FAIL drift |
| After regen | Same command | PASS |
| Local gate | `./scripts/verify-local.sh` from repo root | Exit 0 for intended jobs |

Do not weaken drift tests. Do not skip corpus regen.

## 7. Delivery

- **Branch:** `cursor/verify-local-gate-91c2`
- **Commits (suggested):** (1) fix diagnostics imports; (2) regen security corpus; (3) HANDOVER (+ PRODUCT_STATUS if needed)
- **PR:** one squash-merge PR; Gemini medium+ findings addressed before merge
- **Standing process:** subagent-driven implementation after the plan is written

## 8. Follow-ups (not this PR)

1. ARCH orphan quarantine/delete + update `arch*Gate` tests that still reference `SecurityArchitecturePage`
2. When activated: Phase 1 parked leftovers (`ruff format`, Testcontainers, FE god-file splits) as separate programs

## 9. Spec self-review

- [x] No TBD/TODO placeholders
- [x] Scope matches brainstorming choices (A merge-gate + light park; ARCH = separate follow-up; one PR for imports+corpus)
- [x] RCA pairs each failure with a concrete fix
- [x] Out-of-scope list prevents scope creep into FE debt / format / Testcontainers
