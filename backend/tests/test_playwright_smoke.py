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


def _feed_tab_visible(page) -> bool:
    """True when the FEED tab panel is shown (not merely mounted with hidden)."""
    return page.evaluate(
        """
        () => {
          const feed = document.querySelector('.cve-feed');
          if (!feed) return false;
          const panel = feed.closest('.app-tab-panel');
          return panel ? !panel.hidden : feed.offsetParent !== null;
        }
        """
    )


def _open_full_feed(page) -> None:
    """BRIEF tab is default — switch to the CVE feed when cards are only on FEED."""
    link = page.get_by_role("button", name="Open full feed →")
    if link.count() > 0:
        link.first.click()
    else:
        page.get_by_role("button", name="Switch to full CVE feed").click()
    page.wait_for_selector(".cve-feed", timeout=30_000)
    _poll(
        page,
        """
        () => {
          const feed = document.querySelector('.cve-feed');
          const panel = feed?.closest('.app-tab-panel');
          return feed && panel && !panel.hidden;
        }
        """,
    )


def _wait_for_brief_cards(page) -> int:
    page.wait_for_selector(".morning-brief, .stats-row, .cve-feed", timeout=60_000)
    _poll(
        page,
        """
        () => {
          const brief = document.querySelector('.morning-brief');
          if (!brief) return !!document.querySelector('.cve-feed .cve-card');
          return !document.querySelector('.morning-brief-loading');
        }
        """,
    )
    count = page.evaluate(
        "document.querySelectorAll('.morning-brief-row, .cve-feed .cve-card').length"
    )
    if count < 1:
        _open_full_feed(page)
        _poll(
            page,
            "() => document.querySelectorAll('.cve-feed .cve-card').length > 0",
        )
        count = page.evaluate("document.querySelectorAll('.cve-feed .cve-card').length")
    return count


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
    if not _feed_tab_visible(smoke_page):
        _open_full_feed(smoke_page)
    _poll(
        smoke_page,
        """
        () => {
          window.scrollTo(0, document.body.scrollHeight);
          const feed = document.querySelector('.cve-feed');
          return feed ? feed.getBoundingClientRect().top < -100 : false;
        }
        """,
        timeout=10.0,
    )

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

    smoke_page.get_by_role("button", name="Filter: KEV", exact=True).click()
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
    row = smoke_page.locator(".morning-brief-row-btn, .cve-card").first
    row_label = row.get_attribute("aria-label")
    assert row_label

    row.click()
    smoke_page.wait_for_selector(".drawer-panel-open", timeout=30_000)

    smoke_page.get_by_role("button", name="Close drawer (Escape)").click()
    smoke_page.wait_for_selector(".drawer-panel-open", state="detached", timeout=30_000)

    focused_label = smoke_page.evaluate(
        "() => document.activeElement?.getAttribute('aria-label') || ''"
    )
    assert focused_label == row_label


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
