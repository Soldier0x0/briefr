# Study Guide Truth Hardening + Profile Pathways — Design

**Date:** 2026-07-19  
**Status:** Phase 0 inventory gates (G1–G3, G5) **implemented and green** on this branch; Phase 1 still blocked pending maintainer go-ahead  
**Supersedes for sequencing:** `docs/superpowers/plans/2026-07-19-study-guide-prose-depth.md` (absorbed / deferred non-blocking polish)  
**Related:** `docs/superpowers/specs/2026-07-19-study-guide-audit-design.md` (inventory auditor — necessary but not sufficient)  
**Plan:** `docs/superpowers/plans/2026-07-19-study-guide-truth-hardening.md`

## 1. Purpose

Ship a **fact-accurate** learning corpus for BRIEFR — grounded in what the latest codebase actually does — then (only after that) publish **profile-based pathways** on a docs subdomain.

The maintainer will continue to add features and run independent audits. When they say **“update,”** agents must re-inventory HEAD, close new weak/gap/stale findings, and bring gates green again. Prefer reading every in-scope file over shipping plausible-but-unverified prose.

## 2. Decisions locked in brainstorming

| Decision | Choice |
|----------|--------|
| Docs home job | **Both:** System Design track **and** role tracks, via a chooser |
| v1 role profiles | **Security analyst** + **Security architect** only |
| Repo layout (Phase 1) | **Separate learn/docs repo** that **pulls a truth bundle** from BRIEFR (not a second architecture SSOT) |
| Accuracy bar | **Facts only** — what is present and working on HEAD; no aspirational claims |
| Sequencing | **Phase 0 truth hardening first**; Phase 1 pathways blocked until gates green |
| Recommended build approach | Pathway **overlays** on an audited textbook; inventory/generator as the accuracy engine underneath |

## 3. Goals and non-goals

### Phase 0 goals (this design’s implementation focus)

1. **File completeness** — Every in-scope source file is `covered` (named and explained) or explicit `out_of_scope` with a written reason. Status `weak` (directory-only association) is **not** shippable.
2. **Claim grounding** — Technical prose asserts only behavior that exists on HEAD. When guide and reality disagree: **code → `docs/PRODUCT_STATUS.md` → guide** (fix the guide; log RCA in `STALE_CLAIMS.md` when useful).
3. **Hard ship gates** — Machine-checkable criteria (below) must pass before any Phase 1 work starts.
4. **Re-audit protocol** — Documented, repeatable response when the maintainer says “update” or pastes audit findings after new features.
5. **Keep existing shell** — `docs/STUDY_GUIDE.html` remains editable SSOT; `docs/study-guide/` remains generated.

### Phase 1 goals (designed at high level; implement only after Phase 0 green)

1. Separate public learn/docs repository.
2. Consume a versioned **truth bundle** exported from green BRIEFR audits.
3. Home chooser → System Design pathway **or** Analyst **or** Architect lens.
4. Deploy to `docs.<domain>`.
5. Overlays reorder/reframe facts; they must not invent architecture.

### Non-goals

- Operator / detection-engineer profiles in v1 (later).
- Rewriting product architecture only inside the learn repo.
- Marketing or roadmap-as-fact language in published pathways.
- Hand-editing generated `docs/study-guide/`.
- Auto-publishing profile sites while `weak > 0`, `gap > 0`, or open stale claims remain.
- Mapping every individual `backend/tests/**` file (tests stay aggregate “testing strategy” unless inventory scope is explicitly expanded later).
- Product feature development as part of Phase 0 (docs/auditor/gates only; exception: tiny doc-forced clarifications never prefer inventing product behavior).

## 4. Accuracy bar (non-negotiable)

1. **Inventory** — Walk every in-scope file on HEAD (read modules as needed to describe real behavior).
2. **No weak ship** — `weak` must be driven to **0**, or each leftover row must be an explicit audited `out_of_scope` with reason (e.g. empty `__init__.py` re-export package marker).
3. **No gap ship** — `gap = 0`.
4. **Orphans** — Only intentional, documented historical mentions (today: `backend/db/dialect.py` Post-B deletion, correctly taught).
5. **Claims** — No open “wrong vs code / PRODUCT_STATUS” items in `STALE_CLAIMS.md` at Phase 0 close.
6. **Re-verify on demand** — Maintainer “update” → full re-pass of gates against latest HEAD.

**Important:** Today’s `gap = 0` is **necessary but not sufficient**. Current headline (~441 covered / ~244 weak) is **not** 100% accurate for this bar.

## 5. Architecture — Phase 0 truth pipeline

### Layers

| Layer | Location | Role |
|-------|----------|------|
| Runtime truth | Code on HEAD + `docs/PRODUCT_STATUS.md` | Wins all disputes |
| Editable textbook | `docs/STUDY_GUIDE.html` | Fact prose + Concept/Why/How/Self-check |
| Auditor | `scripts/audit_study_guide.py` | Inventory + classification |
| Reports | `docs/planning/specs/study-guide-audit/` | `inventory.*`, `summary.md`, `STALE_CLAIMS.md`, IR scorecard |
| Generated book | `docs/study-guide/` | Reader multi-file book (regenerate only) |
| Learn repo / `docs.` | Separate (Phase 1) | Pathways; blocked until Phase 0 green |

### Pipeline (every update pass)

```text
HEAD tree
  → inventory every in-scope file
  → classify: covered | weak | gap | out_of_scope | orphan_mention
  → gate: weak=0 (or justified OOS), gap=0; orphans only if documented
  → claim pass: prose vs PRODUCT_STATUS + cited paths must exist
  → rewrite STUDY_GUIDE.html where wrong/thin
  → rebuild book + re-audit until green
```

