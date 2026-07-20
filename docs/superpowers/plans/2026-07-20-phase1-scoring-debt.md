# Phase 1 Debt + Scoring Program — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Phase 1 audit items F1.1–F1.11 plus scoring hygiene/upgrades (backend-only engine, wallboard Threat/OP, EPSS OP rules, SSVC annotation, exposure flags) as multiple PRs in one program, with docs + graphify on every relevant PR.

**Architecture:** Keep ADR-002 axes (Threat / Environment / Operational Priority). Backend `scoring/` is the sole engine; FE display-only. SSVC and EPSS rules are additive OP/annotation layers — never re-blend Environment into Threat. Waves W2–W5 serial; debt waves avoid conflicting with open scoring PRs.

**Tech Stack:** FastAPI/`backend/scoring/*`, React/`frontend/src/scoring/riskScore.js`, pytest, node:test, `./scripts/verify-local.sh`, study-guide/learn builders, graphify when CLI available.

**Spec:** `docs/superpowers/specs/2026-07-20-phase1-scoring-debt-design.md`

## Global Constraints

- Branch per wave: `cursor/<wave-slug>-91c2` off fresh `origin/main`
- Threat stays asset-independent; UNKNOWN never adds phantom points
- CISA KEV floor only; VulnCheck-only has no Threat floor
- No new “total risk” headline; OP remains primary action band
- FE must not recalculate live Threat/v1.1b for display numbers
- Scoring PRs: update PRODUCT_STATUS, SYSTEM_DESIGN, API_REFERENCE, HANDOVER; regenerate study-guide/learn when teaching changes; run `graphify update .` (if CLI missing: install/document fallback and still refresh `graphify-out/` when tool exists)
- Do not mix formatting-only changes with behavioral scoring changes
- Merge gate: `./scripts/verify-local.sh` green; Gemini disposition before merge when bot comments
- Shared surfaces: do not parallelize W2–W5 with each other

## File map (program-wide)

| Path | Role |
|------|------|
| `backend/scoring/threat.py` | Threat v1.0 (unchanged formula in W3–W5) |
| `backend/scoring/environment.py` | Environment tiers |
| `backend/scoring/priority.py` | OP rules; W3 EPSS escalations |
| `backend/scoring/ssvc.py` | **Create W4** — SSVC annotation |
| `backend/scoring/risk.py` | Shared raws, momentum, legacy v1.1b |
| `backend/scoring/asset_match.py` | Asset/CPE; W5 profile flags consumers |
| `backend/routers/cves.py` | `POST /api/cves/{id}/risk` response shape |
| `backend/wallboard/service.py` | W2 rank by OP then Threat |
| `frontend/src/scoring/riskScore.js` | W2 display-only; drop live score use |
| `frontend/src/components/DetailDrawer/*` | Consume API fields; SSVC chip W4 |
| `frontend/src/pages/WallboardPage.jsx` | Display fields if payload shape changes |
| `backend/correlation/copy.py` → `narrative.py` | W1 F1.10 |
| `AGENTS.md` / `CLAUDE.md` | W1 F1.8 |
| `docs/index.md` | W1 F1.7 |
| `scripts/verify-local.sh` | W1 F1.11 add `npm run test:unit` |
| `backend/routers/admin.py` → `admin/` | W7 |
| Docs + builders + `graphify-out/` | Every scoring/debt-visible PR |

---

### Task 0: W0 — Plan already landed; kickoff HANDOVER + graphify baseline

**Files:**
- Modify: `docs/HANDOVER.md`
- Modify: `docs/planning/SPRINT_2026-07.md` (add Phase 1 program checkbox block if absent)
- Run: `graphify update .` when CLI available

**Interfaces:**
- Consumes: approved design spec
- Produces: HANDOVER entry pointing at spec + this plan

- [x] **Step 1: Append HANDOVER entry** (newest first) summarizing Phase 1 program waves W0–W8 and link to spec/plan paths. Also added Phase 1 W0–W8 checkbox block to `docs/planning/SPRINT_2026-07.md`.

- [x] **Step 2: Attempt graphify baseline**

```bash
command -v graphify && graphify update . || echo "GRAPHIFY_MISSING: install before scoring waves; do not treat graphify-out as fresh"
```

Result: **GRAPHIFY_MISSING** (`graphify` not on PATH; no `graphify-out/` refresh invented).

- [x] **Step 3: Commit on design branch or W0 branch**

