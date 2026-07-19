# Engineering Audit Refresh (Delta + Thermo-Nuclear) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks 2–7 are independent and MAY be dispatched in parallel via `dispatching-parallel-agents` after Task 1 completes.

**Goal:** Refresh every `docs/audit/` finding against current `main` with fresh evidence, thermo-nuclear depth, rescored phases, and Resolved appendices — docs only, no product code changes.

**Architecture:** Pin a refresh SHA, then run six parallel domain agents (Phases 1–10 + idempotency). Coordinator merges placeholder new IDs, rewrites Phase 11 / README / progress, and gates on a completeness script checklist before PR update.

**Tech Stack:** Markdown audit corpus in `docs/audit/`; git evidence; graphify for orientation; parallel explore/generalPurpose agents; no application runtime changes.

## Global Constraints

- **Docs only:** modify `docs/audit/**` and (if needed) `docs/superpowers/**` + a short `docs/HANDOVER.md` note. Never edit `backend/`, `frontend/`, `deploy/`, CI, or dependencies.
- **Delta refresh:** keep finding IDs; do not blank-page rewrite narratives.
- **Closed findings:** move to `## Resolved since last audit` appendix; remove from main Findings list.
- **New findings:** only high-conviction thermo-nuclear/structural gaps; agents use `NEW-A`/`NEW-B` placeholders; coordinator assigns final `F{n}.{k}` IDs.
- **Status tags:** each open finding title includes `· Status: OPEN|UPDATED|NEW`.
- **Evidence on HEAD:** re-measure locations/line counts/commands at the pinned SHA.
- **Composer-executable format:** Location · Description · Why · Evidence · Risk · Priority · Recommended solution (code sketch) · Acceptance criteria · Effort · Quick Win vs Architectural.
- **Thermo-nuclear bar:** code-judo, ~1k LOC smell, no spaghetti growth, right-layer logic; prefer few high-conviction news over nit lists.
- **Branch:** `cursor/audit-refresh-91c2` (already exists). Base: `main`.
- **Design SSOT:** `docs/superpowers/specs/2026-07-19-audit-refresh-design.md`.
- **Graphify first** before broad Grep/Read exploration in every agent prompt.

## File map

| Path | Role |
|------|------|
| `docs/audit/PHASE_01_repo_code_debt.md` … `PHASE_10_*.md` | Per-phase findings (refresh) |
| `docs/audit/PHASE_11_readiness.md` | Capstone synthesis (coordinator rewrite) |
| `docs/audit/IDEMPOTENCY_AUDIT.md` | Idempotency findings (align with IDEM-* landings) |
| `docs/audit/README.md` | Index + scorecard |
| `docs/audit/_AUDIT_PROGRESS.md` | Refresh ledger / resume state |
| `docs/superpowers/specs/2026-07-19-audit-refresh-design.md` | Design (done) |
| `docs/superpowers/plans/2026-07-19-audit-refresh.md` | This plan |
| `docs/HANDOVER.md` | One short entry after refresh lands |

## Prior finding ID inventory (must all be classified)

| Doc | IDs |
|-----|-----|
| Phase 1 | F1.1–F1.11 |
| Phase 2 | F2.1–F2.10 |
| Phase 3 | F3.1–F3.9 |
| Phase 4 | F4.1–F4.8 |
| Phase 5 | F5.1–F5.11 |
| Phase 6 | F6.1–F6.7 |
| Phase 7 | F7.1–F7.8 |
| Phase 8 | F8.1–F8.7 |
| Phase 9 | F9.1–F9.6 |
| Phase 10 | F10.1–F10.7 |
| Idempotency | IDEM-A…F (A–D already marked resolved in doc; re-verify) |

## Likely-closed candidates (verify; do not assume)

- **F10.1** — license contradiction: commit `d015d1f9` flipped to Business Source License 1.1; re-grep AGPL/proprietary claims.
- **IDEM-A…D** — commits `89e8ee1c`, `1dfbad9f` (+ related); confirm code matches RESOLVED claims.
- **F10.3 / F10.4** — version framing may have moved; re-check README / version files.
- Anything else closed only with commit/path evidence.

