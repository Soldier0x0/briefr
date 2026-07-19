# Engineering Audit Refresh (Delta + Thermo-Nuclear) — Design

**Date:** 2026-07-19  
**Status:** Design approved in brainstorming; awaiting plan + execution  
**Baseline (original audit):** commit `61c686f` / docs landed ~2026-07-17 on `claude/engineering-audit-dzib4j` (PR #661 draft)  
**Refresh against:** current `main` HEAD at branch creation (`ff23c18a` or newer after pull)  
**Branch:** `cursor/audit-refresh-91c2`  
**Deliverable dir:** `docs/audit/`  
**Related skills:** brainstorming → writing-plans; dispatching-parallel-agents; thermo-nuclear-code-quality-review; systematic-debugging (for RCA of “is this finding still true?”)

## 1. Purpose

Re-run the existing 11-phase engineering audit **against current `main`**, deeply and clearly, **without rewriting the corpus from scratch** and **without implementing product fixes**.

Update the same finding IDs with fresh evidence and sharper remediations. Close what is fixed into an appendix. Add new findings only when a thermo-nuclear code-quality bar surfaces high-conviction structural gaps. Rescore every phase and the program total.

## 2. Decisions locked in brainstorming

| Decision | Choice |
|----------|--------|
| Update mode | **Delta refresh** of same issues (not full rewrite of narratives) |
| Closed findings | Move to **“Resolved since last audit”** appendix; keep open list tight |
| New findings | Allowed when thermo-nuclear review finds clear structural gaps; continue numbering (`F{n}.{next}`) |
| Scope | All 11 phase docs + `IDEMPOTENCY_AUDIT.md` + `README.md` + `_AUDIT_PROGRESS.md` |
| Scoring | **Re-score every phase** and the program total from fresh evidence |
| Execution | **Approach 2:** parallel phase agents + coordinator synthesis |
| Implementation | **Docs only** — no product/backend/frontend/deploy code changes |
| Quality bar | Thermo-nuclear: code-judo, ≤1k-line smell, no spaghetti growth, right-layer logic |

## 3. Goals and non-goals

### Goals

1. Every prior finding on HEAD is classified **OPEN**, **UPDATED**, or **CLOSED** (appendix).
2. Evidence, locations (file:line), and remediations are accurate on the pinned refresh SHA.
3. New findings only for high-conviction structural / maintainability gaps (thermo-nuclear).
4. Phase scores + Phase 11 P0/P1/P2 + README scorecard reflect the *current open* set.
5. Documents remain **Composer-executable**: concrete location, remediation sketch, acceptance criteria, effort, Quick Win vs Architectural.
6. Single draft PR, docs-only diff under `docs/audit/` (plus this design/plan under `docs/superpowers/` as needed).

### Non-goals

- Full rewrite of every phase narrative from a blank page.
- Implementing fixes for P0/P1 findings in this PR.
- Merging or superseding historical PR #661 as a code-change vehicle.
- Cosmetic nits, style preferences, or speculative SaaS roadmap as “findings.”
- Changing product runtime behavior, CI config, or dependencies.

## 4. Output contract (per phase file)

Preserve the existing document skeleton. Refresh content in place.

### 4.1 Header

- Pin `Reviewed at commit <SHA>` (refresh baseline).
- Note prior baseline (`61c686f`) and that this is a **2026-07-19 refresh**.

### 4.2 Open findings list

For each still-open prior finding:

- Keep ID (`F1.1`, …).
- Add status tag: `OPEN` or `UPDATED`.
- Refresh **Location**, **Evidence**, **Recommended solution**, **Acceptance criteria** as needed.
- Deepen remediations with thermo-nuclear / code-judo guidance where the issue is structural.
- Do not invent unverified line numbers; re-measure on HEAD.

### 4.3 New findings

- Only when thermo-nuclear review finds clear structural gaps not covered by an existing ID.
- Continue numbering within the phase (`F1.12`, …).
- Tag `NEW`.
- Same mandatory field set as original audit.

### 4.4 Appendix — Resolved since last audit

For each closed prior finding:

- Original ID + title
- Why closed (behavior/path/commit evidence)
- Verification date / SHA

Closed items must leave the main Findings list so the open list stays actionable.

### 4.5 Phase wrap sections (always refresh)

- Executive Summary
- Overall Score /10 (rescored)
- Strengths / Weaknesses
- Immediate Action Items
- Long-Term Recommendations
- Production-Readiness Assessment

### 4.6 Finding field set (mandatory, unchanged)

Title · Location · Description · Why it matters · Evidence · Risk · Priority (Critical/High/Medium/Low) · Recommended solution (with code sketch where useful) · Acceptance criteria · Estimated effort · Quick Win vs Architectural

## 5. Thermo-nuclear review bar

Apply aggressively to Phases 1–3 (debt, architecture, engines) and whenever deepening remediations. Prefer a smaller number of high-conviction findings over long nit lists.

**Must look for:**

0. Code-judo moves that delete layers/branches/helpers rather than rearrange them  
1. Files at or past ~1000 LOC without strong reason to stay monoliths  
2. Spaghetti / special-case branching bolted onto unrelated flows  
3. Design cleanup opportunities that preserve behavior  
4. Magical / thin / wrong-layer abstractions  
5. Dual-maintenance drift and missing canonical helpers  
6. Non-atomic or unnecessarily sequential orchestration where structure is the bug  

**Do not add** low-value cosmetic findings if larger structural issues exist.

## 6. Parallel execution architecture

### 6.1 Agent wave (independent domains)

| Agent | Scope |
|-------|--------|
| A1 | Phase 1 (repo/debt) + Phase 2 (architecture) — thermo-nuclear heavy |
| A2 | Phase 3 (engines) + `IDEMPOTENCY_AUDIT.md` |
| A3 | Phase 4 (testing) + Phase 9 (reliability) |
| A4 | Phase 5 (product/UX) + Phase 6 (performance) |
| A5 | Phase 7 (security) + Phase 8 (operations) |
| A6 | Phase 10 (documentation) |

Each agent receives: prior finding list, format template, pinned HEAD SHA, docs-only constraint, thermo-nuclear rubric, graphify-first exploration rule.

Each agent returns:

- Updated markdown for its files
- Status table: ID → OPEN | UPDATED | CLOSED | NEW
- Proposed phase score(s)
- Placeholder IDs for new findings (`NEW-A`, `NEW-B`, …) to avoid collisions

### 6.2 Coordinator synthesis (serial)

1. Integrate agent outputs; assign final new IDs; resolve duplicate themes.  
2. Rewrite **Phase 11** from open findings only (scorecard, cross-cutting themes, P0/P1/P2).  
3. Update **README.md** index/scores and **`_AUDIT_PROGRESS.md`** with a “2026-07-19 refresh” ledger.  
4. Cross-check likely-closed items against HANDOVER / recent commits (examples: BSL license flip vs F10.1; IDEM-* fixes vs idempotency findings).  
5. Commit/push docs-only; open/update draft PR.

### 6.3 Conflict rules

- Cross-cutting disagreements (e.g. “CI red”) → one coordinator re-check on HEAD → one verdict.  
- Idempotency status must align with landed IDEM-* fix commits; do not leave fixed items open.  
- Agents never edit product code.

## 7. Verification method (per finding)

For each prior finding:

1. **Locate** current code/docs on HEAD (graphify → targeted read/grep).  
2. **Reproduce claim** with evidence (path, command, count, behavior).  
3. If fixed → **CLOSED** + appendix evidence (commit hash and/or path proving fix).  
4. If still true → **OPEN** or **UPDATED**; refresh evidence; deepen remediation if structural.  
5. If partially true → **UPDATED**; state precisely what remains.  

Use systematic-debugging discipline for ambiguous “is it fixed?” cases: no status change without root-cause evidence.

## 8. Scoring

- Rescore each phase 0–10 from **current open** finding severity and density.  
- Phase 11 recomputes weighted **self-hosted** program score and separately states **Enterprise-SaaS** lens score.  
- README scorecard must match Phase 11.  
- Scores are judgments grounded in evidence, not averages of arbitrary weights unless Phase 11 documents the weighting explicitly (preserve prior Phase 11 method: qualitative weighted synthesis with published phase table).

## 9. Delivery

| Item | Value |
|------|--------|
| Branch | `cursor/audit-refresh-91c2` |
| Base | `main` |
| PR | Draft, docs-only |
| Paths | `docs/audit/**` (required); `docs/superpowers/specs/**` and `docs/superpowers/plans/**` for design/plan |
| Title | `docs(audit): refresh 11-phase engineering audit against current main` |

## 10. Success criteria

1. All 11 phases + `IDEMPOTENCY_AUDIT.md` refreshed at the pinned SHA.  
2. Every prior finding is OPEN/UPDATED in the main list **or** in the Resolved appendix.  
3. New findings (if any) are high-conviction, numbered, and fully formatted.  
4. Phase scores + Phase 11 P0/P1/P2 reflect the current open set.  
5. README + `_AUDIT_PROGRESS.md` describe the 2026-07-19 refresh.  
6. Diff contains no product runtime code changes.

## 11. Explicit out of scope for this PR

- Fixing P0/P1 items in application code  
- Greening CI / dependency-audit / gitleaks as code work  
- Merging PR #661  
- Enterprise SaaS multi-tenancy implementation  

## 12. Next step after spec approval

Invoke **writing-plans** to produce `docs/superpowers/plans/2026-07-19-audit-refresh.md` with agent prompts, merge checklist, and verification commands — then execute the plan.
