# PostgreSQL and backups

## Symptoms

- Backend refuses start — Postgres required
- `connection refused` to `127.0.0.1:5432`
- Restore script fails
- Startup auto-restore loop

## Fixes

| Issue | Fix |
|-------|-----|
| Postgres not running | `docker compose -f deploy/docker-compose.postgres.yml up -d` or start host service |
| Wrong `DATABASE_URL` | Match user/db/host/port in `.env` |
| Restore needs age key | Ensure `BACKUP_AGE_KEY_FILE` exists and matches archive |
| Corrupt DB | `briefr-restore.sh` — stops backend first |

![Backup restore — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/backup-restore-flow.png`](../assets/backup-restore-flow.png)

## Commands

```bash
bash /opt/briefr/deploy/briefr-restore.sh --list
bash /opt/briefr/deploy/briefr-backup.sh manual
```

## Related

[updates-and-backups.md](../deploy/updates-and-backups.md), [postgres.md](../deploy/postgres.md)