## Shared verification helper (run after each phase task)

```bash
# From repo root. Replace PHASE and expected ID list.
DOC=docs/audit/PHASE_01_repo_code_debt.md
SHA=$(git rev-parse HEAD)
rg -n '^### F1\.' "$DOC"
rg -n 'Resolved since last audit' "$DOC"
rg -n 'Overall Score' "$DOC"
rg -n 'Status: (OPEN|UPDATED|NEW)' "$DOC"
# Completeness: every prior ID appears either as ### F1.x heading OR inside Resolved appendix
python3 - <<'PY'
import re,sys
from pathlib import Path
doc=Path("docs/audit/PHASE_01_repo_code_debt.md").read_text()
prior={f"F1.{i}" for i in range(1,12)}
open_ids=set(re.findall(r'^### (F1\.\d+)\b', doc, re.M))
# appendix mentions
resolved=set(re.findall(r'\b(F1\.\d+)\b', doc.split('Resolved since last audit')[-1])) if 'Resolved since last audit' in doc else set()
missing=prior-open_ids-resolved
extra_open=open_ids-prior  # new findings OK if NEW
print("SHA check header mentions:", SHA[:12] in doc or "Reviewed at" in doc[:800])
print("missing classification:", sorted(missing))
print("open:", sorted(open_ids))
print("resolved-mentioned:", sorted(resolved & prior))
assert not missing, missing
print("OK")
PY
```

Adapt `PHASE_0N` / `F{n}` / prior set per task. Expected: `OK` and no missing IDs.

---

### Task 1: Pin refresh baseline + progress scaffolding

**Files:**
- Modify: `docs/audit/_AUDIT_PROGRESS.md`
- Modify: `docs/audit/README.md` (add refresh banner only; full scorecard in Task 9)

**Interfaces:**
- Consumes: design decisions; `git rev-parse origin/main`
- Produces: pinned `REFRESH_SHA` written into `_AUDIT_PROGRESS.md`; agents must quote this SHA

- [ ] **Step 1: Fetch and pin SHA**

```bash
cd /workspace
git fetch origin main
git merge-base --is-ancestor HEAD origin/main || git rebase origin/main
REFRESH_SHA=$(git rev-parse origin/main)
echo "$REFRESH_SHA" | tee /tmp/audit-refresh-sha.txt
git rev-parse --short "$REFRESH_SHA"
```

Expected: a 40-char SHA printed; working tree on `cursor/audit-refresh-91c2`.

- [ ] **Step 2: Update `_AUDIT_PROGRESS.md` with refresh section**

At the top (after title), insert a section that includes exactly:

```markdown
## 2026-07-19 refresh (delta + thermo-nuclear)

- **Mode:** delta refresh of same finding IDs; Resolved appendix for closed; NEW IDs for thermo-nuclear gaps only.
- **Implementation:** docs only — no product code changes.
- **Pinned SHA:** `<REFRESH_SHA from Step 1>`
- **Prior baseline:** `61c686f` (2026-07-17 original audit).
- **Branch / PR:** `cursor/audit-refresh-91c2` / #695
- **Agent wave status:**

| Agent | Scope | Status |
|-------|-------|--------|
| A1 | Phase 1 + 2 | ⬜ |
| A2 | Phase 3 + IDEMPOTENCY | ⬜ |
| A3 | Phase 4 + 9 | ⬜ |
| A4 | Phase 5 + 6 | ⬜ |
| A5 | Phase 7 + 8 | ⬜ |
| A6 | Phase 10 | ⬜ |
| Synth | Phase 11 + README | ⬜ |
```

Keep the historical §0–§7 content below; do not delete the original ledger — mark it `## Original 2026-07-17 audit (historical)`.

- [ ] **Step 3: Add README refresh banner**

At top of `docs/audit/README.md`, after the H1, add:

```markdown
> **2026-07-19 refresh** against `main` @ `<short SHA>`. Same finding IDs; closed items live in each phase’s **Resolved since last audit** appendix. Scores below are from the refresh (see Phase 11). Docs only — no code fixes in this pass.
```