```bash
git add docs/HANDOVER.md docs/planning/SPRINT_2026-07.md docs/superpowers/plans/2026-07-20-phase1-scoring-debt.md
git commit -m "docs: Phase 1 program kickoff (HANDOVER + sprint + plan ticks)"
```

---

### Task 1: W1 — F1.11 FE unit tests in verify-local

**Files:**
- Modify: `scripts/verify-local.sh`
- Test: `frontend` via `npm run test:unit` (already in package.json)

**Interfaces:**
- Consumes: existing `frontend/package.json` script `"test:unit": "node --test 'src/**/*.test.js'"`
- Produces: verify-local fails if any FE unit test fails

- [x] **Step 1: Write failing gate check** — add a step to `verify-local.sh` after `npm run build` that runs unit tests. Confirm current suite passes before relying on it.

- [x] **Step 2: Implement verify-local step**

```bash
step "Frontend unit tests (required — F1.11)"
(
  cd frontend
  if [[ ! -d node_modules ]]; then
    npm ci --ignore-scripts
  fi
  npm run test:unit
)
pass "npm run test:unit"
```

- [x] **Step 3: Run gate**

```bash
./scripts/verify-local.sh
```

Expected: FE unit tests step runs and passes (or fix any pre-existing failures in the same PR only if caused by the gate).

- [x] **Step 4: Commit**

```bash
git add scripts/verify-local.sh
git commit -m "ci: gate frontend unit tests in verify-local (F1.11)"
```

---

### Task 2: W1 — F1.10 rename `correlation/copy.py` → `narrative.py`

**Files:**
- Create: `backend/correlation/narrative.py` (move contents)
- Delete: `backend/correlation/copy.py`
- Modify: all importers of `correlation.copy` / `correlation.copy`
- Test: `backend/tests/` grepping copy imports

**Interfaces:**
- Consumes: existing narrative helper functions in `copy.py`
- Produces: module `correlation.narrative` with same public functions

- [x] **Step 1: Find all imports**

```bash
rg -n "correlation\.copy|from correlation import copy|correlation/copy" backend
```

- [x] **Step 2: Add failing import test** in an existing correlation test file or new `tests/test_correlation_narrative_module.py`:

```python
def test_narrative_module_importable():
    from correlation.narrative import __doc__  # or a known exported symbol
    assert __doc__
```

Run: `cd backend && pytest tests/test_correlation_narrative_module.py -q` → FAIL until rename.

- [x] **Step 3: Rename + update imports; leave thin re-export only if needed for one release — prefer hard cut with green tests.**

- [x] **Step 4: Run correlation-related tests + commit**

```bash
cd backend && pytest tests/ -q -k correlation
git add -A backend/correlation backend/tests
git commit -m "refactor: rename correlation.copy to narrative (F1.10)"
```

---

### Task 3: W1 — F1.8 AGENTS thin pointer; F1.9 config headers; F1.7 index labels

**Files:**
- Modify: `AGENTS.md` (pointer to `CLAUDE.md` for rules; keep Cursor-cloud section if required)
- Modify: `backend/settings.py`, `config_schema.py`, `operator_settings.py`, `db/config.py`, `routers/config.py` — one-line ownership docstring each
- Modify: `docs/index.md` — authoritative vs snapshot labels

- [x] **Step 1: Document ownership table in HANDOVER or index for the five config modules (no key overlap claim without `rg` evidence).**

- [x] **Step 2: Apply docstring headers stating single responsibility.**

- [x] **Step 3: Make `AGENTS.md` point to `CLAUDE.md` for the rulebook; keep cloud-specific instructions in AGENTS if that is the Cursor entrypoint — avoid duplicating danger zones.**

- [x] **Step 4: Label docs in `docs/index.md`.**

- [x] **Step 5: Commit**

```bash
git commit -m "docs: AGENTS pointer, config ownership headers, index labels (F1.7–F1.9)"
```

---

### Task 4: W1 — F1.6 swallowed-exception triage (batch 1)

**Files:**
- Modify: highest-risk `except Exception: pass/continue` sites in non-test backend (start with scoring/feeds/scheduler paths found by grep)
- Test: ensure no behavior change beyond logging

- [x] **Step 1: Inventory**

```bash
rg -n "except Exception" backend --glob '!tests/**' -A1 | rg -n "pass|continue" 
```

- [x] **Step 2: For each site in batch 1: narrow type where safe; add `logger.warning(..., exc_info=True)` with context; never log secrets.

- [x] **Step 3: Run nearby tests; commit**

```bash
git commit -m "fix: log swallowed exceptions batch 1 (F1.6)"
```

---

### Task 5: W2 — Guard tests for backend-only Threat + KEV floor semantics

