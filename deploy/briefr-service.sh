#!/usr/bin/env bash
# BRIEFR service control — start, stop, restart, status, health (no git, no build).
#
# Production operators use this for day-to-day restarts after .env or config changes.
# Full release apply (pip, migrate, frontend build): briefr-deploy.sh
# Git pull + update (legacy): briefr-update.sh
#
# Usage (as root):
#   bash /opt/briefr/deploy/briefr-service.sh start
#   bash /opt/briefr/deploy/briefr-service.sh stop
#   bash /opt/briefr/deploy/briefr-service.sh restart
#   bash /opt/briefr/deploy/briefr-service.sh status
#   bash /opt/briefr/deploy/briefr-service.sh health
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/briefr}"
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
# shellcheck source=lib.sh
source "${INSTALL_DIR}/deploy/lib.sh"

usage() {
  sed -n '2,12p' "${SCRIPT_PATH}"
  echo ""
  echo "Commands: start | stop | restart | status | health"
}

CMD="${1:-}"
if [ -z "${CMD}" ]; then
  usage
  exit 2
fi

require_root "${SCRIPT_PATH}" || exit 1

case "${CMD}" in
  start)
    echo "==> Starting BRIEFR"
    systemctl enable briefr-backend
    systemctl start briefr-backend
    if command -v nginx &>/dev/null; then
      nginx -t
      systemctl reload nginx
    fi
    verify_backend_health_gate
    ;;
  stop)
    echo "==> Stopping BRIEFR"
    stop_briefr_services
    ;;
  restart)
    echo "==> Restarting BRIEFR"
    systemctl enable briefr-backend
    systemctl restart briefr-backend
    if command -v nginx &>/dev/null; then
      nginx -t
      systemctl reload nginx
    fi
    print_service_status_summary
    verify_backend_health_gate
    ;;
  status)
    print_service_status_summary
    ;;
  health)
    verify_backend_health_gate
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: ${CMD}" >&2
    usage
    exit 2
    ;;
esac
