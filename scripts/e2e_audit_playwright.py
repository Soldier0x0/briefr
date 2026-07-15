#!/usr/bin/env python3
"""Exhaustive BRIEFR UI click-map audit — logs every step, no product code changes."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from http import cookiejar
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

FRONTEND = "http://127.0.0.1:5173"
BACKEND = "http://127.0.0.1:8000"
USER = "agentctl"
PASSWORD = "agent-control-test-32bytes!!"
OUT = Path("/opt/cursor/artifacts/e2e-audit-2026-07-15.json")
REPORT = Path("/workspace/docs/planning/specs/e2e-audit-results-2026-07-15.md")


@dataclass
class Step:
    area: str
    action: str
    status: str  # OK | BUG | SKIP | WARN
    detail: str = ""


@dataclass
class Audit:
    steps: list[Step] = field(default_factory=list)

    def log(self, area: str, action: str, status: str, detail: str = "") -> None:
        self.steps.append(Step(area, action, status, detail))
        mark = {"OK": "✓", "BUG": "✗", "SKIP": "−", "WARN": "!"}.get(status, "?")
        print(f"{mark} [{area}] {action}" + (f" — {detail}" if detail else ""))

    def save(self) -> None:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps([asdict(s) for s in self.steps], indent=2))


def auth_cookies() -> list[dict]:
    jar = cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    payload = json.dumps(
        {"username": USER, "password": PASSWORD, "remember_me": True}
    ).encode()
    req = urllib.request.Request(
        f"{BACKEND}/api/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(req, timeout=20):
        pass
    return [
        {
            "name": c.name,
            "value": c.value,
            "domain": "127.0.0.1",
            "path": c.path or "/",
            "httpOnly": True,
            "secure": False,
            "sameSite": "Strict",
        }
        for c in jar
    ]


def dismiss_overlays(page) -> None:
    for sel in [
        'button[aria-label="Close (Escape)"]',
        'button[aria-label="Close drawer (Escape)"]',
        'button.tutorial-close',
        'button[aria-label="Skip"]',
    ]:
        loc = page.locator(sel)
        if loc.count():
            try:
                loc.first.click(timeout=2000)
            except Exception:
                pass
    for _ in range(2):
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)


def safe_click(page, audit: Audit, area: str, action: str, locator, *, timeout=8000, force=False) -> bool:
    try:
        loc = locator.first if hasattr(locator, "first") else locator
        loc.wait_for(state="visible", timeout=timeout)
        loc.click(timeout=timeout, force=force)
        audit.log(area, action, "OK")
        return True
    except PwTimeout as e:
        audit.log(area, action, "BUG", f"timeout: {e}")
        return False
    except Exception as e:
        audit.log(area, action, "BUG", str(e)[:200])
        return False


def dismiss_tutorial(page) -> None:
    page.add_init_script(
        "try{localStorage.setItem('briefr_tutorial_seen','1')}catch{}"
    )


def go_home(page, audit: Audit) -> None:
    page.goto(FRONTEND, wait_until="networkidle", timeout=90_000)
    page.wait_for_selector(".header-logo-btn, .header-nav", timeout=30_000)
    dismiss_overlays(page)
    audit.log("nav", "reset home", "OK")


def goto_tab(page, audit: Audit, tab_text: str) -> None:
    dismiss_overlays(page)
    loc = page.locator("button.header-tab", has_text=tab_text)
    if not loc.count():
        audit.log("nav", f"tab {tab_text}", "BUG", "header tabs not visible (maybe on ARCH route)")
        return
    try:
        loc.first.click(timeout=8000)
        page.wait_for_timeout(500)
        audit.log("nav", f"tab {tab_text}", "OK")
    except Exception as e:
        audit.log("nav", f"tab {tab_text}", "BUG", str(e)[:120])


def main() -> int:
    audit = Audit()
    try:
        run_audit(audit)
    except Exception as e:
        audit.log("fatal", "run aborted", "BUG", str(e)[:300])
    audit.save()
    write_report(audit)
    bugs = sum(1 for s in audit.steps if s.status == "BUG")
    print(f"\nTotal steps: {len(audit.steps)}, BUG: {bugs}, report: {REPORT}")
    return 0


def run_audit(audit: Audit) -> None:
    cookies = auth_cookies()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        ctx.add_cookies(cookies)
        page = ctx.new_page()
        dismiss_tutorial(page)

        # --- Login / load ---
        try:
            page.goto(FRONTEND, wait_until="networkidle", timeout=120_000)
            page.wait_for_selector(".header-logo-btn", timeout=60_000)
            audit.log("auth", "load dashboard", "OK")
        except Exception as e:
            audit.log("auth", "load dashboard", "BUG", str(e))
            return

        if page.locator(".tutorial-overlay").count():
            safe_click(page, audit, "tutorial", "skip", page.get_by_role("button", name="Skip"))

        # --- Global chrome ---
        safe_click(page, audit, "chrome", "logo home", page.locator(".header-logo-btn"))
        page.wait_for_timeout(300)

        safe_click(page, audit, "chrome", "overflow menu", page.get_by_role("button", name="Open menu"))
        if safe_click(page, audit, "chrome", "open About", page.get_by_role("menuitem", name="About")):
            page.wait_for_timeout(300)
            safe_click(page, audit, "chrome", "close About", page.get_by_role("button", name="Close (Escape)"))
        dismiss_overlays(page)
        page.goto(FRONTEND, wait_until="networkidle", timeout=60_000)
        page.wait_for_selector(".header-logo-btn", timeout=30_000)

        safe_click(page, audit, "chrome", "timezone", page.get_by_role("button", name="Select timezone"))
        page.keyboard.press("Escape")

        safe_click(page, audit, "chrome", "notifications", page.get_by_role("button", name="Notifications"))
        page.keyboard.press("Escape")

        safe_click(page, audit, "chrome", "account menu", page.get_by_role("button", name=f"Account menu for {USER}"))
        dismiss_overlays(page)

        # --- BRIEF ---
        go_home(page, audit)
        goto_tab(page, audit, "BRIEF")
        dismiss_overlays(page)
        for chip in page.locator(".morning-brief-filter-chip").all()[:5]:
            try:
                label = chip.inner_text().strip()
                chip.click()
                audit.log("brief", f"filter {label}", "OK")
            except Exception as e:
                audit.log("brief", "filter chip", "BUG", str(e)[:100])

        dismiss_overlays(page)
        if page.locator(".morning-brief-row-btn").count():
            safe_click(page, audit, "brief", "open brief row", page.locator(".morning-brief-row-btn").first, force=True)
            try:
                page.wait_for_selector(".drawer-panel-open", timeout=15_000)
                audit.log("brief", "drawer opened from brief", "OK")
                safe_click(page, audit, "brief", "close drawer", page.get_by_role("button", name="Close drawer (Escape)"))
            except PwTimeout:
                audit.log("brief", "drawer opened from brief", "BUG", "no drawer")

        # Analyst charts
        try:
            exp = page.locator(".brief-charts summary, .brief-charts details summary").first
            if exp.count():
                exp.click(timeout=5000)
                audit.log("brief", "expand charts", "OK")
        except Exception as e:
            audit.log("brief", "expand charts", "WARN", str(e)[:80])

        for label in page.locator(".brief-chart-card-title").all():
            audit.log("brief", f"chart visible: {label.inner_text()[:40]}", "OK")
        safe_click(page, audit, "brief", "epss window picker", page.locator(".brief-epss-window button, .time-window-picker button").first)

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        audit.log("brief", "scroll page", "OK")

        # --- FEED ---
        go_home(page, audit)
        goto_tab(page, audit, "FEED")
        for qf in ["ALL", "WATCHLIST", "KEV", "CRITICAL", "HIGH", "MEDIUM", "PoC", "KEV OVERDUE"]:
            safe_click(
                page,
                audit,
                "feed",
                f"quick filter {qf}",
                page.get_by_role("button", name=f"Filter: {qf}", exact=True),
            )

        for tid in ["toggle-kev", "toggle-poc", "toggle-epss", "toggle-my-stack"]:
            el = page.locator(f"#{tid}")
            if el.count():
                safe_click(page, audit, "feed-sidebar", f"toggle {tid}", el)
            else:
                audit.log("feed-sidebar", f"toggle {tid}", "SKIP", "not in DOM")

        if page.locator(".cve-card, .cve-feed .cve-card").count():
            safe_click(page, audit, "feed", "open cve card", page.locator(".cve-card").first)
            page.wait_for_selector(".drawer-panel-open", timeout=30_000)
            page.wait_for_selector(".drawer-loading-overlay", state="hidden", timeout=60_000)
            audit.log("drawer", "opened from feed", "OK")

            drawer = page.locator(".drawer-panel-open")
            for tab in ["OVERVIEW", "INTEL", "DETECT", "RELATED"]:
                safe_click(
                    page,
                    audit,
                    "drawer",
                    f"tab {tab}",
                    drawer.get_by_role("tab", name=tab, exact=True),
                )
                page.wait_for_timeout(600)
                page.evaluate(
                    """() => {
                      const p = document.querySelector('.drawer-panel-open .drawer-body, .drawer-scroll');
                      if (p) p.scrollTop = p.scrollHeight;
                    }"""
                )

            for btn in ["Pin", "Start investigation", "Close drawer (Escape)"]:
                if btn == "Pin":
                    loc = drawer.get_by_role("button", name="Pin").or_(drawer.get_by_role("button", name="Unpin"))
                else:
                    loc = drawer.get_by_role("button", name=btn)
                if loc.count():
                    if btn != "Close drawer (Escape)":
                        safe_click(page, audit, "drawer", btn, loc.first, force=True)
                    else:
                        safe_click(page, audit, "drawer", btn, loc)

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        audit.log("feed", "scroll feed", "OK")

        # --- IOC ---
        go_home(page, audit)
        goto_tab(page, audit, "IOC LOOKUP")
        inp = page.locator("#ioc-value-input")
        if inp.count():
            inp.fill("8.8.8.8")
            safe_click(page, audit, "ioc", "lookup", page.get_by_role("button", name="Lookup"))
            page.wait_for_timeout(2000)
            audit.log("ioc", "results rendered", "OK" if page.locator(".ioc-lookup-results, .threat-bar-section").count() else "WARN", "check enrichment")
            inp.fill("")
            inp.fill("not-valid!!!")
            safe_click(page, audit, "ioc", "invalid lookup", page.get_by_role("button", name="Lookup"))

        # --- INCIDENTS ---
        go_home(page, audit)
        goto_tab(page, audit, "INCIDENTS")
        try:
            page.wait_for_selector(".cs-hero, .cs-card, .cs-empty", timeout=60_000)
            n = page.locator(".cs-card").count()
            audit.log("incidents", f"cards visible: {n}", "OK" if n else "WARN")
            if n:
                safe_click(page, audit, "incidents", "open case card", page.locator(".cs-card").first)
                page.wait_for_timeout(800)
                page.keyboard.press("Escape")
        except PwTimeout as e:
            audit.log("incidents", "load tab", "BUG", str(e)[:120])

        # --- FORGE ---
        go_home(page, audit)
        goto_tab(page, audit, "FORGE")
        for view, label in [
            ("coverage", "Coverage map"),
            ("scenarios", "Threat scenarios"),
            ("campaigns", "Campaigns"),
            ("backlog", "Backlog"),
            ("library", "Library"),
        ]:
            safe_click(page, audit, "forge", f"view {view}", page.get_by_role("tab", name=label))
            page.wait_for_timeout(500)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

        # Library controls
        go_home(page, audit)
        goto_tab(page, audit, "FORGE")
        safe_click(page, audit, "forge", "library tab", page.get_by_role("tab", name="Library"))
        for cb in page.locator(".data-grid-toggle").all()[:2]:
            try:
                cb.click()
                audit.log("forge-library", "grid toggle", "OK")
            except Exception as e:
                audit.log("forge-library", "grid toggle", "BUG", str(e)[:120])

        # --- ARCH ---
        page.goto(f"{FRONTEND}/security-architecture", wait_until="networkidle", timeout=60_000)
        links = page.locator(".sa-nav-btn").all()
        section_names = []
        for link in links:
            try:
                txt = (link.inner_text() or "").strip()
                if txt and txt not in section_names:
                    section_names.append(txt)
                    link.click()
                    page.wait_for_timeout(700)
                    audit.log("arch", f"section {txt}", "OK")
                    # wrap toggle if present
                    wrap = page.locator("text=Wrap").first
                    if wrap.count():
                        wrap.click()
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception as e:
                audit.log("arch", f"section click", "BUG", str(e)[:120])

        # Graph controls
        if page.get_by_role("button", name="RESET VIEW").count():
            safe_click(page, audit, "arch-graph", "reset view", page.get_by_role("button", name="RESET VIEW"))

        # --- Admin ---
        page.goto(f"{FRONTEND}/admin", wait_until="networkidle", timeout=60_000)
        if "/admin" in page.url:
            audit.log("admin", "route loaded", "OK")
            # Analyst pages first
            for link in page.locator(".admin-sidebar button, .admin-sidebar a").all():
                try:
                    txt = (link.inner_text() or "").strip().split("\n")[0]
                    if not txt or "switch" in txt.lower():
                        continue
                    link.click()
                    page.wait_for_timeout(600)
                    audit.log("admin-analyst", f"page {txt[:50]}", "OK")
                except Exception as e:
                    audit.log("admin-analyst", "sidebar nav", "BUG", str(e)[:120])
            # Operator mode
            op = page.get_by_role("button", name="Operator")
            if op.count():
                op.first.click()
                page.wait_for_timeout(800)
                audit.log("admin", "operator mode", "OK")
                for link in page.locator(".admin-sidebar button, .admin-sidebar a").all():
                    try:
                        txt = (link.inner_text() or "").strip().split("\n")[0]
                        if not txt or "switch" in txt.lower():
                            continue
                        link.click()
                        page.wait_for_timeout(600)
                        audit.log("admin-operator", f"page {txt[:50]}", "OK")
                    except Exception as e:
                        audit.log("admin-operator", "sidebar nav", "BUG", str(e)[:120])
        else:
            audit.log("admin", "route loaded", "BUG", f"url={page.url}")

        # --- Static routes ---
        for path in ["/wallboard", "/privacy", "/terms"]:
            page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=30_000)
            audit.log("static", path, "OK" if page.locator("body").inner_text().strip() else "BUG")

        ctx.close()
        browser.close()


def write_report(audit: Audit) -> None:
    bugs = [s for s in audit.steps if s.status == "BUG"]
    warns = [s for s in audit.steps if s.status == "WARN"]
    oks = [s for s in audit.steps if s.status == "OK"]
    lines = [
        "# E2E audit results — 2026-07-15",
        "",
        f"**Method:** Playwright systematic click-map (headless, auth as `{USER}`).",
        f"**Steps:** {len(audit.steps)} total · {len(oks)} OK · {len(warns)} WARN · {len(bugs)} BUG",
        f"**Raw log:** `{OUT}`",
        "",
        "## Coverage note",
        "",
        "This pass automates every main-nav tab, FEED quick filters, sidebar toggles, drawer tabs,",
        "FORGE sub-views, ARCH sidebar sections, admin sidebar pages, and static routes.",
        "It does not replace human visual review for color/spacing — see post-ui-audit plan for those.",
        "",
        "## Bugs / failures",
        "",
    ]
    if not bugs:
        lines.append("_None recorded in automated pass._")
    else:
        for s in bugs:
            lines.append(f"- **[{s.area}]** {s.action}: {s.detail}")
    lines.extend(["", "## Warnings", ""])
    for s in warns:
        lines.append(f"- **[{s.area}]** {s.action}: {s.detail}")
    lines.extend(["", "## Full step log", "", "| Status | Area | Action | Detail |", "|--------|------|--------|--------|"])
    for s in audit.steps:
        d = s.detail.replace("|", "\\|")
        lines.append(f"| {s.status} | {s.area} | {s.action} | {d} |")
    REPORT.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