**Files:**
- Test: `backend/tests/test_threat_score.py` (extend)
- Test: new or extend wallboard tests under `backend/tests/`

**Interfaces:**
- Consumes: `calculate_threat_score`, `derive_operational_priority`
- Produces: failing tests that encode W2 contracts before code changes

- [x] **Step 1: Write failing tests**

```python
def test_vulncheck_only_does_not_apply_kev_floor():
    cve = {"is_kev": False, "is_vulncheck_exploited": True, "epss_score": 0.01, "cvss_score": 5.0}
    threat = calculate_threat_score(cve, momentum_score=0.0)
    assert threat["score"] < 80  # no CISA floor


def test_cisa_kev_applies_floor():
    cve = {"is_kev": True, "kev_date_added": "2026-07-01", "epss_score": 0.01, "cvss_score": 5.0}
    threat = calculate_threat_score(cve, momentum_score=0.0)
    assert threat["score"] >= 80
```

- [x] **Step 2: Run — confirm CISA case already passes; VulnCheck case must pass (fix threat.py if floor wrongly applied).**

```bash
cd backend && pytest tests/test_threat_score.py -q
```

- [x] **Step 3: Commit tests**

```bash
git commit -m "test: CISA vs VulnCheck KEV floor contract (W2)"
```

---

### Task 6: W2 — Wallboard ranks by OP then Threat

**Files:**
- Modify: `backend/wallboard/service.py` (`_top_risk_tile`)
- Test: wallboard unit/integration test

**Interfaces:**
- Consumes: `calculate_threat_score`, `classify_environment`, `derive_operational_priority`
- Produces: `top_risk.items[]` with `threat_score`, `op_band` (and optionally keep `risk_score` as Threat for API compat — prefer rename carefully with PRODUCT_STATUS note)

- [x] **Step 1: Failing test** — two CVEs where legacy v1.1b order ≠ Threat/OP order; assert new sort key.

- [x] **Step 2: Replace `calculate_risk_score` ranking with:**

```python
from scoring.threat import calculate_threat_score
from scoring.environment import classify_environment
from scoring.priority import derive_operational_priority, PRIORITY_RANK

threat = calculate_threat_score(cve, momentum_score=mom)
env = classify_environment(cve, profile=None)
op = derive_operational_priority(threat["band"], env["tier"], corr_escalation=False)
# sort by (PRIORITY_RANK[op["band"]], -threat["score"])
```

- [x] **Step 3: Update API_REFERENCE / PRODUCT_STATUS for wallboard payload fields.**

- [x] **Step 4: Commit**

```bash
git commit -m "fix(wallboard): rank top risk by OP then Threat (W2)"
```

---

### Task 7: W2 — FE display-only (remove live Threat recalculation path)

**Files:**
- Modify: `frontend/src/scoring/riskScore.js`
- Modify: `frontend/src/scoring/riskScore.test.js` — parity tests must call backend fixtures OR document that FE helpers are display-only and move parity to backend
- Modify: `DetailDrawer/index.jsx` / `OverviewTab.jsx` if they call `calculateThreatScore`

**Interfaces:**
- Consumes: `/risk` response `threat`, `environment`, `operational_priority`
- Produces: no UI path that recomputes Threat for display

- [x] **Step 1: Inventory callers**

```bash
rg -n "calculateThreatScore" frontend/src
```

- [x] **Step 2: Change tests** so S1/S4 assertions use frozen JSON fixtures matching backend `calculate_threat_score` output (checked into `frontend/src/scoring/fixtures/` or generated once). Remove dependency on live FE formula for product truth.

- [x] **Step 3: Deprecate or delete `calculateThreatScore` export; keep `buildRiskHeroSummary`, colors, `applyCorrelationEscalationToRiskScore` until escalation moves server-side.

- [x] **Step 4: `npm run test:unit && npm run build`**

- [x] **Step 5: Docs + HANDOVER + graphify attempt; commit**

```bash
git commit -m "fix(ui): scoring display-only; stop FE Threat recompute (W2/F1.3)"
```

---

### Task 8: W2 — Correlation escalation contract

**Files:**
- Prefer: move `correlation_escalation` application into `POST /risk` when correlation snapshot is cheap/available
- Else: document in SYSTEM_DESIGN that FE merge is temporary; add test that FE `applyCorrelationEscalationToRiskScore` matches `derive_operational_priority(..., corr_escalation=True)`

- [x] **Step 1: Choose backend path if `CORRELATION_PRECOMPUTE` or cached correlation exists for CVE; else keep FE merge.**

