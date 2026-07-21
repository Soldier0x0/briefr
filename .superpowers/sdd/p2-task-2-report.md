# Program 2 Task 2 Report — Structured live risk matching via CPE scorer

## Status

DONE

## Summary

- Commit: `590066ea feat(secarch): score live self-stack risks via CPE assets`
- Rewrote `security_architecture.merge.self_stack_risk_rows` so live self-stack risk rows are admitted only when `matching.cpe.score_cve_for_assets` returns `55` or `100`.
- Removed description/affected-products substring admission from this path by dropping `_stack_match_clause` from `self_stack_risk_rows`.
- Added `match_score` and `match_basis` to live risk rows.
- Preserved existing live-row fields including `matched_term`, `is_kev`, `severity`, CVSS/EPSS, and `published`.
- Updated the overview help copy to describe structured CPE product/version scoring instead of fuzzy term matching.
- Did not change FEED, wallboard, framework scope, or other `_stack_match_clause` consumers.

## TDD Evidence

### RED

Command:

`/workspace/backend/.venv/bin/python -m pytest tests/test_security_architecture_live.py -q`

Result after adding the three required tests and before production changes:

- `test_curveball_does_not_match_pypi_cryptography` failed because the old description LIKE path admitted the CurveBall row as a `cryptography` self-stack match.
- `test_product_version_match_is_strong` failed because the old path returned no row for CPE-only `react` metadata.
- `test_product_only_match_is_weaker_labeled` failed because the old path returned no row for CPE-only `fastapi` metadata.
- Summary: `3 failed, 21 passed`.

### GREEN

Focused live suite:

`/workspace/backend/.venv/bin/python -m pytest tests/test_security_architecture_live.py -q`

Result: `24 passed, 15 warnings`.

Final focused verification:

`/workspace/backend/.venv/bin/python -m pytest tests/test_security_architecture_live.py tests/test_cpe_matching.py -q`

Result: `36 passed, 15 warnings`.

## Implementation Notes

- Added top-level `json` import in `merge.py`; no inline `import json`.
- Added `_hydrate_cpe_matches(row)` using `cpe_matches` first and `affected_products` fallback.
- Added `_self_stack_assets(corpus)` using generated self-stack terms with optional `vendor` and exact `version`.
- Candidate query now loads KEV or critical CVEs only when structured CPE/product metadata exists, scores in memory, sorts admitted rows by KEV, score, and published date, and returns at most 50.
- `match_basis` is `product+version` for score `100` and `product-only` for score `55`.

## Self-Review

- Scope checked: only `merge.py`, the Security Architecture overview help string, the live test file, and this report changed.
- `_stack_match_clause` remains in place for the existing stack-scoped surfaces outside this self-stack risk path.
- The CurveBall false positive is guarded by a regression test.
- Structured product/version and product-only paths are guarded by regression tests.
- No full corpus regeneration was performed.

## Concerns

None.

---

## Final-review fix pass — candidate recall and dead helper cleanup

### Status

DONE

### Summary

- Deleted dead `_matched_term` from `backend/security_architecture/merge.py`.
- Deleted `test_matched_term_none_reads_as_unknown_not_python_none`, the direct helper-only test for `_matched_term`.
- Replaced the blind newest-500 KEV/critical candidate fetch with a structured-field product-token prefilter over `cpe_matches` and `affected_products`.
- Kept the urgency gate as `c.is_kev = 1 OR c.severity = 'CRITICAL'`, kept the non-empty structured-field gate, and kept final admission through `score_cve_for_assets` at scores `55` and `100`.
- SQL candidate fetch is now bounded at `LIMIT 2000` after the product-token prefilter; returned rows remain capped to 50 after scoring.
- No FEED `_stack_match_clause` changes.

### TDD Evidence

RED:

- Command: `cd /workspace/backend && .venv/bin/python -m pytest tests/test_security_architecture_live.py::test_self_stack_prefilter_finds_older_matching_kev_after_many_newer_nonmatches -q`
- Result before production change: failed as expected; rows were `[]` instead of `["CVE-2020-4242"]` because the older matching KEV was outside the newest 500 urgent candidates.

GREEN:

- Command: `cd /workspace/backend && .venv/bin/python -m pytest tests/test_security_architecture_live.py::test_self_stack_prefilter_finds_older_matching_kev_after_many_newer_nonmatches -q`
- Result: `1 passed, 1 warning`.

Final verification:

- Command: `cd /workspace/backend && .venv/bin/python -m pytest tests/test_security_architecture_live.py tests/test_security_architecture_corpus.py -q`
- Result: `60 passed, 16 warnings`.

### Concerns

None.
