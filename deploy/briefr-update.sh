#!/usr/bin/env bash
# BRIEFR update script — pull latest main and restart services
set -euo pipefail

INSTALL_DIR="/opt/briefr"
APP_USER="briefr"

echo "==> Stopping BRIEFR services"
systemctl stop briefr.target briefr-frontend briefr-backend 2>/dev/null || true

echo "==> Pulling latest from main"
cd "${INSTALL_DIR}"
git pull origin main

echo "==> Fixing ownership (required after pull as root)"
if id -u "${APP_USER}" &>/dev/null; then
  chown -R "${APP_USER}:${APP_USER}" "${INSTALL_DIR}"
  chmod 750 "${INSTALL_DIR}/backend"
  [ -f "${INSTALL_DIR}/backend/.env" ] && chmod 640 "${INSTALL_DIR}/backend/.env"
fi

echo "==> Updating Python dependencies"
"${INSTALL_DIR}/venv/bin/pip" install -r backend/requirements.txt

echo "==> Updating frontend dependencies"
cd "${INSTALL_DIR}/frontend"
npm install

echo "==> Verifying backend imports"
cd "${INSTALL_DIR}/backend"
if id -u "${APP_USER}" &>/dev/null; then
  sudo -u "${APP_USER}" "${INSTALL_DIR}/venv/bin/python" -c "import main; print('import ok')"
else
  "${INSTALL_DIR}/venv/bin/python" -c "import main; print('import ok')"
fi

echo "==> Starting BRIEFR services"
systemctl daemon-reload
systemctl start briefr.target

echo ""
echo "==> Service status"
systemctl status briefr.target --no-pager -l || true
systemctl status briefr-backend --no-pager -l | head -20 || true
systemctl status briefr-frontend --no-pager -l | head -12 || true