- [x] **Step 2: Add parity test FE vs backend escalation helper.**

- [x] **Step 3: Commit + docs.**

---

### Task 9: W2 PR closeout

- [x] **Step 1: `./scripts/verify-local.sh`**
- [ ] **Step 2: Push PR; Gemini disposition; merge** (parent opens PR / merges — this wave pushes branch only)
- [x] **Step 3: Study-guide/learn regen if Overview scoring chapter mentions FE scoring** — skipped (operator docs only; no taught chapter source requiring regen)

```bash
python3 scripts/build_study_guide_book.py
python3 scripts/build_learn_site.py
```

---

### Task 10: W3 — EPSS OP escalation tests (RED)

**Files:**
- Modify: `backend/tests/test_operational_priority.py`
- Modify: `backend/scoring/priority.py`

**Interfaces:**
- Extends: `derive_operational_priority(threat_band, env_tier, corr_escalation=False, *, epss=None, epss_delta=None)`
- Or pass a small `signals: dict` to avoid signature sprawl

Recommended signature:

```python
def derive_operational_priority(
    threat_band: str,
    env_tier: str,
    corr_escalation: bool = False,
    *,
    epss: float | None = None,
    epss_rising: bool = False,
) -> dict[str, Any]:
```

- [x] **Step 1: Failing tests**

```python
def test_epss_ge_half_escalates_med_possible():
    op = derive_operational_priority("MED", "POSSIBLE", epss=0.55)
    assert op["band"] == "P2"  # was P3 in base table
    assert "EPSS" in op["rationale"]


def test_kev_crit_unknown_unchanged_by_low_epss():
    op = derive_operational_priority("CRIT", "UNKNOWN", epss=0.01)
    assert op["band"] == "P1"
```

- [x] **Step 2: Run RED**

```bash
cd backend && pytest tests/test_operational_priority.py::test_epss_ge_half_escalates_med_possible -q
```

Expected: FAIL

- [x] **Step 3: Implement additive escalation after base table + before/after corr bump; never escalate past P1; never change Threat.**

- [x] **Step 4: Wire `epss` / rising from `cves.py` `/risk` handler using CVE epss + momentum signals.**

- [x] **Step 5: Docs (API_REFERENCE, ADR-002 addendum), graphify, commit, PR, merge.**
  (GRAPHIFY_MISSING on this agent; PR/merge left to maintainer — branch pushed only.)

---

### Task 11: W4 — SSVC annotation module (TDD)

**Files:**
- Create: `backend/scoring/ssvc.py`
- Test: `backend/tests/test_ssvc.py`
- Modify: `backend/routers/cves.py` risk response
- Modify: OverviewTab for SSVC chip

**Interfaces:**

```python
def calculate_ssvc_outcome(
    *,
    threat: dict,
    environment: dict,
    cve: dict,
    internet_facing: bool | None = None,
    criticality: str | None = None,
) -> dict:
    """Return {version, outcome, factors, path} — Act|Attend|Track*|Track."""
```

- [x] **Step 1: Failing tests for mapping** — CISA KEV + CONFIRMED → Act; LOW + NO_MATCH → Track; document factor extraction from Threat components (Active/PoC/None).

- [x] **Step 2: Implement deterministic tree; **do not** mutate Threat or replace OP.

- [x] **Step 3: Add `ssvc` key to `/risk` JSON.**

- [x] **Step 4: UI chip beside OP; tooltip with path/factors.**

- [x] **Step 5: Docs crosswalk P↔SSVC; study-guide regen; graphify; PR; merge.**
  (Docs + ADR-002 addendum done this PR. GRAPHIFY_MISSING — CLI not on PATH / no `graphify-out/`. Study-guide regen skipped — no taught chapter source text change beyond operator docs. Push branch only per wave instructions; no PR/merge in this agent turn.)

---

### Task 12: W5 — Profile exposure/criticality flags

**Files:**
- Schema/prefs: wherever My Stack / asset profile JSON is defined (`user_preferences`, asset wizard)
- Modify: `classify_environment` evidence labels (optional) and `derive_operational_priority` / `calculate_ssvc_outcome` modifiers
- Migration only if new DB columns required — prefer JSON profile fields first (no migration)

**Interfaces:**
- Profile may include: `internet_facing: bool`, `criticality: "MISSION_CRITICAL"|"IMPORTANT"|"SUPPORTING"|null`, optional `privileged_service`, `ot_safety`

- [x] **Step 1: Failing OP tests** — CISA KEV + internet_facing + env not NO_MATCH prefers P1 when applicable per design table cells written into the test.

