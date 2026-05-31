#!/usr/bin/env bash
# Quick backend diagnostics — run on the server as root
set -euo pipefail

INSTALL_DIR="/opt/briefr"
APP_USER="briefr"

echo "=== journalctl (last 40 lines) ==="
journalctl -u briefr-backend -n 40 --no-pager || true

echo ""
echo "=== import test as ${APP_USER} ==="
cd "${INSTALL_DIR}/backend"
sudo -u "${APP_USER}" "${INSTALL_DIR}/venv/bin/python" -c "import main; print('OK: main imported')" || {
  echo "FAILED — run: chown -R ${APP_USER}:${APP_USER} ${INSTALL_DIR}"
  exit 1
}

echo ""
echo "=== health check ==="
curl -sf "http://127.0.0.1:8000/api/health" && echo || echo "Backend not responding on :8000"
