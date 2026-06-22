"""Shared pytest fixtures — Playwright smoke stack when PLAYWRIGHT_SMOKE=1."""

from __future__ import annotations

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
