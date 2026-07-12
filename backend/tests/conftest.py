"""Shared pytest fixtures — Playwright smoke stack when PLAYWRIGHT_SMOKE=1,
and Postgres schema/isolation for running the backend suite against a live
DATABASE_URL (Sprint Post-B: full suite on Postgres, gates module conversion)."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import http.cookiejar
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
SEED_SCRIPT = REPO_ROOT / "scripts" / "seed_screenshot_data.py"

sys.path.insert(0, str(BACKEND_DIR))


def _postgres_dsn_or_none() -> str | None:
    """PG-001: use the settings-safe resolver, not a raw os.environ read.

    db/config.py::resolve_database_url() prioritizes settings.database_url
    (a Pydantic singleton frozen at process start) over os.environ, exactly
    so a test file's raw (non-monkeypatch) os.environ mutation can't corrupt
    Postgres detection for every test that runs afterward in the same
    process. test_db_explorer.py's module-level `os.environ["DATABASE_URL"]
    = ""` (never reverted -- module-level code can't use monkeypatch) used
    to defeat that safety net here by reading os.environ directly, breaking
    this fixture's isolation TRUNCATE for every test collected after it."""
    from db.config import resolve_database_url

    url = resolve_database_url()
    return url if url.startswith("postgresql") else None


_postgres_live: bool | None = None


def _postgres_is_live() -> bool:
    """True when DATABASE_URL points at Postgres and the server accepts connections."""
    global _postgres_live
    if _postgres_live is not None:
        return _postgres_live
    from backup.postgres_util import postgres_server_live

    _postgres_live = postgres_server_live()
    return _postgres_live


@pytest.fixture(scope="session", autouse=True)
def _postgres_schema_once():
    """Apply Alembic migrations once per session via a standalone asyncpg
    connection — never via the pool, which would bind it to this fixture's
    closing event loop (see tests/test_postgres_pool.py). No-op on SQLite or
    when Postgres is configured but unreachable (common on Windows dev boxes
    with DATABASE_URL in .env but no local server)."""
    if not _postgres_is_live():
        yield
        return

    async def _boot() -> None:
        from database import run_postgres_migrations

        await run_postgres_migrations()

    asyncio.run(_boot())

    # Every `with TestClient(app)` runs FastAPI lifespan, which calls
    # run_postgres_migrations() again — redundant once the session-level
    # migration above has already run (Gemini review, PR #303). main.py
    # binds its own module-level reference via `from database import
    # run_postgres_migrations`, so both names need patching.
    import database
    import main

    async def _noop_migrations() -> None:
        return

    database.run_postgres_migrations = _noop_migrations
    main.run_postgres_migrations = _noop_migrations

    # Alembic env.py fileConfig can run during the migration above after
    # collection-time `from main import app` already installed handlers.
    from structured_logging import configure_logging

    configure_logging()

    yield


@pytest.fixture(autouse=True)
def _postgres_test_isolation(_postgres_schema_once):
    """Truncate all app tables before each test when DATABASE_URL is
    Postgres and the server is reachable — reproduces the fresh-temp-file
    isolation SQLite tests get from tmp_path. No-op on SQLite (the default
    CI/local test run) or when Postgres is configured but down."""
    if not _postgres_is_live():
        yield
        return

    dsn = _postgres_dsn_or_none()
    assert dsn is not None

    async def _truncate() -> None:
        import asyncpg

        conn = await asyncpg.connect(dsn, timeout=15)
        try:
            rows = await conn.fetch(
                "SELECT tablename FROM pg_tables"
                " WHERE schemaname = 'public' AND tablename != 'alembic_version'"
            )
            tables = ", ".join(f'"{r["tablename"]}"' for r in rows)
            if tables:
                await conn.execute(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")
        finally:
            await conn.close()

    asyncio.run(_truncate())
    yield


def run_db_test(coro):
    """Run an async test body that calls database.get_db()/get_connection()
    directly (no TestClient/lifespan). Opens the Postgres pool for the
    duration of the call and closes it after — no-ops on SQLite, since
    init_pool()/close_pool() are already dialect-aware no-ops there.
    Drop-in replacement for `asyncio.run(coro)` in direct-db-call tests —
    takes the coroutine object itself (mirrors asyncio.run's signature),
    so `asyncio.run(foo(x, y))` becomes `run_db_test(foo(x, y))`."""
    from db.connection import close_pool, init_pool

    async def _wrapped():
        await init_pool()
        try:
            return await coro
        finally:
            await close_pool()

    return asyncio.run(_wrapped())


@pytest.fixture(autouse=True)
def _isolate_log_ring_buffer():
    """Clear the admin log ring buffer before each test and re-attach the
    handler if Alembic or another library replaced root handlers mid-session."""
    from structured_logging import clear_log_buffer, ensure_ring_buffer_attached

    ensure_ring_buffer_attached()
    clear_log_buffer()
    yield


@pytest.fixture(autouse=True)
def _noop_scheduler(monkeypatch):
    """Neutralize main.py lifespan's scheduler/on-startup hooks for every
    test. Every `with TestClient(app)` usage runs real FastAPI lifespan;
    without this, each such test would launch the actual scheduler and
    on-startup jobs. Centralized here instead of the ~15 files that
    previously hand-rolled the same three monkeypatch.setattr calls —
    tests that assert real scheduler behavior test scheduler.py directly,
    not through lifespan, so this is safe to apply unconditionally."""

    async def _noop_async(*args, **kwargs):
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)


