# Self-stack Risk Register precision — Design

**Date:** 2026-07-21  
**Status:** Approved for planning (brainstorming)  
**Implementation branch (planned):** `cursor/self-stack-precision-91c2`

## 1. Goal

Live Risk Register (“self-exposure”) rows must mean a CVE **plausibly affects a product BRIEFR ships/runs**, preferably at a **pinned version** — not that a dependency name appears as a substring in a CVE description.

**Success criteria:**
- Description-only / fuzzy text matches no longer populate live risk rows by default
- Known false-positive shape (e.g. CVE-2020-0601 CurveBall ↛ PyCA `cryptography`) does not appear
- Product+version-in-range matches still appear, with clear match basis
- Product-only matches (version unknown) appear only as weaker/explicitly labeled rows, not as an undifferentiated CRITICAL inventory
- Overview self-CVE exposure tile counts the filtered set
- Operator-facing copy stops implying SBOM-confirmed hits

## 2. Program sequencing

| Order | Program | Spec |
|------:|---------|------|
| 1 | Restore `verify-local` merge gate (imports + corpus regen) | `docs/superpowers/specs/2026-07-21-verify-local-gate-design.md` |
| 2 | Self-stack risk precision (this document) | this file |

Windows/Docker Desktop packaging is **parked** (default later: Docker Desktop + browser). Not part of either program.

## 3. Scope

### In scope

1. **Richer self-stack generation** in `scripts/generate_security_corpus.py`
   - Preserve version pins from `backend/requirements.txt` where present
   - Preserve version ranges/pins from `frontend/package.json` dependencies / devDependencies where present
   - Tag ecosystem: `pypi` | `npm` | `runtime` (for `postgresql`, `nginx`, etc.)
   - Emit structured fields per term (at minimum): `term`, `source`, `ecosystem`, `version` (nullable), plus optional `vendor`/`product` aliases when trivial to derive
2. **Replace live-risk matcher** in `security_architecture/merge.py::self_stack_risk_rows`
   - Stop using `_stack_match_clause` description/`affected_products` free-text `LIKE` for Risk Register live rows
   - Treat self-stack entries as assets and score via existing `matching.cpe.score_cve_for_assets` (and helpers) against CVE `cpe_matches` / structured `affected_products`
3. **Admission policy by score**
   - Score **100** (product + version in range): admit as strong match
   - Score **55** (product match, version unknown): admit only as weaker tier with explicit UI/API labeling
   - No score: **exclude**
4. **UI / copy honesty** on Risk Register + overview tile help text: show match basis (`product+version` vs `product-only`); keep “not SBOM/PURL-precise” where data is incomplete, without looking like 45 confirmed criticals
5. **Docs:** `PRODUCT_STATUS`, `HANDOVER`, methodology note (About / section help) updated to describe structured matching
6. **Tests** for FP/TP fixtures and generator pin preservation

### Out of scope

| Item | Disposition |
|------|-------------|
| Embeddings / semantic search as primary matcher | Out — optional later corroboration only |
| Operator dismiss / mute live rows | Follow-up after precision lands |
| Full SBOM / CycloneDX / PURL platform | Out |
| Changing FEED/wallboard stack filter behavior | Out unless a tiny shared helper is extracted without behavior change |
| Docker Desktop / Windows `.exe` | Parked |
| Phase 1 leftovers (`ruff format`, FE >600 LOC, Testcontainers) | Parked |
| ARCH orphan page deletion | Separate follow-up |
| Risk Register cell wrap UX | Separate follow-up (UI-only) |

## 4. Root cause (why deployers see panic FPs)

Current live rows:
1. Build bare terms from requirements/`package.json` (**versions stripped**)
2. Query KEV/CRITICAL CVEs with `_stack_match_clause` → `LOWER(description|affected_products) LIKE %term%`
3. Label severity from the CVE row and show CRITICAL chips

That admits product-family collisions (e.g. Windows CryptoAPI CVE matching the word/path near `cryptography`) and floods the register with unverified “self-exposure.”

## 5. Architecture

### 5.1 Reuse existing CPE scorer

Do **not** invent a parallel matcher. Reuse `backend/matching/cpe.py`:
- `product_keys_match`
- `version_in_range` / `score_asset_against_cpe`
- `score_cve_for_assets(cpe_matches, assets) → best score {0, 55, 100}`

Correlation already converts `affected_products` entries into vendor/product dicts when `cpe_matches` is empty — live self-stack scoring should follow the same hydration pattern.

### 5.2 Self-stack as assets

Map each generated self-stack entry → asset dict for the scorer, e.g.:
- `product`: normalized package/product token
- `vendor`: optional (PyPI/npm often empty; runtime components may set vendor)
- `version`: pinned version when known; empty string when unknown

### 5.3 Candidate selection

Avoid scanning the entire CVE table with description `LIKE`. Prefer:
1. Restrict to `is_kev = 1 OR severity = 'CRITICAL'` (keep current urgency filter), **and**
2. Restrict to rows with non-empty `cpe_matches` and/or structured `affected_products`, **and**
3. Prefilter by normalized product token against those structured fields (exact/normalized key), then score

Exact SQL shape is an implementation detail; the invariant is: **no description-substring admission path** for live risk rows.

### 5.4 Presentation

- Title/summary include matched product, pin (if any), and match basis
- Weaker (55) rows must be visually/textually distinct from strong (100) rows
- Live rows remain non-hand-closable (still derived); precision reduces the set instead of adding dismiss in v1

## 6. Error handling & degraded modes

- If CPE/`affected_products` data is missing for many CVEs, the live list may shrink — that is **acceptable** (prefer empty/honest over noisy CRITICAL)
- Generator must remain idempotent for drift tests; new fields are additive on generated `self_stack.yaml` records
- Missing pins → product-only scoring path only (score 55 max)

## 7. Testing strategy

| Case | Expected |
|------|----------|
| Asset `cryptography` (pypi) vs CurveBall-like CPE (Windows CryptoAPI product) | No live row |
| Asset `react`@pinned vs CVE with matching npm/react CPE in range | Strong row (100) |
| Asset with no version vs CPE product match without usable range | Weaker row (55) or excluded if product keys don’t match |
| Generator round-trip | Pins preserved; ecosystem set; drift test updated |
| Overview tile | Counts only admitted rows |

## 8. Delivery

- Branch: `cursor/self-stack-precision-91c2` off main **after** Program 1 merges (or off main if Program 1 already landed)
- Docs in same PR: `PRODUCT_STATUS`, `HANDOVER`, methodology/help strings
- Gemini disposition before merge; prefer subagent-driven implementation

## 9. Spec self-review

- [x] No TBD placeholders for required behavior
- [x] Explicitly rejects embedding-primary matching
- [x] Reuses `matching.cpe` rather than duplicating version logic
- [x] Sequencing with verify-local gate documented
- [x] Out-of-scope prevents packaging / dismiss / full SBOM creep
