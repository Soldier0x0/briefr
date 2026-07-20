# Task 6 report - Expand `run_catchup_tick` kicks

## Status

Implemented on branch `cursor/w3-catchup-drain-91c2`.

`run_catchup_tick` now kicks the enabled backlog drain paths for embeddings,
correlation precompute, LLM product extraction, and CPE catalog sync while
catch-up mode is actively accepting new work.

## Scope notes

- No new broker.
- No bypass of `api_queue`: the tick calls existing scheduler entrypoints.
- Existing enabled gates and locks stay authoritative:
  - `run_embeddings_sync`
  - `run_correlation_precompute_tick`
  - `run_llm_extraction_sync`
  - `run_cpe_catalog_sync`
- `run_llm_extraction_sync` still owns the Procrastinate enqueue path when
  durable jobs are enabled.

## TDD evidence

Red test run:

- Command: `cd backend && pytest tests/test_catchup_tick.py -q`
- Result: 2 failed, 4 passed.
- Expected failures:
  - active tick called only embeddings/correlation, not LLM/CPE.
  - embeddings exception aborted later kicks.

Green test run:

- Command: `cd backend && pytest tests/test_catchup_tick.py -q`
- Result: 6 passed, 1 warning.

## Files changed

- `backend/scheduler.py`
- `backend/tests/test_catchup_tick.py`
- `docs/PRODUCT_STATUS.md`
- `docs/HANDOVER.md`
- `.superpowers/sdd/task-6-report.md`

## Final verification

- `cd backend && pytest tests/test_catchup_tick.py -q`
  - `6 passed, 1 warning`
- `cd backend && pytest tests/test_catchup_tick.py tests/test_llm_product_extraction.py tests/test_detection_context_llm.py -q`
  - `30 passed, 1 warning`
- `cd backend && pytest tests/test_catchup_tick.py tests/test_llm_product_extraction.py tests/test_detection_context_llm.py tests/test_cpe_catalog_q3.py -q`
  - `36 passed, 2 warnings`
- `cd backend && pytest tests/ -q`
  - `7 failed, 1550 passed, 13 skipped, 329 warnings`
  - Rerun of the failing files stayed red with the same failure classes.

## Full-suite failures observed

- `tests/test_posture.py::test_security_readout_includes_posture`
  - `routers/admin/diagnostics.py` raises `NameError: datetime is not defined`.
- `tests/test_support_pack.py::test_support_pack_returns_redacted_bundle`
- `tests/test_support_pack.py::test_support_pack_redacts_secret_log_extras`
  - `routers/admin/diagnostics.py` raises `NameError: Response is not defined`.
- `tests/test_security_architecture_corpus.py::test_committed_corpus_has_no_drift`
- `tests/test_security_architecture_corpus.py::test_committed_architecture_graph_has_no_drift`
- `tests/test_security_architecture_corpus_drift_admin.py::test_check_corpus_drift_matches_committed_files`
- `tests/test_security_architecture_corpus_drift_admin.py::test_admin_corpus_drift_endpoint`
  - committed security corpus files have drifted from generated output.

## Concerns

- `run_catchup_tick` records only the first kick exception in scheduler
  last-run metadata to keep the existing short error field shape.
- The CPE and LLM paths can still no-op when their existing feature/provider
  gates are disabled, which is intentional.
- Full backend pytest is not green on this branch because of unrelated
  diagnostics import regressions and security-corpus drift listed above.
