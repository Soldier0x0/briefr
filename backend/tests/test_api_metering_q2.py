"""Q2 universal outbound API metering."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
ALLOWED_HTTPX_MODULES = {
    "resilient_client.py",
    "ai/openai_chat.py",
    "ai/gemini_client.py",
    "webhooks/ssrf.py",  # may construct clients for tests / allowlisted
}


_HTTPX_CLIENT_NAMES = {"AsyncClient", "Client", "request", "get", "post"}


def test_no_new_direct_httpx_outside_allowlist():
    """CI guard: outbound HTTP should go through resilient_request."""
    offenders = []
    for path in BACKEND.rglob("*.py"):
        if "tests" in path.parts or ".venv" in path.parts:
            continue
        rel = str(path.relative_to(BACKEND)).replace("\\", "/")
        if any(rel.endswith(a) or rel == a for a in ALLOWED_HTTPX_MODULES):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "httpx":
                for alias in node.names:
                    if alias.name in _HTTPX_CLIENT_NAMES:
                        imported_names.add(alias.asname or alias.name)
                        offenders.append(
                            f"{rel}:{node.lineno}:from httpx import {alias.name}"
                        )
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    if func.value.id == "httpx" and func.attr in _HTTPX_CLIENT_NAMES:
                        name = f"httpx.{func.attr}"
                elif isinstance(func, ast.Name) and func.id in imported_names:
                    name = func.id
                if name:
                    offenders.append(f"{rel}:{node.lineno}:{name}")
    assert offenders == [], (
        "direct httpx clients must go through resilient_client (or allowlist):\n"
        + "\n".join(offenders)
    )


def test_path_template_collapses_ids():
    from db.api_metering import path_template_from_url

    host, path = path_template_from_url(
        "https://services.nvd.nist.gov/rest/json/cves/2.0/CVE-2024-1234"
    )
    assert host == "services.nvd.nist.gov"
    assert "{id}" in path
    _, numeric = path_template_from_url("https://example.com/api/v1/items/12345")
    assert numeric.endswith("/{id}")


def test_metering_records_attempt(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "meter.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("API_CALL_EVENTS_ENABLED", "1")
    monkeypatch.setenv("PROCRASTINATE_ENABLED", "0")

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)

    import asyncio
    from api_metering import record_outbound_attempt
    from database import get_db
    from main import app

    async def _write():
        await record_outbound_attempt(
            source="nvd",
            method="GET",
            url="https://services.nvd.nist.gov/rest/json/cves/2.0",
            status_code=200,
            ok=True,
            latency_ms=12,
        )
        db = await get_db()
        try:
            rows = await db.execute_fetchall("SELECT source, ok FROM api_call_events")
            return rows
        finally:
            await db.close()

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        rows = asyncio.run(_write())
        assert rows
        res = client.get("/api/admin/api-usage/metering?hours=24")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert "by_source" in body
        assert any(r["source"] == "nvd" for r in body["by_source"])