Leave the phase table scores as-is until Task 9 (or mark “pending refresh”).

- [ ] **Step 4: Commit**

```bash
git add docs/audit/_AUDIT_PROGRESS.md docs/audit/README.md
git commit -m "docs(audit): pin 2026-07-19 refresh baseline and progress ledger"
git push -u origin cursor/audit-refresh-91c2
```

---

### Task 2: Agent A1 — Phase 1 + Phase 2 (thermo-nuclear heavy)

**Files:**
- Modify: `docs/audit/PHASE_01_repo_code_debt.md`
- Modify: `docs/audit/PHASE_02_architecture.md`
- Modify: `docs/audit/_AUDIT_PROGRESS.md` (flip A1 → ✅)

**Interfaces:**
- Consumes: pinned `REFRESH_SHA`; prior IDs F1.1–F1.11, F2.1–F2.10
- Produces: refreshed phase docs; status table; proposed scores; `NEW-A…` placeholders if needed

- [ ] **Step 1: Dispatch / execute with this prompt (paste verbatim to subagent)**

```text
You are refreshing BRIEFR engineering audit docs. DO NOT change product code.

MANDATORY: run `graphify query "repository code quality god files architecture dual dialect"` before broad exploration.
Read docs/superpowers/specs/2026-07-19-audit-refresh-design.md and the thermo-nuclear code-quality bar (code-judo, 1k LOC, spaghetti, right-layer).

Pinned SHA: <REFRESH_SHA>
Files to update:
- docs/audit/PHASE_01_repo_code_debt.md (IDs F1.1–F1.11)
- docs/audit/PHASE_02_architecture.md (IDs F2.1–F2.10)

For EACH prior ID:
1) Re-verify on HEAD with concrete evidence (wc -l, rg counts, file:line).
2) OPEN or UPDATED → keep in Findings with Status tag; refresh Location/Evidence/Remediation.
3) CLOSED → move to "## Resolved since last audit" with commit/path evidence; remove from main list.
Deepen structural remediations (esp. god-files, dual-dialect, dual scoring, App.jsx state).
Add NEW findings only for high-conviction thermo-nuclear gaps; label ### NEW-A —, ### NEW-B —.
Refresh Executive Summary, Overall Score /10, Strengths, Weaknesses, Immediate Actions, Long-Term, Production-Readiness.
Return: status table ID→OPEN|UPDATED|CLOSED|NEW, proposed scores, list of files changed.
```

- [ ] **Step 2: Run completeness check for Phase 1 and 2**

```bash
python3 - <<'PY'
import re
from pathlib import Path

def check(path, prefix, n):
    doc = Path(path).read_text()
    prior = {f"{prefix}.{i}" for i in range(1, n+1)}
    open_ids = set(re.findall(rf'^### ({re.escape(prefix)}\.\d+)\b', doc, re.M))
    parts = doc.split('Resolved since last audit')
    resolved = set(re.findall(rf'\b({re.escape(prefix)}\.\d+)\b', parts[-1])) if len(parts)>1 else set()
    missing = prior - open_ids - resolved
    assert 'Overall Score' in doc
    assert missing == set(), (path, missing)
    print(path, 'OK open', sorted(open_ids), 'resolved', sorted(resolved & prior))

check('docs/audit/PHASE_01_repo_code_debt.md','F1',11)
check('docs/audit/PHASE_02_architecture.md','F2',10)
PY
```

Expected: both print `OK`.

- [ ] **Step 3: Commit**

```bash
git add docs/audit/PHASE_01_repo_code_debt.md docs/audit/PHASE_02_architecture.md docs/audit/_AUDIT_PROGRESS.md
git commit -m "docs(audit): refresh Phase 1–2 findings against current main"
git push origin cursor/audit-refresh-91c2
```

---

### Task 3: Agent A2 — Phase 3 + Idempotency

**Files:**
- Modify: `docs/audit/PHASE_03_engines.md`
- Modify: `docs/audit/IDEMPOTENCY_AUDIT.md`
- Modify: `docs/audit/_AUDIT_PROGRESS.md` (A2 → ✅)

