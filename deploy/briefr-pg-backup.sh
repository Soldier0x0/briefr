#!/usr/bin/env bash
# PostgreSQL backup entry point — delegates to briefr-backup.sh.
# When DATABASE_URL is set, python -m backup run uses pg_dump on the HOST against
# the published container port (production: Postgres in Docker at /opt/infra/postgres).
# Scheduled via APScheduler job `scheduled_backup` (BACKUP_INTERVAL_HOURS).
# This script remains for manual / pre-restore / pre-update runs only.
# Do not enable briefr-pg-backup.timer alongside the backend — see OPERATIONS.md.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/briefr-backup.sh" "${@:-scheduled}"
