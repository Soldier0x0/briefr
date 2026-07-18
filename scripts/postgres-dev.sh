#!/usr/bin/env bash
# Disposable PostgreSQL 16 + pgvector for dev/CI pytest (PG-002 / embeddings E1).
#
# Starts a throwaway container on 127.0.0.1:5433 so the dual-DB test rule in
# CLAUDE.md does not collide with production (:5432) or
# deploy/docker-compose.postgres.yml (also :5432).
#
# Usage (from repo root):
#   ./scripts/postgres-dev.sh start    # create/start briefr-pg-test, wait, print DATABASE_URL
#   ./scripts/postgres-dev.sh stop
#   ./scripts/postgres-dev.sh status
#   ./scripts/postgres-dev.sh url
#   ./scripts/postgres-dev.sh wait
#   ./scripts/postgres-dev.sh destroy  # remove container (data lost)
#
# Example pytest both-ways:
#   DATABASE_URL="$(./scripts/postgres-dev.sh url)" BRIEFR_REQUIRE_POSTGRES=1 \
#     python3 -m pytest tests/ -q   # from backend/
#
# Override image: BRIEFR_PG_DEV_IMAGE=pgvector/pgvector:pg16 (default).
# Existing containers started on plain postgres:16-alpine lack `vector` —
# run `./scripts/postgres-dev.sh destroy && ./scripts/postgres-dev.sh start`
# once after pulling this change.

set -eu
set -o pipefail 2>/dev/null || true

CONTAINER_NAME="${BRIEFR_PG_DEV_CONTAINER:-briefr-pg-test}"
PG_IMAGE="${BRIEFR_PG_DEV_IMAGE:-pgvector/pgvector:pg16}"
PG_PORT="${BRIEFR_PG_DEV_PORT:-5433}"
PG_USER="${BRIEFR_PG_DEV_USER:-briefr}"
PG_PASSWORD="${BRIEFR_PG_DEV_PASSWORD:-briefr}"
PG_DB="${BRIEFR_PG_DEV_DB:-briefr}"
PG_URL="postgresql://${PG_USER}:${PG_PASSWORD}@127.0.0.1:${PG_PORT}/${PG_DB}"

cmd="${1:-start}"

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required for postgres-dev.sh" >&2
    exit 1
  fi
}

wait_ready() {
  require_docker
  for _ in $(seq 1 45); do
    if docker exec "$CONTAINER_NAME" pg_isready -U "$PG_USER" -d "$PG_DB" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "Postgres container '$CONTAINER_NAME' did not become ready in 45s" >&2
  return 1
}

case "$cmd" in
  start)
    require_docker
    if docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
      docker start "$CONTAINER_NAME" >/dev/null 2>&1 || true
    else
      docker run -d \
        --name "$CONTAINER_NAME" \
        -p "127.0.0.1:${PG_PORT}:5432" \
        -e "POSTGRES_USER=${PG_USER}" \
        -e "POSTGRES_PASSWORD=${PG_PASSWORD}" \
        -e "POSTGRES_DB=${PG_DB}" \
        "$PG_IMAGE" >/dev/null
    fi
    wait_ready
    echo "Postgres dev container ready: $CONTAINER_NAME on 127.0.0.1:${PG_PORT}"
    echo "DATABASE_URL=$PG_URL"
    ;;
  stop)
    require_docker
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    echo "Stopped $CONTAINER_NAME"
    ;;
  status)
    require_docker
    if docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
      docker ps -a --filter "name=^/${CONTAINER_NAME}$" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    else
      echo "Container $CONTAINER_NAME not found"
      exit 1
    fi
    ;;
  url)
    echo "$PG_URL"
    ;;
  wait)
    wait_ready
    ;;
  destroy)
    require_docker
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    echo "Removed $CONTAINER_NAME"
    ;;
  *)
    echo "Usage: $0 {start|stop|status|url|wait|destroy}" >&2
    exit 1
    ;;
esac