**Interfaces:**
- Consumes: `REFRESH_SHA`; F3.1–F3.9; IDEM-A…F; HANDOVER IDEM fix notes; commits `89e8ee1c`, `1dfbad9f`
- Produces: refreshed engines + idempotency docs; status tables; proposed scores

- [ ] **Step 1: Execute with prompt**

```text
Docs-only audit refresh. graphify first: `graphify query "scheduler locks cache correlation risk scoring idempotency"`.

Pinned SHA: <REFRESH_SHA>
Update:
- docs/audit/PHASE_03_engines.md (F3.1–F3.9)
- docs/audit/IDEMPOTENCY_AUDIT.md (IDEM-A…F)

Re-verify each finding on HEAD. For IDEM-A…D currently marked RESOLVED: confirm code still matches; if yes keep/strengthen Resolved evidence; if regress, reopen as OPEN with RCA.
IDEM-E ACCEPTED / IDEM-F DEFERRED: confirm still accurate; keep disposition explicit.
Thermo-nuclear focus: process-local caches/locks, dual job systems, dual risk scoring (link F1.3/F3.5).
NEW findings only as ### NEW-A — placeholders.
Refresh scores + wrap sections. Return status tables + proposed scores.
```

- [ ] **Step 2: Completeness check**

```bash
python3 - <<'PY'
import re
from pathlib import Path
doc=Path('docs/audit/PHASE_03_engines.md').read_text()
prior={f'F3.{i}' for i in range(1,10)}
open_ids=set(re.findall(r'^### (F3\.\d+)\b', doc, re.M))
resolved=set(re.findall(r'\b(F3\.\d+)\b', doc.split('Resolved since last audit')[-1])) if 'Resolved since last audit' in doc else set()
assert not (prior-open_ids-resolved), prior-open_ids-resolved
idem=Path('docs/audit/IDEMPOTENCY_AUDIT.md').read_text()
for k in 'ABCDEF':
    assert f'IDEM-{k}' in idem
print('OK')
PY
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add docs/audit/PHASE_03_engines.md docs/audit/IDEMPOTENCY_AUDIT.md docs/audit/_AUDIT_PROGRESS.md
git commit -m "docs(audit): refresh Phase 3 engines + idempotency audit"
git push origin cursor/audit-refresh-91c2
```

---

### Task 4: Agent A3 — Phase 4 + Phase 9

**Files:**
- Modify: `docs/audit/PHASE_04_testing.md`
- Modify: `docs/audit/PHASE_09_reliability.md`
- Modify: `docs/audit/_AUDIT_PROGRESS.md`

**Interfaces:**
- Consumes: `REFRESH_SHA`; F4.1–F4.8; F9.1–F9.6; `.github/workflows/*`; `scripts/verify-local.sh`
- Produces: refreshed testing + reliability docs

- [ ] **Step 1: Execute with prompt**

```text
Docs-only. graphify: `graphify query "CI pytest playwright coverage reliability chaos"`.
Pinned SHA: <REFRESH_SHA>
Update PHASE_04_testing.md (F4.1–F4.8) and PHASE_09_reliability.md (F9.1–F9.6).
Re-verify CI baseline claims against current workflows and any known-red notes in CLAUDE.md/HANDOVER — do not greenwash; evidence only.
Classify each ID OPEN/UPDATED/CLOSED; appendix for closed; NEW-A placeholders only if structural gaps.
Rescore both phases. Return status tables.
```

- [ ] **Step 2: Completeness check**

```bash
python3 - <<'PY'
import re
from pathlib import Path

def check(path, prefix, n):
    doc=Path(path).read_text()
    prior={f'{prefix}.{i}' for i in range(1,n+1)}
    open_ids=set(re.findall(rf'^### ({re.escape(prefix)}\.\d+)\b', doc, re.M))
    resolved=set(re.findall(rf'\b({re.escape(prefix)}\.\d+)\b', doc.split('Resolved since last audit')[-1])) if 'Resolved since last audit' in doc else set()
    assert not (prior-open_ids-resolved), (path, prior-open_ids-resolved)
    print(path,'OK')
check('docs/audit/PHASE_04_testing.md','F4',8)
check('docs/audit/PHASE_09_reliability.md','F9',6)
PY
```

