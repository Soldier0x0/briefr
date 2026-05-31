#!/usr/bin/env bash
# BRIEFR update script — pull latest main and restart services
set -euo pipefail

INSTALL_DIR="/opt/briefr"
APP_USER="briefr"
APP_HOME="/var/lib/briefr"

ensure_app_user() {
  if ! id -u "${APP_USER}" &>/dev/null; then
    echo "==> Creating system user '${APP_USER}'"
    useradd --system --no-create-home --shell /usr/sbin/nologin "${APP_USER}"
  fi
}

ensure_app_home() {
  ensure_app_user
  mkdir -p "${APP_HOME}/.cache/pip" "${APP_HOME}/.npm"
  chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}"
  if [ "$(id -u)" -eq 0 ]; then
    usermod -d "${APP_HOME}" "${APP_USER}" 2>/dev/null || true
  fi
}

as_app_user() {
  ensure_app_home
  if [ "$(id -u)" -eq 0 ]; then
    runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" "$@"
  else
    env HOME="${APP_HOME}" "$@"
  fi
}

fix_tree_permissions() {
  ensure_app_user
  echo "==> Fixing ownership and permissions"
  chown -R "${APP_USER}:${APP_USER}" "${INSTALL_DIR}"
  find "${INSTALL_DIR}" -type d -exec chmod 755 {} +
  find "${INSTALL_DIR}" -type f -exec chmod 644 {} +
  chmod 750 "${INSTALL_DIR}/backend"
  [ -f "${INSTALL_DIR}/backend/.env" ] && chmod 640 "${INSTALL_DIR}/backend/.env"
  [ -d "${INSTALL_DIR}/deploy" ] && chmod 755 "${INSTALL_DIR}/deploy" && chmod 755 "${INSTALL_DIR}/deploy/"*.sh 2>/dev/null || true
  [ -d "${INSTALL_DIR}/venv/bin" ] && chmod 755 "${INSTALL_DIR}/venv/bin/"* 2>/dev/null || true
if [ -d "${INSTALL_DIR}/frontend/node_modules/.bin" ]; then
  chmod 755 "${INSTALL_DIR}/frontend/node_modules/.bin/"* 2>/dev/null || true
fi
}

echo "==> Stopping BRIEFR services"
systemctl stop briefr.target briefr-frontend briefr-backend 2>/dev/null || true

echo "==> Pulling latest from main"
if [ "$(id -u)" -eq 0 ]; then
  git config --global --add safe.directory "${INSTALL_DIR}" 2>/dev/null || true
  git -C "${INSTALL_DIR}" remote set-url origin https://github.com/Soldier0x0/briefr.git 2>/dev/null || true
  git -C "${INSTALL_DIR}" pull origin main
else
  as_app_user git -C "${INSTALL_DIR}" pull origin main
fi

fix_tree_permissions

echo "==> Updating Python dependencies"
as_app_user "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"

echo "==> Updating frontend dependencies"
as_app_user bash -c "cd '${INSTALL_DIR}/frontend' && npm install --cache '${APP_HOME}/.npm'"

echo "==> Verifying backend imports"
as_app_user bash -c "cd '${INSTALL_DIR}/backend' && '${INSTALL_DIR}/venv/bin/python' -c 'import main; print(\"import ok\")'"

echo "==> Starting BRIEFR services"
systemctl daemon-reload
systemctl start briefr.target

echo ""
echo "==> Service status"
systemctl status briefr.target --no-pager -l || true
systemctl status briefr-backend --no-pager -l | head -20 || true
systemctl status briefr-frontend --no-pager -l | head -12 || true