### Inventory scope (unchanged from audit design unless expanded)

**In scope:** `backend/` (runtime), `frontend/src/`, `deploy/`, load-bearing root scripts already used by the auditor.

**Out of scope categories:** `node_modules/`, `.venv/`, build artifacts, individual test files (aggregate), `docs/archive/`, vendor/minified assets.

## 6. Ship gates (Phase 0 → Phase 1)

| ID | Gate | Pass criteria |
|----|------|----------------|
| G1 | Inventory | `gap = 0` |
| G2 | Depth | `weak = 0` for in-scope files, **or** each remaining row is explicit `out_of_scope` with allowlisted reason in audit output |
| G3 | Orphans | Only documented intentional historical mentions |
| G4 | Claims | No open wrong-vs-truth items in `STALE_CLAIMS.md` |
| G5 | Book | `python scripts/build_study_guide_book.py` succeeds; pages match SSOT; builder + auditor pytest green |

**Phase 1 is forbidden** until G1–G5 pass on the commit that exports the truth bundle.

## 7. Workstreams (Phase 0)

1. **Auditor upgrade** — Fail (or report as ship-blocking) when `weak > 0` under the Phase 0 policy; keep/extend path-existence checks for cited chips; optional helpers for claim grounding.
2. **Weak→covered sweeps** — Directory-by-directory (e.g. `backend/ai/`, `backend/feeds/`, `backend/detection/`, frontend pages/components): name real files in chips/How; read modules when prose is thin.
3. **Claim RCA pass** — Diff guide vs `PRODUCT_STATUS` and code; fix guide; record RCA in `STALE_CLAIMS.md` when behavior changed or a false claim was found.
4. **Update protocol** — Maintainer trigger (“update” and/or pasted audit results) → re-inventory HEAD → close new weak/gap/stale → green G1–G5 again.
5. **Absorbed prose depth** — Interview-depth improvements for short chapters (former prose-depth plan) happen **inside** Phase 0 only insofar as they serve accuracy and covered status; no profile site work.

Many PRs are expected. Prefer small directory sweeps over one mega-diff.

## 8. Re-audit / “update” protocol

When the maintainer adds features, runs external audits, or says **update**:

1. Sync to latest HEAD (and apply any pasted audit findings as input, not as unverified truth).
2. Run `scripts/audit_study_guide.py` (and upgraded ship-gate checks).
3. For each new `gap` / `weak` / stale claim: read the relevant files; update `STUDY_GUIDE.html`; regenerate the book.
4. Resolve G4 items in `STALE_CLAIMS.md` (fix or close with RCA).
5. Stop only when G1–G5 are green.
6. If Phase 1 already exists: export a new truth bundle and refresh the learn repo overlays so pathways do not drift.

Do not leave “known weak” as accepted debt under the Phase 0 bar.

## 9. Phase 1 preview (blocked; not implemented in Phase 0)

### Product shape

- **Repo:** separate public learn/docs repository (name TBD, e.g. `briefr-learn`).
- **Input:** versioned truth bundle produced only from a BRIEFR commit with G1–G5 green.
- **Home:** chooser — System Design | Security analyst | Security architect.
- **Overlays:** pathway ordering, persona framing, “how this persona sees the tool” navigation — all citing bundle facts.
- **Host:** `docs.<domain>`.

### Explicit dependency

No learn-repo scaffolding, no `docs.` deploy pipeline for pathways, and no profile curriculum drafting that invents facts, until Phase 0 closes.

## 10. Testing and verification

- Extend pytest so local/CI verify can fail when G1–G3 regress under Phase 0 policy (exact API to be specified in the implementation plan).
- Keep `backend/tests/test_audit_study_guide.py` and `backend/tests/test_build_study_guide_book.py` green.
- After every content PR: rebuild book + re-run auditor; confirm `gap=0` and weak policy.
- Prefer reading real modules over inventing How text that “sounds right.”

## 11. Risks

| Risk | Mitigation |
|------|------------|
| 244 weak files is large | Sweep by directory; many small PRs; track counts in `summary.md` / HANDOVER |
| Prose invents behavior | Truth order + STALE_CLAIMS + cite real paths only |
| Phase 1 starts early | Hard gate language in HANDOVER + this spec; no learn-repo PRs until G1–G5 |
| Features land mid-hardening | “Update” protocol; re-inventory; do not merge pathways on a stale bundle |
| Empty `__init__.py` noise | Allow explicit `out_of_scope` with reason — still inventoried, not silently weak |

## 12. Success criteria

**Phase 0 done when:** On HEAD, every in-scope file is `covered` or explicit justified `out_of_scope`; `gap=0`; orphans only documented; no open stale claims; book regenerated; maintainer can say “update” after new features and the same gates return to green.

**Phase 1 ready when:** Phase 0 done **and** a truth-bundle export contract exists for the separate learn repo (detailed in a later Phase 1 design/plan).

## 13. Spec self-review

- **Placeholders:** none intentional; learn-repo name left TBD (Phase 1 detail).
- **Consistency:** Phase 0 blocks Phase 1 everywhere; accuracy bar matches brainstorming (facts from HEAD, every file if needed).
- **Scope:** Phase 0 is one implementation track; Phase 1 is preview-only here.
- **Ambiguity:** `weak=0` vs allowlisted `out_of_scope` is explicit; “update” protocol is explicit.