- [ ] **Step 3: Commit**

```bash
git add docs/audit/PHASE_04_testing.md docs/audit/PHASE_09_reliability.md docs/audit/_AUDIT_PROGRESS.md
git commit -m "docs(audit): refresh Phase 4 testing + Phase 9 reliability"
git push origin cursor/audit-refresh-91c2
```

---

### Task 5: Agent A4 — Phase 5 + Phase 6

**Files:**
- Modify: `docs/audit/PHASE_05_product_ux.md`
- Modify: `docs/audit/PHASE_06_performance.md`
- Modify: `docs/audit/_AUDIT_PROGRESS.md`

**Interfaces:**
- Consumes: `REFRESH_SHA`; F5.1–F5.11; F6.1–F6.7; `frontend/src/styles/tokens.css`; design-system docs
- Produces: refreshed UX + performance docs

- [ ] **Step 1: Execute with prompt**

```text
Docs-only. graphify: `graphify query "design system tokens AsyncState feed pagination performance pool"`.
Pinned SHA: <REFRESH_SHA>
Update PHASE_05_product_ux.md (F5.1–F5.11) and PHASE_06_performance.md (F6.1–F6.7).
Re-measure evidence (inline style counts, font-size raw vs token, pool settings, OFFSET vs keyset). Respect BRIEFR design-system rules when recommending fixes (tokens, no Tailwind).
Classify OPEN/UPDATED/CLOSED; appendix; NEW-A only for structural UX/perf debt.
Rescore. Return status tables.
```

- [ ] **Step 2: Completeness check**

```bash
python3 - <<'PY'
import re
from pathlib import Path

def check(path, prefix, n):
    doc=Path(path).read_text()
    prior={f'{prefix}.{i}' for i in range(1,n+1)}
    open_ids=set(re.findall(rf'^### ({re.escape(prefix)}\.\d+)\b', doc, re.M))
    resolved=set(re.findall(rf'\b({re.escape(prefix)}\.\d+)\b', doc.split('Resolved since last audit')[-1])) if 'Resolved since last audit' in doc else set()
    assert not (prior-open_ids-resolved), (path, prior-open_ids-resolved)
    print(path,'OK')
check('docs/audit/PHASE_05_product_ux.md','F5',11)
check('docs/audit/PHASE_06_performance.md','F6',7)
PY
```

- [ ] **Step 3: Commit**

```bash
git add docs/audit/PHASE_05_product_ux.md docs/audit/PHASE_06_performance.md docs/audit/_AUDIT_PROGRESS.md
git commit -m "docs(audit): refresh Phase 5 UX + Phase 6 performance"
git push origin cursor/audit-refresh-91c2
```

---

### Task 6: Agent A5 — Phase 7 + Phase 8

**Files:**
- Modify: `docs/audit/PHASE_07_security.md`
- Modify: `docs/audit/PHASE_08_operations.md`
- Modify: `docs/audit/_AUDIT_PROGRESS.md`

**Interfaces:**
- Consumes: `REFRESH_SHA`; F7.1–F7.8; F8.1–F8.7; auth/JWT/rate-limit/metrics/backup paths
- Produces: refreshed security + ops docs

- [ ] **Step 1: Execute with prompt**

```text
Docs-only. graphify: `graphify query "JWT secret rate limit RBAC metrics backup restore deploy"`.
Pinned SHA: <REFRESH_SHA>
Update PHASE_07_security.md (F7.1–F7.8) and PHASE_08_operations.md (F8.1–F8.7).
Re-verify F7.1 fail-closed JWT guard carefully (read actual control flow — systematic RCA before OPEN/CLOSED).
Do not claim CI/dependency-audit green without evidence.
Classify OPEN/UPDATED/CLOSED; appendix; NEW-A for structural security/ops gaps only.
Rescore. Return status tables.
```

