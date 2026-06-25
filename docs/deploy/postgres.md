# PostgreSQL

BRIEFR **requires PostgreSQL**. SQLite is not supported for production.

---

![Postgres topology — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/postgres-topology.png`](../assets/postgres-topology.png)  
> **Miro prompt:** [IMAGE_BRIEFS §4](../IMAGE_BRIEFS.md#4-postgres-topology)

## Why Postgres (not SQLite)

| Issue (SQLite era) | Postgres fix |
|--------------------|--------------|
| `database is locked` under nightly jobs + API | Row-level locking, connection pool |
| Concurrent OTX IOC prefetch | Safe upserts + striping (#225) |
| Multi-user path (V2.0) | Already on Postgres (#150+) |

## Local development

```bash
docker compose -f deploy/docker-compose.postgres.yml up -d
```

Default DSN in `.env.example`:

```text
DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5432/briefr
```

## Migrations

Alembic migrations run on backend startup. Schema changes ship with releases.

## Production

Production often uses Postgres 16 in Docker at `/opt/infra/postgres`, host `127.0.0.1:5432`.

## Full guide

[`POSTGRES.md`](../POSTGRES.md) — provisioning, tuning, parity notes.

## Troubleshooting

[postgres-and-backups.md](../troubleshoot/postgres-and-backups.md)
