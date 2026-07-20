# Phase 1 debt + scoring program — Design

**Status:** Draft for maintainer review (2026-07-20)  
**Inputs:** `docs/audit/PHASE_01_repo_code_debt.md` (F1.1–F1.11); ADR-002; Perplexity deep research on KEV/EPSS/SSVC alignment; maintainer decisions (multi-PR same phase; backend sole engine; docs+graphify every relevant PR).

## 1. Goal

Execute **Phase 1 audit findings (F1.1–F1.11)** and **scoring hygiene + upgrades** in **one program**, delivered as **multiple serial/parallel PRs** (not one mega-PR). Keep ADR-002’s Threat / Environment / Operational Priority model. Make the backend the sole scoring engine. Integrate SSVC/EPSS/exposure improvements as additive, explainable layers without re-blending “unknown” environment into Threat.

## 2. Non-negotiables

- Threat Score stays **asset-independent**.
- Environment / exposure / criticality affect **OP and/or SSVC only**, never Threat math.
- `UNKNOWN` environment is a **state**, never phantom numeric points (no return of the 17.5 v1.1b bug).
- **CISA KEV** gets Threat floor 80; **VulnCheck-only** exploitation does **not** get that floor.
- CVSS is never a Threat floor.
- No new single “total risk” headline; OP band remains the action surface; SSVC is an **annotation**.
- Frontend is **display-only** for scores (no live `calculateThreatScore` / v1.1b recompute for UI numbers).
- Scoring remains **deterministic and LLM-independent**; EPSS/KEV consumed from stored inputs on the request path.
- Every PR that changes code or operator-visible behavior updates the **docs cycle** and runs **`graphify update .`** (graphify is assumed stale until refreshed).

## 3. Out of scope (later)

- Full CMDB / scanner / SBOM ingestion.
- Stakeholder-specific SSVC decision trees.
- Enforced remediation SLAs (optional guidance only, later).
- Making Postgres Testcontainers the default CI target (optional follow-on after F1.4 ratchet).
- Deleting `legacy_risk_v11b` from the API in the first hygiene PR (deprecate later once consumers are gone).

## 4. Program shape

**Approach:** One Phase 1 program, many PRs.

| Track | Content |
|-------|---------|
| **A — Scoring hygiene** | F1.3 + wallboard unify + KEV/VulnCheck clarity + FE display-only |
| **B — Scoring upgrades** | EPSS OP rules → SSVC annotation → exposure/criticality flags |
| **C — Repo debt** | F1.6–F1.11 quick wins → F1.1 lint → F1.2/F1.5 splits → F1.4 SQL ratchet |

**Parallelism:** W2–W5 (scoring) are **serial** (shared `backend/scoring/` + DetailDrawer). Track C waves must not land formatting or god-file moves that conflict with open scoring PRs; default lint (W6) **after** W5.

## 5. Wave / PR map

| Wave | Theme | Delivers |
|------|--------|----------|
| **W0** | Kickoff | This spec + implementation plan; HANDOVER/SPRINT pointer; baseline `graphify update .` |
| **W1** | Quick wins | F1.6 (swallow triage start), F1.7 docs index labels, F1.8 AGENTS→CLAUDE pointer, F1.9 config headers, F1.10 rename `correlation/copy.py`, F1.11 FE unit tests in verify/CI |
| **W2** | Scoring hygiene | FE display-only; wallboard ranks by OP then Threat (not v1.1b total); CISA-only KEV floor; parity/guard tests; correlation escalation contract (prefer backend; FE merge documented if deferred) |
| **W3** | EPSS → OP | Additive OP one-band escalations (absolute ≥0.5; delta/rising); Threat formula unchanged; versioned rationale |
| **W4** | SSVC annotation | `calculate_ssvc_outcome()`; `ssvc` on `POST /api/cves/{id}/risk`; UI chip beside OP; P↔SSVC crosswalk in docs; Threat unchanged |
| **W5** | Exposure / criticality | Profile flags (`internet_facing`, `criticality`, optional `privileged_service` / `ot_safety`); OP modifiers only; defaults preserve current behavior when absent |
| **W6** | Lint gate (F1.1) | Formatting-only PR first; then ruff + eslint/prettier CI gate |
| **W7** | God files (F1.2) + FE size (F1.5) | `routers/admin/` package; cves router split; incremental component extracts; OpenAPI path/method identity |
| **W8** | Dual-SQL (F1.4) | Sibling `_PG`/`_SQLITE` guard + count ratchet; Postgres-default CI deferred |

Branch naming: `cursor/<wave-slug>-91c2` (or project suffix in force).

## 6. Scoring behavior detail

### 6.1 Engine ownership