- [ ] **Step 2: Completeness check**

```bash
python3 - <<'PY'
import re
from pathlib import Path

def check(path, prefix, n):
    doc=Path(path).read_text()
    prior={f'{prefix}.{i}' for i in range(1,n+1)}
    open_ids=set(re.findall(rf'^### ({re.escape(prefix)}\.\d+)\b', doc, re.M))
    resolved=set(re.findall(rf'\b({re.escape(prefix)}\.\d+)\b', doc.split('Resolved since last audit')[-1])) if 'Resolved since last audit' in doc else set()
    assert not (prior-open_ids-resolved), (path, prior-open_ids-resolved)
    print(path,'OK')
check('docs/audit/PHASE_07_security.md','F7',8)
check('docs/audit/PHASE_08_operations.md','F8',7)
PY
```

- [ ] **Step 3: Commit**

```bash
git add docs/audit/PHASE_07_security.md docs/audit/PHASE_08_operations.md docs/audit/_AUDIT_PROGRESS.md
git commit -m "docs(audit): refresh Phase 7 security + Phase 8 operations"
git push origin cursor/audit-refresh-91c2
```

---

### Task 7: Agent A6 — Phase 10 documentation

**Files:**
- Modify: `docs/audit/PHASE_10_documentation.md`
- Modify: `docs/audit/_AUDIT_PROGRESS.md`

**Interfaces:**
- Consumes: `REFRESH_SHA`; F10.1–F10.7; LICENSE; README; `docs/API_REFERENCE.md`; study-guide/learn recent work (docs quality context only)
- Produces: refreshed Phase 10

- [ ] **Step 1: Execute with prompt**

```text
Docs-only. graphify: `graphify query "license API reference version documentation PRODUCT_STATUS"`.
Pinned SHA: <REFRESH_SHA>
Update docs/audit/PHASE_10_documentation.md (F10.1–F10.7).
Especially re-verify F10.1 against LICENSE + repo grep after BSL flip (commit d015d1f9). Re-check README version framing (F10.3) and version SSOT (F10.4).
Classify OPEN/UPDATED/CLOSED; appendix; NEW-A only if needed.
Rescore. Return status table.
```

- [ ] **Step 2: Completeness check**

```bash
python3 - <<'PY'
import re
from pathlib import Path
doc=Path('docs/audit/PHASE_10_documentation.md').read_text()
prior={f'F10.{i}' for i in range(1,8)}
open_ids=set(re.findall(r'^### (F10\.\d+)\b', doc, re.M))
resolved=set(re.findall(r'\b(F10\.\d+)\b', doc.split('Resolved since last audit')[-1])) if 'Resolved since last audit' in doc else set()
assert not (prior-open_ids-resolved), prior-open_ids-resolved
print('OK', sorted(open_ids), sorted(resolved&prior))
PY
```

- [ ] **Step 3: Commit**

```bash
git add docs/audit/PHASE_10_documentation.md docs/audit/_AUDIT_PROGRESS.md
git commit -m "docs(audit): refresh Phase 10 documentation findings"
git push origin cursor/audit-refresh-91c2
```

---

### Task 8: Coordinator synthesis — Phase 11

**Files:**
- Modify: `docs/audit/PHASE_11_readiness.md`
- Modify: `docs/audit/_AUDIT_PROGRESS.md` (Synth partial)

**Interfaces:**
- Consumes: all refreshed phase scores + open finding IDs from Tasks 2–7; assigns final IDs for any `NEW-*` placeholders still present
- Produces: Phase 11 scorecard, themes T1…, P0/P1/P2 lists from **open** findings only

- [ ] **Step 1: Collect open Critical/High findings**

```bash
rg -n 'Status: (OPEN|UPDATED|NEW).*Priority: (CRITICAL|HIGH)|Priority: (CRITICAL|HIGH).*Status: (OPEN|UPDATED|NEW)|^### F[0-9]+\.[0-9]+.*Priority: (CRITICAL|HIGH)' docs/audit/PHASE_0{1,2,3,4,5,6,7,8,9}*.md docs/audit/PHASE_10_documentation.md | head -n 200
rg -n '^### NEW-' docs/audit/PHASE_*.md docs/audit/IDEMPOTENCY_AUDIT.md
```

