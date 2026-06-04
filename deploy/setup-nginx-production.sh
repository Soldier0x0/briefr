#!/usr/bin/env bash
# One-time or repeat production setup — delegates to briefr-update.sh
# Run as root: bash /opt/briefr/deploy/setup-nginx-production.sh
#
# USE_TLS=1  — force HTTPS config (projectjupiter.in)
# Otherwise TLS is auto-enabled when certbot certs exist.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/briefr-update.sh"
