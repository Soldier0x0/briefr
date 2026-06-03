#!/usr/bin/env bash
# Refresh MITRE ATT&CK techniques and CVE→technique mappings (weekly job uses same logic)
set -euo pipefail

INSTALL_DIR="/opt/briefr"
APP_USER="briefr"
APP_HOME="/var/lib/briefr"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: bash $0"
  exit 1
fi

mkdir -p "${APP_HOME}/.cache/pip"
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}" 2>/dev/null || true

echo "==> Refreshing MITRE ATT&CK data (STIX + CTID CSV + KEV mappings)"
runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" \
  bash -c "cd '${INSTALL_DIR}/backend' && '${INSTALL_DIR}/venv/bin/python' -c \"
import asyncio
import logging
from database import init_db, get_db
from feeds.mitre import refresh_mitre_data

logging.basicConfig(level=logging.INFO, format='%(message)s')

async def main():
    await init_db()
    db = await get_db()
    stats = await refresh_mitre_data(db)
    await db.close()
    print('')
    print('MITRE refresh complete:')
    print('  techniques loaded:', stats.get('techniques'))
    print('  CVEs with mappings (sources):', stats.get('cve_mappings_source'))
    print('  CVE→technique links in DB:', stats.get('cve_links'))
    if stats.get('skipped_unknown_techniques'):
        print('  skipped unknown technique IDs:', stats['skipped_unknown_techniques'])
    print('')
    print('Note: CTID publishes CVE mappings as CSV (not CVE_mappings.json).')
    print('Mappings appear in the drawer Intel tab for linked CVEs only.')

asyncio.run(main())
\""

echo "==> Done. Restart backend: sudo systemctl restart briefr-backend"
