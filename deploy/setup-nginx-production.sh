#!/usr/bin/env bash
# Build frontend for production and configure nginx (disable Vite dev service)
set -euo pipefail

INSTALL_DIR="/opt/briefr"
APP_USER="briefr"
APP_HOME="/var/lib/briefr"
NGINX_SITE="${NGINX_SITE:-/etc/nginx/sites-available/briefr}"
USE_TLS="${USE_TLS:-0}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: bash $0"
  exit 1
fi

id -u "${APP_USER}" &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin "${APP_USER}"
mkdir -p "${APP_HOME}/.npm"
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}" "${INSTALL_DIR}"

echo "==> Building frontend (production bundle)"
runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" npm_config_cache="${APP_HOME}/.npm" \
  bash -c "cd '${INSTALL_DIR}/frontend' && npm install && npm run build"

chmod 755 "${INSTALL_DIR}/frontend/node_modules/.bin/"* 2>/dev/null || true

echo "==> Installing nginx site config"
if [ "${USE_TLS}" = "1" ]; then
  cp "${INSTALL_DIR}/deploy/nginx-briefr.conf" "${NGINX_SITE}"
  echo "    TLS config installed — ensure certbot certificates exist for projectjupiter.in"
else
  cp "${INSTALL_DIR}/deploy/nginx-briefr-http.conf" "${NGINX_SITE}"
  echo "    HTTP config installed — edit server_name in ${NGINX_SITE} if needed"
fi

ln -sf "${NGINX_SITE}" /etc/nginx/sites-enabled/briefr
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

echo "==> Disabling Vite dev service (production uses nginx + dist)"
systemctl disable --now briefr-frontend 2>/dev/null || true

echo "==> Ensuring backend is enabled"
systemctl enable briefr-backend
systemctl restart briefr-backend

nginx -t
systemctl reload nginx

echo ""
echo "Production UI:  http://$(hostname -I | awk '{print $1}')/"
echo "API health:     http://$(hostname -I | awk '{print $1}')/api/health"
echo ""
echo "Set ALLOWED_ORIGINS in ${INSTALL_DIR}/backend/.env to your public URL, then:"
echo "  systemctl restart briefr-backend"
