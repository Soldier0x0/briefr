# PHASE 7 — Security · Authentication · Authorization (RBAC) · Input Validation · API Security · Secrets Management · Privacy & Data Leakage · Dependency & Supply Chain

*Refreshed at pinned commit `ff23c18a4925b3b7082a2b1d1600884324d90d02`. Scope: auth/JWT, rate limiting, RBAC, input validation, dependency audit, LLM egress, DB explorer SQL construction, and security posture controls.*

---

## Executive Summary

The security posture is stronger than the prior audit because the highest-risk item, **F7.1 JWT fail-closed production startup**, is now fixed in actual control flow: `settings.py` checks `settings.is_production and not settings.jwt_secret` before any dev/test secret auto-generation. The root cause was ordering, and the current code resolves that class of failure rather than masking it.

The remaining gaps are narrower but still real. Rate limiting still defaults to per-process buckets unless `BRIEFR_RATE_LIMIT_STORE=db` is set. The dependency-audit workflow exists, but this refresh did not run it and does not claim it is green. Input validation is now a more concrete finding: pinned `routers/admin.py` still has raw `dict` bodies and direct `request.json()` paths, and there is no visible global request-body size guard in `main.py`.

**Overall Score: 8.3 / 10.**

---

## Finding Status

| ID | Status | Current disposition |
|---|---|---|
| F7.1 | CLOSED | Production JWT guard now runs before auto-generation; dev/test generation remains after the guard. |
| F7.2 | UPDATED | Shared DB-backed buckets exist, but remain opt-in via `BRIEFR_RATE_LIMIT_STORE=db`; no posture warning for multi-worker + memory store. |
| F7.3 | OPEN | `dependency-audit` workflow remains present; no fresh green evidence collected in this docs refresh. |
| F7.4 | OPEN | Frontend dependency ranges still use caret constraints; `npm ci --ignore-scripts` and overrides reduce but do not remove review/provenance risk. |
| F7.5 | OPEN | DB explorer still formats allowlisted identifiers; tests reject hostile filter columns, but internal quoting defense is not added. |
| F7.6 | UPDATED | Raw `dict` bodies and `request.json()` remain in admin/config paths; body-size guard still absent. |
| F7.7 | UPDATED | Empty LLM payload guard and redacted AI operations exist; external LLM data-flow/no-egress policy is still not fully documented. |
| F7.8 | UPDATED | Live role re-read and analyst read-only surfaces improved the model, but permissions remain essentially user/admin and single-tenant. |

---

## Open / Updated Findings

### F7.2 — Rate limiting remains opt-in shared state under multi-worker · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `backend/rate_limit_store.py`, `backend/rate_limit.py`, `settings.production_posture_warnings`.
- **Current evidence:** `shared_store_enabled()` enables DB-backed buckets only for `BRIEFR_RATE_LIMIT_STORE=db` / truthy values. `production_posture_warnings()` warns when `RATE_LIMIT_ENABLED=0`, but does not warn when production uses the in-memory store with multiple workers.
- **Risk:** A configured limit is enforced per process unless operators opt into the DB store; horizontal scale can still multiply effective login/IOC/admin limits.
- **Recommended solution:** Default to the shared store for production Postgres, or add a production posture warning when memory buckets are used with multi-worker/replica deployment. Document the required setting in operations.
- **Acceptance criteria:** Multi-worker production either uses shared buckets or emits an actionable warning; a test demonstrates global enforcement with two workers or equivalent shared-store simulation.

### F7.3 — Dependency-audit signal is still unverified · Status: OPEN · Priority: HIGH · Quick Win
- **Location:** `.github/workflows/backend-tests.yml` `dependency-audit`; `frontend/package.json` `audit:ci`.
- **Current evidence:** The workflow still runs `pip-audit -r backend/requirements.txt` and `npm run audit:ci`. This refresh did not run those jobs or inspect fresh CI logs, so no green claim is made.
- **Risk:** A standing red or unreviewed supply-chain job turns new high-severity advisories into background noise.
- **Recommended solution:** Run and triage the current audit output; upgrade dependencies or record explicit, time-boxed ignores/overrides. Make the gate actionable again.
- **Acceptance criteria:** Fresh `pip-audit` and `npm audit --audit-level=high` evidence is green, or every remaining advisory has a tracked, justified exception.

### F7.4 — Frontend dependency ranges are review-sensitive · Status: OPEN · Priority: MEDIUM · Quick Win
- **Location:** `frontend/package.json`, `package-lock.json`, CI `npm ci --ignore-scripts`.
- **Current evidence:** Dependencies and devDependencies still use caret ranges. `npm ci --ignore-scripts` and `overrides` for selected packages are good hardening, but lockfile refreshes can still move versions.
- **Risk:** Minor/patch supply-chain compromise can enter through a reviewed lockfile update unless provenance and high-risk package review are explicit.
- **Recommended solution:** Keep `npm ci --ignore-scripts`; add provenance/signature checks where supported; consider exact pins for untrusted-content packages and automated dependency PR review.
- **Acceptance criteria:** Lockfile changes are reviewed as security-relevant; provenance/audit checks run in CI where available.

