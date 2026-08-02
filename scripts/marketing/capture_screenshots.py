#!/usr/bin/env python3
"""Capture portrait UI screenshots for marketing reels (1080x1920)."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "marketing" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORT = {"width": 1080, "height": 1920}


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed — using mockups only", file=sys.stderr)
        return 1

    base = "http://127.0.0.1:5173"
    shots = [
        ("morning-brief.png", f"{base}/?tab=brief"),
        ("cve-feed.png", f"{base}/?tab=feed"),
        ("ioc-lookup.png", f"{base}/?tab=ioc"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=2)
        page.goto(base, wait_until="networkidle", timeout=120_000)
        time.sleep(2)

        for name, url in shots:
            page.goto(url, wait_until="networkidle", timeout=60_000)
            time.sleep(1.5)
            page.screenshot(path=str(OUT / name), full_page=False)
            print(f"Captured {name}")

        # CVE drawer
        page.goto(f"{base}/?tab=feed", wait_until="networkidle")
        time.sleep(1)
        card = page.locator(".cve-card, [data-cve-id], .feed-card").first
        if card.count():
            card.click()
            time.sleep(1.2)
            page.screenshot(path=str(OUT / "cve-detail.png"), full_page=False)
            print("Captured cve-detail.png")

        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
