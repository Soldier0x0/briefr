#!/usr/bin/env bash
# Emergency repair after bad chmod/chown — run as root
set -euo pipefail

INSTALL_DIR="/opt/briefr"
APP_USER="briefr"
APP_HOME="/var/lib/briefr"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: bash $0"
  exit 1
fi

id -u "${APP_USER}" &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin "${APP_USER}"

mkdir -p "${APP_HOME}/.cache/pip" "${APP_HOME}/.npm"
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}"
usermod -d "${APP_HOME}" "${APP_USER}" 2>/dev/null || true

chown -R "${APP_USER}:${APP_USER}" "${INSTALL_DIR}"
find "${INSTALL_DIR}" -type d -exec chmod 755 {} +
find "${INSTALL_DIR}" -type f -exec chmod 644 {} +
chmod 750 "${INSTALL_DIR}/backend"
[ -f "${INSTALL_DIR}/backend/.env" ] && chmod 640 "${INSTALL_DIR}/backend/.env"
chmod 755 "${INSTALL_DIR}/deploy/"*.sh 2>/dev/null || true
chmod 755 "${INSTALL_DIR}/venv/bin/"* 2>/dev/null || true

echo "OK: ${INSTALL_DIR} is owned by ${APP_USER} with usable permissions"
echo "Next: systemctl restart briefr.target && curl -s http://127.0.0.1:8000/api/health"
