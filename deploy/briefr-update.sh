#!/usr/bin/env bash
# BRIEFR update script — pull latest main and restart services
set -euo pipefail

INSTALL_DIR="/opt/briefr"
APP_USER="briefr"

run_git() {
  if [ "$(stat -c '%U' "${INSTALL_DIR}/.git" 2>/dev/null)" = "${APP_USER}" ] && [ "$(id -u)" -eq 0 ]; then
    sudo -u "${APP_USER}" git -C "${INSTALL_DIR}" "$@"
  else
    git -C "${INSTALL_DIR}" "$@"
  fi
}

echo "==> Stopping BRIEFR services"
systemctl stop briefr.target briefr-frontend briefr-backend 2>/dev/null || true

echo "==> Pulling latest from main"
run_git pull origin main

echo "==> Fixing ownership"
if id -u "${APP_USER}" &>/dev/null; then
  chown -R "${APP_USER}:${APP_USER}" "${INSTALL_DIR}"
  chmod 750 "${INSTALL_DIR}/backend"
  [ -f "${INSTALL_DIR}/backend/.env" ] && chmod 640 "${INSTALL_DIR}/backend/.env"
fi

echo "==> Updating Python dependencies"
if id -u "${APP_USER}" &>/dev/null; then
  sudo -u "${APP_USER}" "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"
else
  "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"
fi

echo "==> Updating frontend dependencies"
if id -u "${APP_USER}" &>/dev/null; then
  sudo -u "${APP_USER}" bash -c "cd '${INSTALL_DIR}/frontend' && npm install"
else
  cd "${INSTALL_DIR}/frontend" && npm install
fi

echo "==> Verifying backend imports"
if id -u "${APP_USER}" &>/dev/null; then
  sudo -u "${APP_USER}" "${INSTALL_DIR}/venv/bin/python" -c "import sys; sys.path.insert(0, '${INSTALL_DIR}/backend'); import main; print('import ok')"
else
  "${INSTALL_DIR}/venv/bin/python" -c "import sys; sys.path.insert(0, '${INSTALL_DIR}/backend'); import main; print('import ok')"
fi

echo "==> Starting BRIEFR services"
systemctl daemon-reload
systemctl start briefr.target

echo ""
echo "==> Service status"
systemctl status briefr.target --no-pager -l || true
systemctl status briefr-backend --no-pager -l | head -20 || true
systemctl status briefr-frontend --no-pager -l | head -12 || true
