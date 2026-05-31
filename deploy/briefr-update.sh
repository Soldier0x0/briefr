#!/usr/bin/env bash
# BRIEFR update script — pull latest main and restart services
set -euo pipefail

INSTALL_DIR="/opt/briefr"
APP_USER="briefr"

ensure_app_user() {
  if ! id -u "${APP_USER}" &>/dev/null; then
    echo "==> Creating system user '${APP_USER}' (required by systemd units)"
    useradd --system --no-create-home --shell /usr/sbin/nologin "${APP_USER}"
  fi
}

run_git() {
  ensure_app_user
  if [ "$(id -u)" -eq 0 ]; then
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
ensure_app_user
chown -R "${APP_USER}:${APP_USER}" "${INSTALL_DIR}"
chmod 750 "${INSTALL_DIR}/backend"
[ -f "${INSTALL_DIR}/backend/.env" ] && chmod 640 "${INSTALL_DIR}/backend/.env"

echo "==> Updating Python dependencies"
sudo -u "${APP_USER}" "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"

echo "==> Updating frontend dependencies"
sudo -u "${APP_USER}" bash -c "cd '${INSTALL_DIR}/frontend' && npm install"

echo "==> Verifying backend imports"
sudo -u "${APP_USER}" bash -c "cd '${INSTALL_DIR}/backend' && '${INSTALL_DIR}/venv/bin/python' -c 'import main; print(\"import ok\")'"

echo "==> Starting BRIEFR services"
systemctl daemon-reload
systemctl start briefr.target

echo ""
echo "==> Service status"
systemctl status briefr.target --no-pager -l || true
systemctl status briefr-backend --no-pager -l | head -20 || true
systemctl status briefr-frontend --no-pager -l | head -12 || true