- [ ] **Step 2: Assign final IDs for NEW placeholders**

For each `### NEW-X` in a phase file, rename to next free `F{n}.{k}` in that phase (e.g. Phase 1 next is F1.12). Update any cross-references in the same commit.

- [ ] **Step 3: Rewrite Phase 11**

Update `docs/audit/PHASE_11_readiness.md`:

1. Header: reviewed at `REFRESH_SHA`; note 2026-07-19 refresh consolidating refreshed Phases 1–10.
2. Executive Summary reflecting closed vs still-open P0s.
3. Consolidated scorecard table with **new** phase scores.
4. Cross-cutting themes (update T1–T5; add/remove only with evidence).
5. Release-readiness gate: P0/P1/P2 lists citing **current open** IDs only (do not list resolved F10.1 etc. as blockers if closed).
6. Production / Release verdicts rescored (self-hosted + SaaS lenses).

Do not invent new product work; synthesize only.

- [ ] **Step 4: Completeness — Phase 11 cites only open IDs as blockers**

```bash
python3 - <<'PY'
from pathlib import Path
import re
p11=Path('docs/audit/PHASE_11_readiness.md').read_text()
assert '2026-07-19' in p11 or 'refresh' in p11.lower()
assert 'Overall Program Score' in p11 or 'Program Score' in p11
assert 'P0' in p11 and 'P1' in p11
print('Phase11 structure OK')
PY
```

- [ ] **Step 5: Commit**

```bash
git add docs/audit/PHASE_11_readiness.md docs/audit/PHASE_*.md docs/audit/_AUDIT_PROGRESS.md
git commit -m "docs(audit): synthesize Phase 11 readiness from refreshed findings"
git push origin cursor/audit-refresh-91c2
```

---

### Task 9: README scorecard + progress closeout + HANDOVER

**Files:**
- Modify: `docs/audit/README.md`
- Modify: `docs/audit/_AUDIT_PROGRESS.md`
- Modify: `docs/HANDOVER.md`

**Interfaces:**
- Consumes: Phase 11 scorecard
- Produces: README scores match Phase 11; progress all ✅; HANDOVER entry

- [ ] **Step 1: Sync README scores from Phase 11 table**

Copy the phase score numbers and program score into `docs/audit/README.md`. Keep the phase index links. Keep the refresh banner from Task 1 with final short SHA.

- [ ] **Step 2: Mark all agent rows ✅ in `_AUDIT_PROGRESS.md`**

Set every Agent wave Status cell to ✅ and add:

```markdown
### Refresh complete
- All prior finding IDs classified.
- Phase scores rescored; Phase 11 P0 list updated.
- Docs only — no product code changed in this PR.
```

- [ ] **Step 3: Prepend HANDOVER entry**

```markdown
## 2026-07-19 — Engineering audit refresh (docs only)

**Done**
- Delta-refreshed `docs/audit/` against main @ `<short SHA>` (same finding IDs; Resolved appendices; thermo-nuclear NEW findings where warranted).
- Rescored phases; Phase 11 P0/P1/P2 updated from open set.
- Design: `docs/superpowers/specs/2026-07-19-audit-refresh-design.md`
- Plan: `docs/superpowers/plans/2026-07-19-audit-refresh.md`
- PR: #695

**Next:** execute P0 fixes from refreshed Phase 11 (separate PRs); do not treat this docs PR as implementation.
```

- [ ] **Step 4: Diff gate — docs only**

```bash
git diff --name-only origin/main...HEAD
# Allowed prefixes only:
git diff --name-only origin/main...HEAD | rg -v '^(docs/audit/|docs/superpowers/|docs/HANDOVER\.md)$' && echo 'FAIL: non-docs paths' || echo 'OK docs-only'
```

Expected: `OK docs-only` (or only those paths listed).

- [ ] **Step 5: Commit + push + update PR**

