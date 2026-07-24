# Contributor rules

Essential conventions for changing BRIEFR. Full install and test steps live in
[`ONBOARDING.md`](ONBOARDING.md); community process in [`CONTRIBUTING.md`](../CONTRIBUTING.md).

## Source of truth

- [`PRODUCT_STATUS.md`](PRODUCT_STATUS.md) — what is shipped in production today
- [`API_REFERENCE.md`](API_REFERENCE.md) — HTTP API contract
- [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) — architecture
- Online docs: https://docs.projectjupiter.in

When docs disagree with code, **code + PRODUCT_STATUS win**.

## Danger zones — read before editing

1. **SQL:** `db/` is **Postgres-native**. Write Postgres SQL; use parallel
   `_SQLITE` / `_PG` constants only where SQLite compatibility keeps the default
   test suite green. Production requires `DATABASE_URL` + `BRIEFR_REQUIRE_POSTGRES=1`.
   Any `db/` change should be validated on Postgres when possible
   (`DATABASE_URL=postgresql://… pytest tests/ -q`).
2. **Scheduler locks:** job `id=` strings in `scheduler.py` must stay in sync with
   `routers/admin/jobs.py` `_JOB_RUN_MAP`.
3. **Migrations are forward-only** (Alembic). Never edit an applied migration; add a
   new revision. Postgres-native DDL must be exercised via `verify-local.sh --full`.
4. **Secrets in logs:** never interpolate API keys or tokens into log message strings.
5. **`deploy/` scripts run on live production boxes.** Changes must stay additive per
   the compatibility promise in [`OPERATIONS.md`](OPERATIONS.md).
6. **Heavy work never runs on the request path.** ML, enrichment sweeps, and external
   syncs belong in `scheduler.py` jobs.

## Error handling

- **Backend:** `HTTPException` with short, safe `detail` for expected 4xx; unexpected
  errors reach the global handler (500 + `request_id`). Never put stack traces, SQL, or
  secrets in `detail`.
- **Frontend:** show API `detail` plus `X-Request-ID` ("ref: …"). Every async region
  needs loading / empty / error / data states.

## UI rules

- Density-first layout — no wide side margins or centered narrow columns on feeds/tables.
- Dark terminal aesthetic; semantic tokens from `frontend/src/styles/tokens.css`.
- Radix primitives for checkbox, radio, select, switch, tabs, dialog, tooltip.
- See [`design/design-system.md`](design/design-system.md) §23 for repo-wide UX standards.

## Docs rules

Runtime behavior or API changes → update `PRODUCT_STATUS.md` and `API_REFERENCE.md`
in the same PR.

## Merge gate

```bash
./scripts/verify-local.sh
```

Backend: `pytest tests/ -q` · Frontend: `npm run build` · Use `--full` when Postgres is available.
