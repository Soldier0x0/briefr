"""TM-5: STALE decay (spec §4.1, §9.6 acceptance criterion).

"A fixture record aged past the review window renders STALE and drops out
of all coverage/compliance percentages." Verifies:

- security_architecture.merge.is_stale / annotate_stale pure logic.
- controls_active_ratio excludes stale controls from both numerator and
  denominator (the Overview "Controls Active" tile -- the one real
  percentage a curated record feeds today).
- The router's `/section/{id}` response carries a `stale: bool` on every
  row by default (not only when `?stale=true` is passed), so the frontend
  badge and the percentage math always read the same flag.
- The Overview "Controls Active" ratio, exercised end-to-end through the
  HTTP router with a monkeypatched corpus (same pattern as
  test_security_architecture_shell.py's `_corpus_with` helper).
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import security_architecture.routers.security_architecture as sa_router
from main import app
from security_architecture import merge

TODAY = datetime.date.today()
OLD_DATE = TODAY - datetime.timedelta(days=merge.STALE_WINDOW_DAYS + 10)
RECENT_DATE = TODAY - datetime.timedelta(days=5)


# ── merge.py pure logic ──────────────────────────────────────────────────

def test_is_stale_false_for_generated_records():
    assert merge.is_stale({"origin": "generated", "review_date": OLD_DATE.isoformat()}, today=TODAY) is False


def test_is_stale_false_for_live_records_with_no_review_date():
    assert merge.is_stale({"origin": "live"}, today=TODAY) is False


def test_is_stale_false_for_curated_record_within_window():
    record = {"origin": "curated", "review_date": RECENT_DATE.isoformat()}
    assert merge.is_stale(record, today=TODAY) is False


def test_is_stale_true_for_curated_record_past_window():
    record = {"origin": "curated", "review_date": OLD_DATE.isoformat()}
    assert merge.is_stale(record, today=TODAY) is True


def test_is_stale_handles_unquoted_yaml_date_object():
    """PyYAML parses an unquoted review_date as datetime.date, not str."""
    record = {"origin": "curated", "review_date": OLD_DATE}
    assert merge.is_stale(record, today=TODAY) is True


def test_annotate_stale_adds_flag_to_every_row():
    rows = [
        {"id": "a", "origin": "curated", "review_date": OLD_DATE.isoformat()},
        {"id": "b", "origin": "curated", "review_date": RECENT_DATE.isoformat()},
        {"id": "c", "origin": "live"},
    ]
    annotated = merge.annotate_stale(rows, today=TODAY)
    by_id = {r["id"]: r for r in annotated}
    assert by_id["a"]["stale"] is True
    assert by_id["b"]["stale"] is False
    assert by_id["c"]["stale"] is False


def test_controls_active_ratio_excludes_stale_control_from_both_sides():
    controls = [
        {"id": "fresh-1", "origin": "curated", "review_date": RECENT_DATE.isoformat(), "live_flag": None},
        {"id": "fresh-2", "origin": "curated", "review_date": RECENT_DATE.isoformat(), "live_flag": None},
        {"id": "aged-out", "origin": "curated", "review_date": OLD_DATE.isoformat(), "live_flag": None},
    ]
    ratio = merge.controls_active_ratio(controls)
    # The stale control never appears in the denominator or the numerator --
    # 2 fresh structural controls, both active, out of 2 eligible (not 3).
    assert ratio == {"active": 2, "total": 2, "stale_excluded": 1}


# ── Router integration (monkeypatched corpus, same pattern as
#    test_security_architecture_shell.py) ────────────────────────────────

def _corpus_with_controls(controls):
    return {
        "manifest": {"version": "1", "last_reviewed": "2026-07-13"},
        "components": {"components": []},
        "api_inventory": {"endpoints": []},
        "scheduler_jobs": {"jobs": []},
        "db_tables": {"tables": []},
        "risks": {"risks": []},
        "controls": {"controls": controls},
        "trust_boundaries": {"trust_boundaries": []},
        "abuse_cases": {"abuse_cases": []},
        "threat_scenarios": {"threat_scenarios": []},
        "security_decisions": {"security_decisions": []},
        "reviews": {"reviews": []},
    }


def test_section_controls_response_carries_stale_flag_by_default(monkeypatch):
    """The fixture: one control aged well past the 90-day review window.
    It must render `stale: true` on the *default* read (no ?stale=true
    needed) -- the badge and the percentage math read the same flag."""
    controls = [
        {
            "id": "aged-control", "title": "Aged control", "summary": "x",
            "origin": "curated", "status": "active",
            "review_date": OLD_DATE.isoformat(), "evidence": ["x"], "related_ids": [],
            "live_flag": None,
        },
    ]
    monkeypatch.setattr(sa_router, "get_corpus", lambda: _corpus_with_controls(controls))
    with TestClient(app) as client:
        res = client.get("/api/security-architecture/section/controls")
        assert res.status_code == 200
        body = res.json()
        assert body["count"] == 1
        assert body["items"][0]["stale"] is True


def test_overview_controls_active_tile_excludes_stale_fixture_from_ratio(monkeypatch):
    """End-to-end acceptance check (spec §9.6): a fixture control aged past
    the review window must not count toward either side of the Controls
    Active ratio, while a fresh control still does."""
    controls = [
        {
            "id": "fresh-control", "title": "Fresh control", "summary": "x",
            "origin": "curated", "status": "active",
            "review_date": RECENT_DATE.isoformat(), "evidence": ["x"], "related_ids": [],
            "live_flag": None,
        },
        {
            "id": "aged-control", "title": "Aged control", "summary": "x",
            "origin": "curated", "status": "active",
            "review_date": OLD_DATE.isoformat(), "evidence": ["x"], "related_ids": [],
            "live_flag": None,
        },
    ]
    monkeypatch.setattr(sa_router, "get_corpus", lambda: _corpus_with_controls(controls))
    with TestClient(app) as client:
        res = client.get("/api/security-architecture/overview")
        assert res.status_code == 200
        tile = next(t for t in res.json()["tiles"] if t["id"] == "controls")
        assert tile["value"] == "1/1"


def test_section_stale_filter_isolates_only_the_aged_row(monkeypatch):
    controls = [
        {
            "id": "fresh-control", "title": "Fresh control", "summary": "x",
            "origin": "curated", "status": "active",
            "review_date": RECENT_DATE.isoformat(), "evidence": ["x"], "related_ids": [],
            "live_flag": None,
        },
        {
            "id": "aged-control", "title": "Aged control", "summary": "x",
            "origin": "curated", "status": "active",
            "review_date": OLD_DATE.isoformat(), "evidence": ["x"], "related_ids": [],
            "live_flag": None,
        },
    ]
    monkeypatch.setattr(sa_router, "get_corpus", lambda: _corpus_with_controls(controls))
    with TestClient(app) as client:
        res = client.get("/api/security-architecture/section/controls?stale=true")
        assert res.status_code == 200
        body = res.json()
        assert body["count"] == 1
        assert body["items"][0]["id"] == "aged-control"


def test_stale_endpoint_lists_the_aged_fixture_across_sections(monkeypatch):
    controls = [
        {
            "id": "aged-control", "title": "Aged control", "summary": "x",
            "origin": "curated", "status": "active",
            "review_date": OLD_DATE.isoformat(), "evidence": ["x"], "related_ids": [],
            "live_flag": None,
        },
    ]
    monkeypatch.setattr(sa_router, "get_corpus", lambda: _corpus_with_controls(controls))
    with TestClient(app) as client:
        res = client.get("/api/security-architecture/stale")
        assert res.status_code == 200
        body = res.json()
        assert body["count"] == 1
        assert body["items"][0]["id"] == "aged-control"
        assert body["items"][0]["section"] == "controls"
