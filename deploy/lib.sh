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
_highest_postgresql_client_bin() {
  local best_dir=""
  local max_ver=0
  local pg_dir ver_dir ver
  for pg_dir in /usr/lib/postgresql/*/bin; do
    [ -d "${pg_dir}" ] || continue
    if [ -x "${pg_dir}/pg_dump" ] && [ -x "${pg_dir}/pg_restore" ]; then
      ver_dir="${pg_dir%/bin}"
      ver="${ver_dir##*/}"
      if [ "${ver}" -gt "${max_ver}" ] 2>/dev/null; then
        max_ver="${ver}"
        best_dir="${pg_dir}"
      fi
    fi
  done
  if [ -n "${best_dir}" ]; then
    echo "${best_dir}"
  fi
}

ensure_postgresql_client() {
  if ! is_postgres_deployment; then
    return 0
  fi
  if command -v pg_dump &>/dev/null && command -v pg_restore &>/dev/null; then
    return 0
  fi
  if [ -n "$(_highest_postgresql_client_bin)" ]; then
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
    local pg_bin
    pg_bin="$(_highest_postgresql_client_bin)"
    if [ -n "${pg_bin}" ]; then
      export PATH="${pg_bin}:${PATH}"
    fi
  fi
  if ! command -v pg_dump &>/dev/null; then
    echo "ERROR: postgresql-client not available — backups and restore require pg_dump on PATH"
    echo "       Install manually: apt install postgresql-client"
    return 1
  fi
  echo "    pg_dump: $(command -v pg_dump)"
}

