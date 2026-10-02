# BRIEFR API image. Build context is the repo root.
# Production requirements only — not requirements-dev.txt.
# Final process is non-root and does not use --reload.
#
# Debian slim, not Alpine. Python 3.12 matches CI and is required by
# numpy==2.5.1 (Requires-Python >=3.12), so 3.11 cannot install requirements.txt.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# curl: image HEALTHCHECK. ca-certificates: outbound HTTPS (NVD and other feeds).
# tzdata: ZoneInfo on /api/health. libgomp1: numpy wheels.
# postgresql-client-16: pg_dump/pg_restore for the default backup job (server is PG 16).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        libgomp1 \
        tzdata \
    && install -d /usr/share/keyrings \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && apt-get purge -y gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

RUN groupadd --gid 10001 briefr \
    && useradd --uid 10001 --gid briefr --create-home --shell /usr/sbin/nologin briefr \
    && mkdir -p /var/lib/briefr/backups \
    && chown -R briefr:briefr /app /var/lib/briefr

USER briefr

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
