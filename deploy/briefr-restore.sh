#!/usr/bin/env bash
# Restore BRIEFR database (and .env when present in archive) from a backup.
# Handles both plaintext (.tar.gz) and age-encrypted (.tar.gz.age) archives;
# decryption uses BACKUP_AGE_KEY_FILE (default: ${APP_HOME}/keys/backup-age.key).
# Usage:
#   bash briefr-restore.sh                 # newest valid archive
#   bash briefr-restore.sh --list
#   bash briefr-restore.sh /path/to/briefr-YYYYMMDDTHHMMSSZ.tar.gz[.age]
#   bash briefr-restore.sh --force         # overwrite healthy DB
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/briefr}"
APP_USER="${APP_USER:-briefr}"
APP_HOME="${APP_HOME:-/var/lib/briefr}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: bash $0"
  exit 1
fi

LIST=0
FORCE=0
ARCHIVE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --list) LIST=1 ;;
    --force) FORCE=1 ;;
    -h|--help)
      echo "Usage: bash $0 [--list] [--force] [archive.tar.gz[.age]]"
      exit 0
      ;;
    *)
      ARCHIVE="$1"
      ;;
  esac
  shift
done

export BACKUP_DIR="${BACKUP_DIR:-${APP_HOME}/backups}"
# ${VAR-default} (not :-) so an explicit empty value disables decryption.
export BACKUP_AGE_KEY_FILE="${BACKUP_AGE_KEY_FILE-${APP_HOME}/keys/backup-age.key}"

if [ "${LIST}" -eq 1 ]; then
  runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" BACKUP_DIR="${BACKUP_DIR}" \
    BACKUP_AGE_KEY_FILE="${BACKUP_AGE_KEY_FILE}" \
    bash -c "cd '${INSTALL_DIR}/backend' && '${INSTALL_DIR}/venv/bin/python' -m backup list"
  exit 0
fi

echo "==> Stopping BRIEFR backend before restore"
systemctl stop briefr-backend 2>/dev/null || true

FORCE_FLAG=""
[ "${FORCE}" -eq 1 ] && FORCE_FLAG="--force"

if [ -n "${ARCHIVE}" ]; then
  runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" BACKUP_DIR="${BACKUP_DIR}" \
    BACKUP_AGE_KEY_FILE="${BACKUP_AGE_KEY_FILE}" \
    bash -c "cd '${INSTALL_DIR}/backend' && '${INSTALL_DIR}/venv/bin/python' -m backup restore ${FORCE_FLAG} '${ARCHIVE}'"
else
  runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" BACKUP_DIR="${BACKUP_DIR}" \
    BACKUP_AGE_KEY_FILE="${BACKUP_AGE_KEY_FILE}" \
    bash -c "cd '${INSTALL_DIR}/backend' && '${INSTALL_DIR}/venv/bin/python' -m backup restore ${FORCE_FLAG}"
fi

echo "==> Starting BRIEFR backend"
systemctl start briefr-backend

echo "Restore complete. Verify:"
echo "  curl -sf http://127.0.0.1:8000/api/health | head -c 200; echo"
