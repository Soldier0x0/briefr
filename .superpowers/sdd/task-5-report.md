# Task 5 Report - Manual Retry enqueues durable LLM extraction job

## Status

- Implemented on branch `cursor/w2-llm-durable-91c2`.
- `POST /api/admin/scheduler/run` now special-cases `job_id="llm_product_extraction"` when Procrastinate is enabled.
- Manual Run/Retry defers `jobs:llm_product_extraction` with:
  - `trigger="manual"`
  - `queueing_lock="llm_product_extraction"`
  - `priority=10`
- `AlreadyEnqueued` is treated as an idempotent success.
- Disabled or unavailable Procrastinate falls back to the existing scheduler background path.
- Push was not performed; the controller will push the wave PR.

## Files changed

- `backend/routers/admin/jobs.py`
- `backend/tests/test_admin_scheduler.py`
- `docs/PRODUCT_STATUS.md`
- `docs/SYSTEM_DESIGN.md`
- `docs/API_REFERENCE.md`
- `docs/HANDOVER.md`
- `.superpowers/sdd/task-5-report.md`

## TDD evidence

- Red test added first:
  - `pytest tests/test_admin_scheduler.py::test_run_llm_product_extraction_defers_manual_durable_job -q`
  - Failed because the endpoint returned `Job 'llm_product_extraction' started in background`, proving the current path spawned the scheduler fallback instead of deferring the durable manual job.
- Green after implementation:
  - `pytest tests/test_admin_scheduler.py::test_run_llm_product_extraction_defers_manual_durable_job -q`
  - Result: `1 passed, 2 warnings`.

## Focused verification

- Command:
  - `pytest tests/test_admin_scheduler.py tests/test_llm_extraction_durable.py -q`
- Result:
  - `19 passed, 8 warnings in 1.86s`
- Warnings are existing FastAPI/Starlette deprecations from the test stack.

## Docs

- `PRODUCT_STATUS.md`: Durable jobs row now notes Admin Run/Retry defers the LLM durable job with manual trigger and elevated priority.
- `SYSTEM_DESIGN.md`: LLM product extraction and ownership registry now include manual durable defer behavior.
- `API_REFERENCE.md`: `POST /api/admin/scheduler/run` now documents the LLM durable special case.
- `HANDOVER.md`: Added newest-first Task 5 handover entry.

## Concerns

- Graphify was intentionally not run per task constraint.
- Existing unrelated working tree modification remains untouched: `.superpowers/sdd/task-3-report.md`.
- Full backend suite was not run; verification was focused per task request on admin run and durable extraction behavior.
