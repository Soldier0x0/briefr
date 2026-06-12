"""Chromium-only UI smoke against seeded data (HANDOVER §5.7).

Skipped unless PLAYWRIGHT_SMOKE=1 — regular `pytest tests/ -q` stays fast.
"""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.playwright_smoke


def _poll(page, js: str, *, timeout: float = 120.0, interval: float = 0.25) -> None:
    """Poll page.evaluate until a truthy result (avoids CSP-blocked wait_for_function)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if page.evaluate(js):
                return
        except Exception:  # noqa: BLE001 — transient navigation/context errors
            pass
        time.sleep(interval)
    raise TimeoutError(f"Timed out polling: {js[:80]}...")


def _wait_for_brief_cards(page) -> int:
    page.wait_for_selector(".morning-brief, .stats-row, .cve-feed-list", timeout=60_000)
    _poll(
        page,
        """
        () => {
          const briefCards = document.querySelectorAll('.morning-brief .cve-card').length;
          const feedCards = document.querySelectorAll('.cve-feed-list .cve-card').length;
          return briefCards > 0 || feedCards > 0;
        }
        """,
    )
    return page.evaluate(
        "document.querySelectorAll('.morning-brief .cve-card, .cve-feed-list .cve-card').length"
    )


def _wait_for_incidents_cards(page) -> int:
    page.wait_for_selector(".cs-hero", timeout=60_000)
    _poll(
        page,
        """
        () => {
          const cards = document.querySelectorAll('.cs-card');
          const skeleton = document.querySelector('.cs-skeleton-list');
          const hasError = !!document.querySelector('.cs-source-error');
          const isEmpty = !!document.querySelector('.cs-empty');
          return (cards.length > 0 && !skeleton) || hasError || isEmpty;
        }
        """,
    )
    state = page.evaluate(
        """
        () => {
          const errors = [...document.querySelectorAll('.cs-source-error')]
            .map(el => el.textContent.trim());
          const empty = document.querySelector('.cs-empty');
          return {
            errors,
            empty: empty?.textContent?.trim() || null,
            cardCount: document.querySelectorAll('.cs-card').length,
          };
        }
        """
    )
    locked = [msg for msg in state["errors"] if "database is locked" in msg.lower()]
    assert not locked, f"Incidents tab database lock: {locked}"
    # Per-source RSS failures are surfaced in the UI but must not fail the tab
    # when other sources still produced cards (graceful degradation).
    if state["cardCount"] > 0:
        return state["cardCount"]
    assert not state["errors"], f"Incidents feed errors: {state['errors']}"
    assert not state["empty"], state["empty"] or "Incidents tab empty"
    assert state["cardCount"] > 0, "Incidents tab has no cards"
    return state["cardCount"]


def test_brief_renders_cve_cards(smoke_page):
    count = _wait_for_brief_cards(smoke_page)
    assert count >= 1


def test_filter_click_anchors_to_feed(smoke_page):
    """Quick-filter scroll anchor regression (PR #90 feed UX)."""
    _wait_for_brief_cards(smoke_page)
    smoke_page.get_by_role("button", name="Switch to full CVE feed").click()
    smoke_page.wait_for_selector(".cve-feed", timeout=30_000)
    smoke_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    smoke_page.wait_for_timeout(300)

    feed_top_before = smoke_page.evaluate(
        """
        () => {
          const feed = document.querySelector('.cve-feed');
          return feed ? feed.getBoundingClientRect().top : null;
        }
        """
    )
    assert feed_top_before is not None
    assert feed_top_before < -100, "Feed should start well above viewport before filter click"

    smoke_page.get_by_role("button", name="Filter: KEV").click()
    _poll(smoke_page, "() => !document.querySelector('.feed-refreshing')", timeout=30.0)

    feed_top_after = smoke_page.evaluate(
        """
        () => {
          const feed = document.querySelector('.cve-feed');
          return feed ? feed.getBoundingClientRect().top : null;
        }
        """
    )
    viewport_h = smoke_page.evaluate("window.innerHeight")
    assert feed_top_after is not None
    assert feed_top_after > feed_top_before + 200, "Filter click should scroll feed into view"
    assert feed_top_after < viewport_h * 0.75, "Feed should land in the upper viewport"


def test_drawer_opens_closes_with_focus_restore(smoke_page):
    _wait_for_brief_cards(smoke_page)
    card = smoke_page.locator(".cve-card").first
    card_label = card.get_attribute("aria-label")
    assert card_label

    card.click()
    smoke_page.wait_for_selector(".drawer-panel-open", timeout=30_000)

    smoke_page.get_by_role("button", name="Close drawer (Escape)").click()
    smoke_page.wait_for_selector(".drawer-panel-open", state="detached", timeout=30_000)

    focused_label = smoke_page.evaluate(
        "() => document.activeElement?.getAttribute('aria-label') || ''"
    )
    assert focused_label == card_label


def test_ioc_tab_accepts_input(smoke_page):
    smoke_page.get_by_role("button", name="Switch to IOC lookup").click()
    field = smoke_page.locator("#ioc-value-input")
    field.wait_for(state="visible", timeout=30_000)
    field.fill("8.8.8.8")
    assert field.input_value() == "8.8.8.8"


def test_incidents_renders_cards(smoke_page):
    smoke_page.get_by_role("button", name="Switch to incidents and news").click()
    count = _wait_for_incidents_cards(smoke_page)
    assert count >= 1
