# Intel snapshot publishing (operator runbook)

**Status:** Active (schema split Phase 0)  
**Related:** `docs/DATA_SNAPSHOT.md`, `docs/plans/2026-07-26-001-feature-intel-app-schema-split-plan.md`

---

## Overview

BRIEFR separates **intel** (publishable CVE/correlation data) from **app**
(operator credentials, IOC cache, preferences) using Postgres schemas `intel` and
`app`. Export uses schema-qualified `pg_dump` after Alembic revision
`036_intel_app_schema_split`.

---

## Production schema migration (one-time)

The physical schema split runs **once** when Alembic applies revision `036`
during deploy (`alembic upgrade head` via backend startup or operator runbook).
It does **not** re-run on every process start once `alembic_version` is at head.

### Before upgrade

1. Stop BRIEFR (backend + scheduler).
2. Take an encrypted full backup (existing `.7z` / `pg_dump` workflow).
3. Capture row-count manifest:

```bash
python scripts/schema_row_counts.py --output /var/backups/briefr/pre-036.json
```

### Upgrade

```bash
cd backend && alembic upgrade head
# or restart backend — init_db() runs migrations only when not already at head
```

### After upgrade

```bash
python scripts/verify_schema_split.py --manifest /var/backups/briefr/pre-036.json
```

Smoke: `/api/health`, login, CVE feed, admin DB page.

### Rollback

Restore the pre-migration encrypted backup. Downgrade of `036` is not supported.

---

## Export intel bundle

Publisher instance requirements:

- No real `app.users` rows (or use `--allow-operator-seed` for dev fixtures only).
- Only ingest `sync_state` keys in `intel.sync_state`.
- Only publishable `feed_cache` key prefixes (see `DATA_SNAPSHOT.md`).

```bash
python scripts/export_intel_snapshot.py --output /tmp/briefr-intel.pgdump.gz
python scripts/verify_intel_snapshot.py /tmp/briefr-intel.pgdump.gz
```

Automated publish (export + verify + `latest.json`):

```bash
python scripts/publish_intel_snapshot.py --output-dir /var/lib/briefr/intel-publish
```

See `deploy/intel-publish.cron.example` for cron wiring.

---

## Size strategy

At ~115 MB full compressed backup today, intel-only bundles are typically
**60–90 MB gzip**. Use GitHub Releases; add Git LFS when a single artifact
exceeds ~50 MB.

---

## References

- `scripts/export_intel_snapshot.py`
- `scripts/schema_row_counts.py`
- `scripts/verify_schema_split.py`
- `docs/OPERATIONS.md` (import / restore)
