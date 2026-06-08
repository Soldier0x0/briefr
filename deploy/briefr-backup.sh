#!/usr/bin/env bash
# Create a BRIEFR backup (SQLite + .env) with integrity checks and retention pruning.
# Run as root or as the briefr user.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/briefr}"
APP_USER="${APP_USER:-briefr}"
APP_HOME="${APP_HOME:-/var/lib/briefr}"
REASON="${1:-scheduled}"

if [ "$(id -u)" -eq 0 ]; then
  mkdir -p "${APP_HOME}/backups/logs"
  chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}/backups"
  exec runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" \
    INSTALL_DIR="${INSTALL_DIR}" \
    bash "${INSTALL_DIR}/deploy/briefr-backup.sh" "${REASON}"
fi

cd "${INSTALL_DIR}/backend"
export BACKUP_DIR="${BACKUP_DIR:-${APP_HOME}/backups}"
"${INSTALL_DIR}/venv/bin/python" -m backup run --reason "${REASON}"
