#!/usr/bin/env bash
# Backfill has_poc from stored NVD reference URLs (uses project venv, same as systemd).
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/briefr}"
PY="${INSTALL_DIR}/venv/bin/python3"
SCRIPT="${INSTALL_DIR}/backend/scripts/backfill_poc.py"

if [[ ! -x "${PY}" ]]; then
  echo "error: venv python not found at ${PY}" >&2
  echo "Run deploy/setup.sh or create the venv under ${INSTALL_DIR}/venv" >&2
  exit 1
fi

cd "${INSTALL_DIR}/backend"
if [[ -f "${INSTALL_DIR}/backend/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${INSTALL_DIR}/backend/.env"
  set +a
fi

exec "${PY}" "${SCRIPT}" "$@"