@pytest.fixture(autouse=True)
def _clear_read_cache_between_tests():
    from read_cache import clear_read_cache

    clear_read_cache()
    yield
    clear_read_cache()


def seed_pytest_auth_user_if_missing(
    *,
    user_id: int = 1,
    username: str = "pytest-admin",
    role: str = "admin",
) -> None:
    """Insert the JWT test user when absent. Does not overwrite an existing row
    so demotion/revocation tests can change DB role after seeding."""

    async def _seed() -> None:
        from database import get_db

        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT id FROM users WHERE id = ?",
                (user_id,),
            )
            if rows:
                return
            await db.execute(
                """
                INSERT INTO users (id, username, password_hash, role, is_active)
                VALUES (?, ?, 'hash', ?, 1)
                """,
                (user_id, username, role),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(_seed())


@pytest.fixture
def auth_token():
    """Signed access-token factory (Sprint A0). Set the returned value as the
    `briefr_at` cookie on a TestClient to pass require_admin/require_user —
    admin routes no longer fail open when no key is configured."""
    from auth.tokens import create_access_token

    def _make(role: str = "admin") -> str:
        seed_pytest_auth_user_if_missing(role=role)
        return create_access_token(1, "pytest-admin", role)

    return _make


def attach_pytest_session_cookie(test_client) -> None:
    """Default admin JWT for TestClient when analyst API auth is enabled."""
    from auth.tokens import create_access_token

    test_client.cookies.set(
        "briefr_at",
        create_access_token(1, "pytest-admin", "admin"),
    )


def _request_wants_no_auth(request) -> bool:
    if request.node.get_closest_marker("no_auth") is not None:
        return True
    parent = request.node.parent
    while parent is not None:
        if parent.get_closest_marker("no_auth") is not None:
            return True
        parent = parent.parent
    return False


@pytest.fixture(autouse=True)
def _default_session_cookie_on_testclient(request, monkeypatch):
    """Attach briefr_at to TestClient unless the test/module is marked no_auth."""
    if _request_wants_no_auth(request):
        return

    from fastapi.testclient import TestClient

    original_init = TestClient.__init__
    original_enter = TestClient.__enter__

    def patched_init(self, app, *args, **kwargs):
        original_init(self, app, *args, **kwargs)
        attach_pytest_session_cookie(self)

    def patched_enter(self):
        original_enter(self)
        attach_pytest_session_cookie(self)
        return self

    monkeypatch.setattr(TestClient, "__init__", patched_init)
    monkeypatch.setattr(TestClient, "__enter__", patched_enter)


BACKEND_PORT = int(os.environ.get("PLAYWRIGHT_BACKEND_PORT", "8765"))
FRONTEND_PORT = int(os.environ.get("PLAYWRIGHT_FRONTEND_PORT", "5173"))
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}"

SMOKE_AUTH_USERNAME = "smoke"
SMOKE_AUTH_PASSWORD = "smoke-test-password-32bytes!!"


def _wait_url(url: str, *, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status < 500:
                    return
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                return
            last_err = exc
        except Exception as exc:  # noqa: BLE001 — poll until deadline
            last_err = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_err}")


