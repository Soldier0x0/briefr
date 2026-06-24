#!/usr/bin/env bash
# PostgreSQL backup entry point — delegates to briefr-backup.sh.
# When DATABASE_URL is set, python -m backup run uses pg_dump on the HOST against
# the published container port (production: Postgres in Docker at /opt/infra/postgres).
# Kept as a separate unit name for operators migrating from SQLite timers.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/briefr-backup.sh" "${@:-scheduled}"
