#!/usr/bin/env bash
# Create a BRIEFR backup (SQLite or PostgreSQL + .env) with integrity checks
# and retention pruning. Archives are age-encrypted with the key in
# ${APP_HOME}/keys/backup-age.key (generated on first run, deliberately OUTSIDE
# BACKUP_DIR; set BACKUP_AGE_KEY_FILE="" to disable encryption).
#
# Backend selection is automatic:
#   DATABASE_URL=postgresql://...  →  pg_dump custom format (briefr.pgdump in tarball)
#   (unset)                      →  SQLite online backup (briefr.db in tarball)
#
# Requires postgresql-client (pg_dump) when DATABASE_URL points at PostgreSQL.
# Run as root or as the briefr user.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/briefr}"
APP_USER="${APP_USER:-briefr}"
APP_HOME="${APP_HOME:-/var/lib/briefr}"
REASON="${1:-scheduled}"

# ${VAR-default} (not :-) so an explicit empty value disables encryption.
export BACKUP_AGE_KEY_FILE="${BACKUP_AGE_KEY_FILE-${APP_HOME}/keys/backup-age.key}"

if [ "$(id -u)" -eq 0 ]; then
  mkdir -p "${APP_HOME}/backups/logs" "${APP_HOME}/keys"
  chmod 700 "${APP_HOME}/keys"
  chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}/backups" "${APP_HOME}/keys"
  exec runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" \
    PATH="/usr/bin:/bin:${INSTALL_DIR}/venv/bin" \
    INSTALL_DIR="${INSTALL_DIR}" \
    BACKUP_AGE_KEY_FILE="${BACKUP_AGE_KEY_FILE}" \
    bash "${INSTALL_DIR}/deploy/briefr-backup.sh" "${REASON}"
fi

cd "${INSTALL_DIR}/backend"
export BACKUP_DIR="${BACKUP_DIR:-${APP_HOME}/backups}"
if [ -n "${BACKUP_AGE_KEY_FILE}" ]; then
  # Idempotent: creates the key only when missing, prints the public key.
  "${INSTALL_DIR}/venv/bin/python" -m backup keygen >/dev/null
fi
"${INSTALL_DIR}/venv/bin/python" -m backup run --reason "${REASON}"
