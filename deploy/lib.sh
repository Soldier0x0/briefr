#!/usr/bin/env bash
# Shared helpers for BRIEFR deploy scripts (sourced, not executed directly).
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/briefr}"
APP_USER="${APP_USER:-briefr}"
APP_HOME="${APP_HOME:-/var/lib/briefr}"
NGINX_SITE="${NGINX_SITE:-/etc/nginx/sites-available/briefr}"

ensure_app_user() {
  if ! id -u "${APP_USER}" &>/dev/null; then
    echo "==> Creating system user '${APP_USER}'"
    useradd --system --no-create-home --shell /usr/sbin/nologin "${APP_USER}"
  fi
}

ensure_app_home() {
  ensure_app_user
  mkdir -p \
    "${APP_HOME}/.cache/pip" \
    "${APP_HOME}/.npm" \
    "${APP_HOME}/backups/logs" \
    "${APP_HOME}/keys" \
    "${APP_HOME}/models"
  chmod 700 "${APP_HOME}/keys"
  chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}"
  usermod -d "${APP_HOME}" "${APP_USER}" 2>/dev/null || true
}

as_app_user() {
  ensure_app_home
  runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" "$@"
}

# Re-apply executable bits for tracked files git records as 100755.
# fix_tree_permissions runs chmod 644 on all files, which would otherwise
# leave mode-only diffs that block git pull on the next update.
sync_git_tracked_executable_bits() {
  local meta rel
  if ! git -C "${INSTALL_DIR}" rev-parse --is-inside-work-tree &>/dev/null; then
    return 0
  fi
  while IFS=$'\t' read -r meta rel; do
    case "${meta}" in
      100755\ *) ;;
      *) continue ;;
    esac
    [ -n "${rel}" ] || continue
    [ -f "${INSTALL_DIR}/${rel}" ] || continue
    chmod 755 "${INSTALL_DIR}/${rel}"
  done < <(git -C "${INSTALL_DIR}" ls-files -s 2>/dev/null)
}

# Reset tracked files whose only diff is file mode (leftover +x from older deploy runs).
restore_git_permission_drift() {
  local rel
  if ! git -C "${INSTALL_DIR}" rev-parse --is-inside-work-tree &>/dev/null; then
    return 0
  fi

  sync_git_tracked_executable_bits

  while IFS= read -r -d '' rel; do
    [ -n "${rel}" ] || continue
    if git -C "${INSTALL_DIR}" diff --no-color --quiet -- "${rel}" 2>/dev/null; then
      continue
    fi
    if git -C "${INSTALL_DIR}" diff --no-color -- "${rel}" 2>/dev/null \
      | grep -vE '^(diff --git|index |[+-]{3} |@@|old mode|new mode)' \
      | grep -qE '^[+-]'; then
      continue
    fi
    echo "    Resetting permission-only drift on ${rel}"
    git -C "${INSTALL_DIR}" checkout-index -f -- "${rel}" 2>/dev/null \
      || git -C "${INSTALL_DIR}" restore --worktree -- "${rel}" 2>/dev/null \
      || git -C "${INSTALL_DIR}" checkout -- "${rel}" 2>/dev/null \
      || true
  done < <(git -C "${INSTALL_DIR}" diff -z --name-only 2>/dev/null || true)
  sync_git_tracked_executable_bits
}

fix_tree_permissions() {
  ensure_app_user
  echo "==> Fixing ownership and permissions"
  chown -R "${APP_USER}:${APP_USER}" "${INSTALL_DIR}"
  find "${INSTALL_DIR}" -type d -exec chmod 755 {} +
  find "${INSTALL_DIR}" -type f -exec chmod 644 {} +
  chmod 750 "${INSTALL_DIR}/backend"
  [ -f "${INSTALL_DIR}/backend/.env" ] && chmod 640 "${INSTALL_DIR}/backend/.env"
  if [ -d "${INSTALL_DIR}/deploy" ]; then
    chmod 755 "${INSTALL_DIR}/deploy"
  fi
  [ -d "${INSTALL_DIR}/venv/bin" ] && chmod 755 "${INSTALL_DIR}/venv/bin/"* 2>/dev/null || true
  # Playwright driver/node loses +x after the blanket chmod 644 above.
  find "${INSTALL_DIR}/venv/lib" -path '*/playwright/driver/node' -exec chmod 755 {} + 2>/dev/null || true
  if [ -d "${INSTALL_DIR}/frontend/node_modules/.bin" ]; then
    chmod 755 "${INSTALL_DIR}/frontend/node_modules/.bin/"* 2>/dev/null || true
  fi
  sync_git_tracked_executable_bits
}

ensure_node() {
  if command -v node &>/dev/null; then
    local node_ver
    node_ver="$(node -v | cut -d'v' -f2 | cut -d'.' -f1)"
    if [ "${node_ver}" -ge 18 ]; then
      return
    fi
    echo "==> Upgrading Node.js (found v${node_ver}, v18+ required for Vite)"
  fi

  echo "==> Installing Node.js (required for frontend build)"
  . /etc/os-release
  if [ "${VERSION_ID:-0}" = "11" ]; then
    echo "    Debian 11 (Bullseye): using NodeSource for Node.js 18"
    apt-get install -y -qq curl ca-certificates
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y -qq nodejs
  else
    apt-get update -qq
    apt-get install -y -qq nodejs npm
  fi
}