- Authoritative: `backend/scoring/` (`threat.py`, `environment.py`, `priority.py`, `risk.py` helpers; W4 adds `ssvc.py`).
- API: `POST /api/cves/{cve_id}/risk` remains the single read model for the drawer.
- UI: Overview/DetailDrawer/wallboard consume API fields only.
- `GET /api/config/risk` may continue to expose weight constants for **display**; it is not a second scoring engine.

### 6.2 W2 hygiene

- Remove or stop using frontend live Threat/v1.1b recalculation for displayed numbers.
- Wallboard top-risk ranking: **Operational Priority band, then Threat score** (not `legacy_risk_v11b.total`).
- Keep returning `legacy_risk_v11b` until a later deprecation PR.
- Confirm KEV floor applies only when CISA `is_kev` is true.

### 6.3 W3 EPSS OP rules (Threat unchanged)

Additive, never replacing KEV dominance. Examples to encode and version:

- If Threat band is HIGH or MED, EPSS ≥ 0.5, Environment ≥ POSSIBLE → escalate OP one band (when not already P1).
- If EPSS rose sharply (delta / momentum rising) and Environment ≥ POSSIBLE → allow P3→P2.

Missing EPSS stays 0. Rules appear in OP `rationale`.

### 6.4 W4 SSVC annotation

- Deterministic `ssvc` object: `{ version, outcome: Act|Attend|Track*|Track, factors, path }`.
- Inputs: existing Threat/Environment signals + W5 flags when present; optional Vulnrichment SSVC when already stored.
- Does **not** replace P-band; UI shows SSVC beside OP.
- Doc crosswalk: P1↔Act, P2↔Attend, P3↔Track*, P4↔Track.

### 6.5 W5 exposure / criticality

- Optional profile fields with safe defaults (absent = today’s behavior).
- Feed **OP (and SSVC factors)** only — never Threat.
- Example: CISA KEV + `internet_facing` + env not NO_MATCH → prefer P1 when table would otherwise allow lower only due to weak env (exact table cells specified in implementation plan / tests).

### 6.6 Missing data / errors

- No profile → Environment UNKNOWN, OP `provisional: true`.
- Missing new flags → no modifier from those factors.
- No LLM on scoring path; no live upstream fetch for score math.

## 7. Documentation and graphify cycle

On **every** PR that changes scoring or operator-visible behavior (W2–W5; also debt PRs that change operator docs):

1. `docs/PRODUCT_STATUS.md`
2. `docs/SYSTEM_DESIGN.md`
3. `docs/API_REFERENCE.md` (endpoint/shape changes)
4. ADR-002 addendum or new ADR if semantics change (W3–W5)
5. `docs/HANDOVER.md` (newest first); sprint tick if applicable
6. Study-guide + learn regen when teaching content changes: `scripts/build_study_guide_book.py` then `scripts/build_learn_site.py`
7. **`graphify update .`**

**W0:** baseline graphify refresh so later waves do not navigate a stale graph.

Do not treat graphify as exploration SSOT until the PR’s update has run.

## 8. Testing and merge gates

- Backend pytest for touched scoring modules + ADR-002 matrices (threat / environment / OP).
- Scoring PRs: fixture set covering CISA KEV, VulnCheck-only, high-EPSS non-KEV, UNKNOWN env, NO_MATCH — prove no unknown-asset phantom points.
- Frontend: `npm run build`; unit tests for display-only changes; assert no live score recompute.
- `./scripts/verify-local.sh` ( `--full` when Postgres/tools available).
- W6: formatting-only PR separate from behavioral PRs.
- W7: OpenAPI schema identity before/after router splits.

## 9. Success criteria (program done)

1. F1.1–F1.11 addressed per wave map (F1.4 = ratchet in-phase).
2. Backend sole scoring engine; FE display-only; wallboard Threat/OP; CISA-only KEV floor; EPSS OP rules; SSVC on `/risk`; exposure/criticality OP modifiers.
3. ADR-002 intact (no Environment→Threat blend; no UNKNOWN phantoms; no new total-risk headline).
4. Docs + study-guide/learn current where teaching changed; graphify refreshed per relevant PR.
5. Each wave merged as its own PR after local verify and review disposition.

## 10. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Scoring + lint conflict | W6 after W5; no format mixed with behavior |
| DetailDrawer churn | Serial W2–W5; shared-surface rule |
| Stale graphify misleads agents | W0 + per-PR `graphify update .` |
| Scope creep (CMDB/SSVC trees) | Explicit out-of-scope list |
| FE/backend drift regression | Guard tests; delete live FE score path |

## 11. References

- `docs/audit/PHASE_01_repo_code_debt.md`
- `docs/decisions/ADR-002-operational-priority.md`
- `docs/PRODUCT_STATUS.md` (CVE Overview / scoring)
- `backend/scoring/{threat,environment,priority,risk,asset_match}.py`
- `POST /api/cves/{cve_id}/risk` in `backend/routers/cves.py`
- Maintainer + Perplexity research synthesis (2026-07-20 session)