```bash
git add docs/audit/README.md docs/audit/_AUDIT_PROGRESS.md docs/HANDOVER.md
git commit -m "docs(audit): close out refresh scorecard, progress, HANDOVER"
git push origin cursor/audit-refresh-91c2
```

Update PR #695 body to list final program score and note Resolved highlights (e.g. F10.1 / IDEM-* if closed).

---

### Task 10: Final corpus gate

**Files:**
- Test: verification only (no new files required)

**Interfaces:**
- Consumes: full refreshed corpus
- Produces: pass/fail gate before declaring done

- [ ] **Step 1: Run full ID classification gate**

```bash
python3 - <<'PY'
import re
from pathlib import Path

phases = [
    ('docs/audit/PHASE_01_repo_code_debt.md','F1',11),
    ('docs/audit/PHASE_02_architecture.md','F2',10),
    ('docs/audit/PHASE_03_engines.md','F3',9),
    ('docs/audit/PHASE_04_testing.md','F4',8),
    ('docs/audit/PHASE_05_product_ux.md','F5',11),
    ('docs/audit/PHASE_06_performance.md','F6',7),
    ('docs/audit/PHASE_07_security.md','F7',8),
    ('docs/audit/PHASE_08_operations.md','F8',7),
    ('docs/audit/PHASE_09_reliability.md','F9',6),
    ('docs/audit/PHASE_10_documentation.md','F10',7),
]
failed=False
for path, prefix, n in phases:
    doc=Path(path).read_text()
    prior={f'{prefix}.{i}' for i in range(1,n+1)}
    open_ids=set(re.findall(rf'^### ({re.escape(prefix)}\.\d+)\b', doc, re.M))
    resolved=set(re.findall(rf'\b({re.escape(prefix)}\.\d+)\b', doc.split('Resolved since last audit')[-1])) if 'Resolved since last audit' in doc else set()
    missing=prior-open_ids-resolved
    # open findings should have Status tags
    for m in re.finditer(rf'^### ({re.escape(prefix)}\.\d+).*$', doc, re.M):
        line=m.group(0)
        if 'Status:' not in line:
            print('WARN missing Status tag:', path, m.group(1))
    if missing:
        failed=True
        print('MISSING', path, sorted(missing))
    else:
        print('OK', path)
idem=Path('docs/audit/IDEMPOTENCY_AUDIT.md').read_text()
for k in 'ABCDEF':
    assert f'IDEM-{k}' in idem, k
assert 'NEW-' not in Path('docs/audit').joinpath('PHASE_01_repo_code_debt.md').read_text() or True
left=list(Path('docs/audit').glob('PHASE_*.md'))
for p in left:
    if '### NEW-' in p.read_text():
        failed=True
        print('UNASSIGNED NEW placeholder in', p)
print('FAIL' if failed else 'PASS')
raise SystemExit(1 if failed else 0)
PY
```

Expected: `PASS` exit 0.

- [ ] **Step 2: Confirm no product code in PR diff**

```bash
git diff --name-only origin/main...HEAD | rg -v '^(docs/)' && echo FAIL || echo PASS
```

Expected: `PASS`.

- [ ] **Step 3: Final push if any gate fixes**

```bash
git status -sb
# if fixes: commit "docs(audit): fix refresh gate findings" && push
```

---

## Spec coverage self-check (plan author)

| Spec requirement | Task |
|------------------|------|
| Delta refresh same IDs | 2–7 |
| Resolved appendix | 2–7 |
| NEW thermo-nuclear IDs | 2–7 + final IDs in 8 |
| All 11 phases + idempotency + README + progress | 2–9 |
| Rescore all phases + program | 2–8, 9 |
| Parallel Approach 2 | Tasks 2–7 parallelizable after Task 1 |
| Docs only | Global + Task 9/10 gates |
| Phase 11 P0 from open set | 8 |
| Composer-executable format | agent prompts Tasks 2–7 |
| HANDOVER note | 9 |

## Placeholder scan

No TBD/TODO/“implement later” steps. Commands and prompts are concrete.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-19-audit-refresh.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task (Tasks 2–7 in parallel after Task 1), review between tasks  

**2. Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