ensure_nginx() {
  if ! command -v nginx &>/dev/null; then
    echo "==> Installing nginx"
    apt-get update -qq
    apt-get install -y -qq nginx
  fi
  systemctl enable nginx
}

# True when backend/.env sets DATABASE_URL to a postgresql:// DSN.
is_postgres_deployment() {
  local env_file="${INSTALL_DIR}/backend/.env"
  [ -f "${env_file}" ] || return 1
  # Optional single/double quotes around the DSN value are common in .env files.
  grep -qE '^[[:space:]]*DATABASE_URL[[:space:]]*=[[:space:]]*["'\'']?postgres(ql)?://' \
    "${env_file}" 2>/dev/null
}

# pg_dump/pg_restore on the host (connects to Docker Postgres via published port).
ensure_postgresql_client() {
  if ! is_postgres_deployment; then
    return 0
  fi
  if command -v pg_dump &>/dev/null && command -v pg_restore &>/dev/null; then
    return 0
  fi
  if [ "$(id -u)" -ne 0 ]; then
    echo "WARN: postgresql-client is missing and we are not root — cannot auto-install."
    echo "      Install as root: apt install postgresql-client"
    return 1
  fi
  echo "==> Installing postgresql-client (pg_dump/pg_restore for PostgreSQL backups)"
  apt-get update -qq || true
  if ! apt-get install -y -qq postgresql-client; then
    # Bookworm/Trixie often expose versioned metapackages only.
    local ver
    for ver in 18 17 16 15; do
      if apt-get install -y -qq "postgresql-client-${ver}"; then
        break
      fi
    done
  fi
  if ! command -v pg_dump &>/dev/null; then
    echo "ERROR: postgresql-client not available — backups and restore require pg_dump on PATH"
    echo "       Install manually: apt install postgresql-client"
    return 1
  fi
  echo "    pg_dump: $(command -v pg_dump)"
}

configure_backup_timer() {
  systemctl disable --now briefr-backup.timer 2>/dev/null || true
  systemctl enable --now briefr-pg-backup.timer
}

install_nginx_site() {
  ensure_nginx
  local use_tls=0
  local site_mode="HTTP"
  if [ "${USE_TLS:-}" = "1" ]; then
    use_tls=1
  elif [ -f /etc/letsencrypt/live/projectjupiter.in/fullchain.pem ]; then
    use_tls=1
  fi
  if [ "${use_tls}" = "1" ]; then
    site_mode="HTTPS"
  fi

  echo "==> Installing nginx site (${site_mode})"
  if [ "${use_tls}" = "1" ]; then
    cp "${INSTALL_DIR}/deploy/nginx-briefr.conf" "${NGINX_SITE}"
  else
    cp "${INSTALL_DIR}/deploy/nginx-briefr-http.conf" "${NGINX_SITE}"
  fi
  ln -sf "${NGINX_SITE}" /etc/nginx/sites-enabled/briefr
  rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
}

install_systemd_units() {
  echo "==> Installing systemd units"
  sed "s|/opt/briefr|${INSTALL_DIR}|g" "${INSTALL_DIR}/deploy/briefr-backend.service" \
    > /etc/systemd/system/briefr-backend.service
  sed "s|/opt/briefr|${INSTALL_DIR}|g" "${INSTALL_DIR}/deploy/briefr-backup.service" \
    > /etc/systemd/system/briefr-backup.service
  cp "${INSTALL_DIR}/deploy/briefr-backup.timer" /etc/systemd/system/briefr-backup.timer
  sed "s|/opt/briefr|${INSTALL_DIR}|g" "${INSTALL_DIR}/deploy/briefr-pg-backup.service" \
    > /etc/systemd/system/briefr-pg-backup.service
  cp "${INSTALL_DIR}/deploy/briefr-pg-backup.timer" /etc/systemd/system/briefr-pg-backup.timer
  cp "${INSTALL_DIR}/deploy/briefr.target" /etc/systemd/system/briefr.target
  systemctl daemon-reload
  if is_postgres_deployment; then
    ensure_postgresql_client || \
      echo "    WARN: postgresql-client missing — scheduled Postgres backups will fail until installed"
  fi
  configure_backup_timer
}

disable_vite_dev() {
  echo "==> Disabling Vite dev server (production uses nginx + frontend/dist)"
  systemctl stop briefr-frontend 2>/dev/null || true
  systemctl disable briefr-frontend 2>/dev/null || true
  systemctl mask briefr-frontend 2>/dev/null || true
}

build_frontend() {
  ensure_node
  echo "==> Building frontend production bundle"
  as_app_user bash -c "
    set -euo pipefail
    cd '${INSTALL_DIR}/frontend'
    npm install --cache '${APP_HOME}/.npm'
    npm run build
  "
  if [ ! -f "${INSTALL_DIR}/frontend/dist/index.html" ]; then
    echo "ERROR: frontend build failed — ${INSTALL_DIR}/frontend/dist/index.html missing"
    exit 1
  fi
  echo "    Built: ${INSTALL_DIR}/frontend/dist"
}

run_pre_update_backup() {
  if [ -f "${INSTALL_DIR}/backend/backup/manager.py" ]; then
    if is_postgres_deployment; then
      ensure_postgresql_client || return 0
    fi
    echo "==> Pre-update backup (integrity-checked)"
    if bash "${INSTALL_DIR}/deploy/briefr-backup.sh" pre-update; then
      echo "    Backup OK"
    else
      echo "    Backup WARN — continuing update (check ${APP_HOME}/backups/logs/backup.log)"
    fi
  fi
}
