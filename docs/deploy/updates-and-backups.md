# Updates and backups

Deploy updates safely; understand backup and restore.

---

![Deploy update flow — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/deploy-update-flow.png`](../assets/deploy-update-flow.png)  
> **Miro prompt:** [IMAGE_BRIEFS §2](../IMAGE_BRIEFS.md#2-deploy-update-flow)

![Backup restore flow — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/backup-restore-flow.png`](../assets/backup-restore-flow.png)  
> **Miro prompt:** [IMAGE_BRIEFS §3](../IMAGE_BRIEFS.md#3-backup-restore-flow)

## Update script

```bash
bash /opt/briefr/deploy/briefr-update.sh
```

Optional dev deps for on-server tests:

```bash
BRIEFR_INSTALL_DEV_DEPS=1 bash deploy/briefr-update.sh
```

## Backup tiers

| Trigger | Mechanism |
|---------|-----------|
| Every 6h | `briefr-pg-backup.timer` |
| Pre-update | `briefr-update.sh` |
| Manual | `briefr-backup.sh manual` |
| Startup | Auto-restore if DB corrupt |

Archives: `/var/lib/briefr/backups` — `briefr-*.tar.gz.age` when age key present.

## Restore

```bash
bash /opt/briefr/deploy/briefr-restore.sh --list
bash /opt/briefr/deploy/briefr-restore.sh
```

## Key env vars

| Variable | Default |
|----------|---------|
| `BACKUP_DIR` | `/var/lib/briefr/backups` |
| `BACKUP_RETENTION_COUNT` | `100` |
| `BACKUP_AGE_KEY_FILE` | `/var/lib/briefr/keys/backup-age.key` |

## Legacy

[`OPERATIONS.md`](../OPERATIONS.md) — full ops contract.