configure_backup_timer() {
  # M-5: APScheduler job `scheduled_backup` is the sole scheduled backup owner.
  # Host timers are disabled on install to avoid double archives with BACKUP_INTERVAL_HOURS.
  systemctl disable --now briefr-backup.timer 2>/dev/null || true
  systemctl disable --now briefr-pg-backup.timer 2>/dev/null || true
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
    npm ci --cache '${APP_HOME}/.npm'
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

# Forward-only Alembic migrations — run while backend is stopped (Postgres only).
run_alembic_upgrade() {
  if ! is_postgres_deployment; then
    echo "==> Skipping Alembic (no PostgreSQL DATABASE_URL in backend/.env)"
    return 0
  fi
  echo "==> Running Alembic migrations (forward-only upgrade head)"
  if ! as_app_user bash -c "
    set -euo pipefail
    cd '${INSTALL_DIR}/backend'
    '${INSTALL_DIR}/venv/bin/alembic' upgrade head
  "; then
    echo "FAIL: Alembic upgrade exited non-zero"
    return 1
  fi
  echo "    Alembic OK"
}

# Restore the pre-pull git commit and rebuild the prior release after a failed deploy.
rollback_failed_update() {
  local reason="${1:-update failed}"
  local prior_commit="${BRIEFR_PRE_UPDATE_COMMIT:-}"

  if [ -z "${prior_commit}" ]; then
    echo "ERROR: ${reason} — no BRIEFR_PRE_UPDATE_COMMIT recorded; cannot auto-rollback."
    echo "       Backend may be stopped. Diagnose: journalctl -u briefr-backend -n 50 --no-pager"
    echo "       Restore manually: git -C ${INSTALL_DIR} reset --hard <known-good-commit>"
    echo "       Then: bash ${INSTALL_DIR}/deploy/briefr-update.sh"
    return 1
  fi

  echo ""
  echo "==> ROLLBACK: ${reason}"
  echo "    Restoring git commit ${prior_commit}"

  systemctl stop briefr-backend briefr.target 2>/dev/null || true

  git -C "${INSTALL_DIR}" reset --hard "${prior_commit}"

  fix_tree_permissions

  echo "==> Reinstalling Python dependencies (prior release)"
  as_app_user "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"

  build_frontend
  install_systemd_units
  install_nginx_site

  echo "==> Starting backend (prior release)"
  systemctl enable briefr-backend
  systemctl restart briefr-backend
  nginx -t
  systemctl reload nginx

  echo ""
  echo "ROLLBACK complete — running prior release at ${prior_commit}."
  echo "Database schema may still reflect partial migrations from the failed update."
  echo "If the app fails to start, restore from the pre-update backup (see docs/OPERATIONS.md)."
  return 1
}

# Retry curl /api/health, then run check-backend.sh — exit non-zero when unhealthy.
verify_backend_health_gate() {
  local health_ok=0
  local check_script="${INSTALL_DIR}/deploy/check-backend.sh"

  echo ""
  echo "==> Health gate (retry up to 15s — backend may still be starting)"
  for _ in 1 2 3 4 5; do
    if curl -sf "http://127.0.0.1:8000/api/health" >/dev/null; then
      health_ok=1
      break
    fi
    sleep 3
  done

  if [ "${health_ok}" -eq 1 ]; then
    echo "    Backend :8000  OK (curl)"
  else
    echo "    Backend :8000  FAILED (curl)"
    if [ -f "${check_script}" ]; then
      echo "    Running ${check_script} ..."
      bash "${check_script}" || true
    fi
    return 1
  fi

  if [ -f "${check_script}" ]; then
    if bash "${check_script}"; then
      echo "    check-backend.sh OK"
    else
      echo "    check-backend.sh FAILED"
      return 1
    fi
  fi

  if curl -sf "http://127.0.0.1/api/health" >/dev/null; then
    echo "    Nginx /api   OK"
  else
    echo "    Nginx /api   FAILED (backend must be up; check /etc/nginx/sites-enabled/briefr)"
    return 1
  fi

  if [ -f "${INSTALL_DIR}/frontend/dist/index.html" ]; then
    echo "    Frontend dist OK"
  fi

  return 0
}

stamp_build_info() {
  local commit at
  if git -C "${INSTALL_DIR}" rev-parse --short HEAD &>/dev/null; then
    commit="$(git -C "${INSTALL_DIR}" rev-parse --short HEAD)"
  else
    commit="${BRIEFR_BUILD_COMMIT:-unknown}"
  fi
  at="${BRIEFR_BUILD_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
  echo "==> Stamping build info (commit=${commit})"
  printf '{"commit": "%s", "built_at": "%s"}\n' "${commit}" "${at}" \
    > "${INSTALL_DIR}/backend/.build-info.json"
  chown "${APP_USER}:${APP_USER}" "${INSTALL_DIR}/backend/.build-info.json"
}

stop_briefr_services() {
  echo "==> Stopping services"
  systemctl stop briefr.target briefr-backend 2>/dev/null || true
  systemctl stop briefr-frontend 2>/dev/null || true
}

start_briefr_services() {
  echo "==> Starting backend and nginx"
  systemctl enable briefr-backend
  systemctl restart briefr-backend
  nginx -t
  systemctl reload nginx
}

ensure_python_venv() {
  if [ -x "${INSTALL_DIR}/venv/bin/python" ]; then
    return 0
  fi
  echo "==> Creating Python virtual environment"
  local py=""
  for bin in python3.13 python3.12 python3.11 python3; do
    if command -v "${bin}" &>/dev/null; then
      py="${bin}"
      break
    fi
  done
  if [ -z "${py}" ]; then
    echo "ERROR: python3 not found — install Python 3.11+ and re-run"
    return 1
  fi
  "${py}" -m venv "${INSTALL_DIR}/venv"
  as_app_user "${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip
}

install_python_dependencies() {
  echo "==> Updating Python dependencies"
  as_app_user "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"
  if [ "${BRIEFR_INSTALL_DEV_DEPS:-}" = "1" ]; then
    echo "==> Updating Python dev/test dependencies"
    as_app_user "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements-dev.txt"
  fi
}

verify_backend_imports() {
  echo "==> Verifying backend imports"
  as_app_user bash -c "cd '${INSTALL_DIR}/backend' && '${INSTALL_DIR}/venv/bin/python' -c 'import main; print(\"import ok\")'"
}

# Apply a release from the local install tree (no git pull).
# Optional env: BRIEFR_SKIP_MIGRATE=1 BRIEFR_SKIP_BUILD=1 BRIEFR_SKIP_HEALTH=1
deploy_apply_release() {
  fix_tree_permissions
  stamp_build_info
  install_python_dependencies
  verify_backend_imports

  if [ "${BRIEFR_SKIP_MIGRATE:-0}" != "1" ]; then
    if ! run_alembic_upgrade; then
      return 1
    fi
  else
    echo "==> Skipping Alembic (BRIEFR_SKIP_MIGRATE=1)"
  fi

  if [ "${BRIEFR_SKIP_BUILD:-0}" != "1" ]; then
    build_frontend
  else
    echo "==> Skipping frontend build (BRIEFR_SKIP_BUILD=1)"
    if [ ! -f "${INSTALL_DIR}/frontend/dist/index.html" ]; then
      echo "ERROR: BRIEFR_SKIP_BUILD=1 but ${INSTALL_DIR}/frontend/dist/index.html is missing"
      return 1
    fi
  fi

  install_systemd_units
  install_nginx_site
  disable_vite_dev
  start_briefr_services

  if [ "${BRIEFR_SKIP_HEALTH:-0}" != "1" ]; then
    verify_backend_health_gate || return 1
  else
    echo "==> Skipping health gate (BRIEFR_SKIP_HEALTH=1)"
  fi
  return 0
}

print_service_status_summary() {
  echo ""
  echo "==> Service status"
  systemctl status briefr-backend --no-pager -l | head -15 || true
  systemctl status nginx --no-pager -l | head -10 || true
  if systemctl is-active --quiet briefr-frontend 2>/dev/null; then
    echo "WARNING: legacy briefr-frontend (Vite :5173) is still running"
    echo "         Run: systemctl stop briefr-frontend && systemctl mask briefr-frontend"
  fi
}

run_post_deploy_smoke() {
  local smoke_script="${INSTALL_DIR}/deploy/smoke-intel.sh"
  if [ "${BRIEFR_SKIP_SMOKE:-0}" = "1" ]; then
    echo "    Intel smoke    skipped (BRIEFR_SKIP_SMOKE=1)"
    return 0
  fi
  if [ ! -f "${smoke_script}" ]; then
    echo "    Intel smoke    skipped (smoke-intel.sh not found)"
    return 0
  fi
  if bash "${smoke_script}"; then
    echo "    Intel smoke    OK"
    return 0
  fi
  if [ "${BRIEFR_STRICT_SMOKE:-1}" = "0" ]; then
    echo "    Intel smoke    WARN (failed; BRIEFR_STRICT_SMOKE=0 — deploy completed anyway)"
    return 0
  fi
  echo "FAIL: Intel smoke check failed (strict by default)"
  echo "       Opt out: BRIEFR_SKIP_SMOKE=1 (skip) or BRIEFR_STRICT_SMOKE=0 (warn only)"
  return 1
}

require_install_tree() {
  if [ ! -f "${INSTALL_DIR}/backend/main.py" ]; then
    echo "ERROR: BRIEFR install tree not found at ${INSTALL_DIR}"
    echo "       Expected ${INSTALL_DIR}/backend/main.py"
    echo "       Copy or extract a release artifact to ${INSTALL_DIR} first."
    return 1
  fi
  if [ ! -f "${INSTALL_DIR}/backend/requirements.txt" ]; then
    echo "ERROR: ${INSTALL_DIR}/backend/requirements.txt missing"
    return 1
  fi
  return 0
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo bash $1"
    return 1
  fi
  return 0
}