def _terminate(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _build_incident_snapshot(env: dict[str, str]) -> None:
    code = """
import asyncio
from feeds.case_study_feed import build_incident_feed_snapshot
asyncio.run(build_incident_feed_snapshot())
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR),
        env=env,
        check=True,
    )


def _smoke_auth_cookies(backend_url: str) -> list[dict[str, str | bool]]:
    """Bootstrap or log in the smoke admin via API; return Playwright cookie dicts."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    with opener.open(f"{backend_url}/api/auth/setup-required", timeout=10) as resp:
        setup_required = json.loads(resp.read()).get("required", False)

    if setup_required:
        payload = {"username": SMOKE_AUTH_USERNAME, "password": SMOKE_AUTH_PASSWORD}
        endpoint = f"{backend_url}/api/auth/setup"
    else:
        payload = {
            "username": SMOKE_AUTH_USERNAME,
            "password": SMOKE_AUTH_PASSWORD,
            "remember_me": True,
        }
        endpoint = f"{backend_url}/api/auth/login"

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(req, timeout=10) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"Smoke auth failed ({resp.status}): {resp.read()}")

    cookies: list[dict[str, str | bool]] = []
    for cookie in jar:
        cookies.append(
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": "127.0.0.1",
                "path": cookie.path or "/",
                "httpOnly": True,
                "secure": False,
                "sameSite": "Strict",
            }
        )
    if not cookies:
        raise RuntimeError("Smoke auth succeeded but no session cookies were issued")
    return cookies


@pytest.fixture(scope="session")
def playwright_smoke_stack(tmp_path_factory):
    """Seed SQLite, start uvicorn + Vite preview, yield the UI base URL."""
    if os.environ.get("PLAYWRIGHT_SMOKE") != "1":
        pytest.skip("Set PLAYWRIGHT_SMOKE=1 to run Chromium smoke tests")

    dist_dir = FRONTEND_DIR / "dist"
    if not dist_dir.is_dir():
        pytest.fail(
            "frontend/dist missing — run: cd frontend && npm ci && npm run build",
        )

    db_path = tmp_path_factory.mktemp("playwright") / "briefr.db"
    env = os.environ.copy()
    env.update(
        {
            "DB_PATH": str(db_path),
            "BACKUP_ENABLED": "0",
            "BRIEFR_ENV": "development",
            "ALLOWED_ORIGINS": f"http://127.0.0.1:{FRONTEND_PORT}",
            "PLAYWRIGHT_BACKEND_URL": BACKEND_URL,
            "AUTH_COOKIE_SECURE": "0",
            "JWT_SECRET": "playwright-smoke-test-jwt-secret-32b",
            "RATE_LIMIT_ENABLED": "0",
        }
    )

    subprocess.run(
        [sys.executable, str(SEED_SCRIPT)],
        cwd=str(BACKEND_DIR),
        env=env,
        check=True,
    )
    _build_incident_snapshot(env)

    backend: subprocess.Popen[bytes] | None = None
    frontend: subprocess.Popen[bytes] | None = None
    try:
        backend = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(BACKEND_PORT),
                "--log-level",
                "warning",
            ],
            cwd=str(BACKEND_DIR),
            env=env,
        )
        frontend = subprocess.Popen(
            [
                "npm",
                "run",
                "preview",
                "--",
                "--host",
                "127.0.0.1",
                "--port",
                str(FRONTEND_PORT),
            ],
            cwd=str(FRONTEND_DIR),
            env=env,
        )

        _wait_url(f"{BACKEND_URL}/api/health")
        _wait_url(FRONTEND_URL)
        health = urllib.request.urlopen(f"{BACKEND_URL}/api/health", timeout=10)
        payload = health.read()
        if b'"cve_count"' not in payload:
            raise RuntimeError("Backend health missing cve_count")
        yield FRONTEND_URL
    finally:
        if frontend is not None:
            _terminate(frontend)
        if backend is not None:
            _terminate(backend)


@pytest.fixture(scope="session")
def smoke_auth_cookies(playwright_smoke_stack):
    return _smoke_auth_cookies(BACKEND_URL)


@pytest.fixture
def smoke_page(playwright_smoke_stack, smoke_auth_cookies, browser):
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        color_scheme="dark",
    )
    context.add_cookies(smoke_auth_cookies)
    page = context.new_page()
    page.add_init_script(
        """
        try {
          localStorage.removeItem('briefr_theme');
          document.documentElement.removeAttribute('data-theme');
        } catch {}
        """
    )
    page.goto(playwright_smoke_stack, wait_until="networkidle", timeout=120_000)
    page.wait_for_selector(".header .header-logo-btn", timeout=60_000)
    yield page
    context.close()


@pytest.fixture(scope="session")
def browser():
    if os.environ.get("PLAYWRIGHT_SMOKE") != "1":
        pytest.skip("Set PLAYWRIGHT_SMOKE=1 to run Chromium smoke tests")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(headless=True)
        yield chromium
        chromium.close()