### F7.5 — DB-explorer identifier interpolation is allowlisted but not internally quoted · Status: OPEN · Priority: LOW · Quick Win
- **Location:** `backend/db/explorer.py`, `backend/db/explorer_registry.py`, `backend/tests/test_db_explorer.py`.
- **Current evidence:** `validate_table_name()` rejects unknown/invalid names and tests reject a hostile filter column, but SQL templates still use `.format(table=spec.name, column=f_col, order_by=spec.order_by)`.
- **Risk:** Safe today because all identifiers come from `TableSpec`; future drift could bypass the invariant.
- **Recommended solution:** Add internal identifier quoting/assertion helpers for table, column, and order-by fragments, even after allowlist validation.
- **Acceptance criteria:** A hostile table/column/order value is rejected or safely quoted at the helper boundary, with regression tests.

### F7.6 — Mutation validation and payload-size caps are incomplete · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `backend/routers/admin.py`, `backend/main.py`, upload/config/admin mutation routes.
- **Current evidence:** Pinned admin routes still include raw `dict` bodies (`write_instance_typography_default`, `purge_storage`, `set_config`, webhook destination CRUD, scheduler run/pause/resume, restart) and direct `request.json()` calls. No global max body-size middleware was found in `main.py`.
- **Risk:** Loosely typed mutation payloads and unbounded request bodies expand the DoS and validation surface before business logic runs.
- **Recommended solution:** Replace raw `dict` bodies with Pydantic models, add a global body-size guard plus per-upload caps, and validate upload content types.
- **Acceptance criteria:** Every mutation body is model-backed; oversized requests fail with 413 before processing; upload paths have explicit caps and tests.

### F7.7 — LLM egress controls exist, but data-flow policy is still incomplete · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `backend/ai/llm_payload.py`, `backend/ai/llm_router.py`, `ai_operations`, docs.
- **Current evidence:** Empty/blank LLM payloads are skipped before provider calls, provider attempts are recorded without prompt text, and feature flags can disable several LLM paths. A complete documented external LLM data-flow and a guaranteed no-external-egress mode are still not evident.
- **Risk:** Enterprise self-hosted users need to know which CVE/exploit/detection data leaves the network and how to disable all external provider calls.
- **Recommended solution:** Document provider-bound fields by task, centralize a global no-external-LLM switch, and add tests ensuring asset/internal names are not included unless explicitly opted in.
- **Acceptance criteria:** Data-flow documentation exists; one configuration disables all external LLM egress; tests cover sensitive-field exclusion.

### F7.8 — Authorization remains coarse-grained · Status: UPDATED · Priority: LOW · Architectural
- **Location:** `dependencies.py`, `auth_middleware.py`, `routers/admin.py`, `RequireAdmin.jsx`.
- **Current evidence:** `require_user()` checks live `is_active`; `require_admin()` re-reads the DB role; admin routes are router-gated. Analyst-readable admin surfaces now exist for selected pages, but the backend role model is still essentially `user` and `admin`.
- **Risk:** Single-tenant self-host is acceptable, but least-privilege operator roles and tenant/object scoping are not ready for multi-org SaaS.
- **Recommended solution:** Decide and document the authz target: single-tenant self-host with a small read-only/operator role set, or multi-tenant role/permission/tenant scoping.
- **Acceptance criteria:** Documented authorization model; tests for each role boundary and object/tenant scope if introduced.

---

## Resolved since last audit

### F7.1 — Production JWT secret fail-closed guard · Status: CLOSED
- **Prior root cause:** In the older control flow, dev/test auto-generation populated `settings.jwt_secret` before the production guard, so `not settings.jwt_secret` could never be true.
- **Current control flow:** At pinned `ff23c18`, `settings = Settings()` is followed immediately by the production guard. Only after that does the dev/test `if not settings.jwt_secret:` block generate and persist a secret.
- **Why this closes the class:** Production cannot fall through into per-replica auto-generation; startup fails closed when `BRIEFR_ENV=production` and `JWT_SECRET` is absent. Dev/test still auto-generates and logs persistence failures instead of silently swallowing them.
- **Residual note:** Keep the guard above auto-generation in future settings refactors.

---

## Scores

| Sub-audit | Score |
|---|---|
| Security (general) | 8.3 / 10 |
| Authentication | 8.6 / 10 |
| Authorization (RBAC) | 7.7 / 10 |
| Input Validation | 7.5 / 10 |
| API Security | 8.5 / 10 |
| Secrets Management | 8.5 / 10 |
| Privacy & Data Leakage | 7.8 / 10 |
| Dependency & Supply Chain | 6.5 / 10 |

## Immediate Action Items
1. Triage `dependency-audit` with fresh evidence and restore it as an actionable gate (F7.3).
2. Add model-backed mutation bodies and body-size caps (F7.6).
3. Warn or default shared rate limiting for production multi-worker deployments (F7.2).

## Production-Readiness Assessment
**Strong for single-tenant self-host; improved to 8.3/10.** Closing F7.1 removes the prior must-fix auth startup defect. The remaining production concerns are supply-chain signal quality, scaled rate limiting, typed mutation inputs, and enterprise egress/RBAC expectations.