- [x] **Step 2: Thread flags from risk request body profile into OP/SSVC.**

- [x] **Step 3: Asset wizard UI: optional toggles (design-system tokens; Radix Switch/Checkbox).**

- [x] **Step 4: Docs + graphify + PR + merge.**
  (Docs + ADR-002 W5 addendum + sprint tick this PR. GRAPHIFY_MISSING — CLI not on PATH / no `graphify-out/`. Push branch only per wave instructions; no PR/merge and no W6 in this agent turn.)

---

### Task 13: W6 — Lint gate (F1.1)

**Files:**
- Create: `backend/pyproject.toml` (ruff), `frontend/eslint.config.js`, prettier config
- Modify: CI / `verify-local.sh`
- **PR A:** format-only (`ruff format`, prettier) — no behavior
- **PR B:** enable `--check` gates

- [x] **Step 1: Add tool configs with agreed selects; ignore tests secrets rules as in audit sketch.**
  Config select `E,F,I,B,UP`; initial gate uses `--select F,E9`. ESLint scoped to
  `src/scoring/**` + `src/pages/admin/**`.

- [ ] **Step 2: Format-only PR; verify `git diff -w` behavior unchanged for logic.**
  **Deferred** — full-repo `ruff format` / prettier would be a noise bomb; follow-on PR.

- [x] **Step 3: Gate PR: `ruff check` (F,E9), `npm run lint` (scoped) in verify-local.**
  `ruff format --check` + `npm run format:check` **deferred** with Step 2.

- [ ] **Step 4: Merge both; pyright non-blocking optional.**
  (Push-only this wave; no PR/merge in-agent. pyright still optional.)

---

### Task 14: W7 — Split `admin.py` / `cves.py`; FE component extracts (F1.2 / F1.5)

**Files:**
- Create: `backend/routers/admin/` package modules by concern
- Split: `backend/routers/cves/` for existing sub-routers
- FE: extract hooks from largest drawers incrementally (one component family per commit)

- [x] **Step 1: Capture OpenAPI paths dump before.**

```bash
# from running app or TestClient
python -c "..."  # dump route list to /tmp/routes-before.txt
```

- [x] **Step 2: Mechanical move; `admin/__init__.py` re-exports aggregate router; main.py import unchanged.**

- [x] **Step 3: Diff routes after — must be identical.**

- [ ] **Step 4: FE extracts with visual parity; `npm run build`.** *(deferred — F1.5 not in this PR)*

- [x] **Step 5: Commit/PR per package boundary if needed.** *(admin package on `cursor/phase1-w7-router-split-91c2`; CVE package deferred)*

---

### Task 15: W8 — Dual SQL ratchet (F1.4)

**Files:**
- Create: `backend/tests/test_sql_dialect_pairs.py`
- Doc: CI dialect matrix note in PRODUCT_STATUS or POSTGRES.md

- [x] **Step 1: Failing test that every `_PG` constant in `backend/db/` has sibling `_SQLITE` or `# pg-only` marker.**

- [x] **Step 2: Implement scanner; commit baseline count as upper bound comment.**

- [x] **Step 3: Land on branch (PR optional). Testcontainers default = out of Phase 1 closeout.**

---

### Task 16: Program closeout

- [x] **Step 1: Tick all Phase 1 / scoring checkboxes in SPRINT + HANDOVER “program complete” entry.**
- [x] **Step 2: Final `graphify update .` if CLI available; final study-guide/learn if any drift.** *(GRAPHIFY_MISSING — CLI still absent; study-guide not regenerated — operator docs updated per wave)*
- [x] **Step 3: Confirm success criteria from design §9.** *(Met for in-scope waves; deferred: CVE package split, FE F1.5 extracts, full ruff format, Testcontainers)*

---

## Self-review (plan)

1. **Spec coverage:** W0–W8, F1.1–F1.11, scoring A/B tracks, docs/graphify, out-of-scope — mapped to tasks.
2. **Placeholders:** None intentional; W7 OpenAPI dump command left as agent-local but acceptance is identity diff.
3. **Type consistency:** `derive_operational_priority` gains optional `epss`/`epss_rising`; SSVC `calculate_ssvc_outcome`; wallboard sort uses OP then Threat.
4. **graphify:** CLI often missing in cloud — plan requires attempt + honest HANDOVER note; refresh `graphify-out` when tool present.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-20-phase1-scoring-debt.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  

**2. Inline Execution** — execute tasks in this session with executing-plans checkpoints  

**Which approach?**
