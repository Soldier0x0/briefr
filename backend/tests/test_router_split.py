"""V1.2 §5.2 router split: the OpenAPI route list (method, path, order)
must be byte-identical to the pre-split monolithic main.py."""

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.routing import APIRoute

from main import app

# Snapshot of the pre-split route list (order included — FastAPI matches in
# registration order, and /api/cves/{cve_id} must stay after its siblings).
EXPECTED_ROUTES = [
    ("POST", "/api/refresh"),
    ("POST", "/api/refresh/nvd"),
    ("POST", "/api/refresh/kev"),
    ("POST", "/api/refresh/epss"),
    ("POST", "/api/refresh/mitre"),
    ("GET", "/api/health"),
    ("GET", "/api/health/live"),
    ("GET", "/api/changes"),
    ("GET", "/api/version"),
    ("GET", "/api/time"),
    ("GET", "/api/stats"),
    ("GET", "/api/stats/timeline"),
    ("GET", "/api/stats/top-vendors"),
    ("GET", "/api/cves"),
    ("POST", "/api/cves/match"),
    ("GET", "/api/cves/export"),
    ("GET", "/api/techniques/top"),
    ("GET", "/api/atlas/techniques"),
    ("GET", "/api/case-studies/news"),
    ("GET", "/api/case-studies/feed"),
    ("GET", "/api/atlas/casestudies"),
    ("GET", "/api/cves/{cve_id}/sentences"),
    ("GET", "/api/cves/{cve_id}/epss-history"),
    ("GET", "/api/cves/{cve_id}/related"),
    ("GET", "/api/cves/{cve_id}"),
    ("GET", "/api/otx/pulses/{pulse_id}/iocs"),
    ("POST", "/api/ioc/lookup"),
    ("GET", "/api/ioc/watchlist"),
    ("POST", "/api/ioc/watchlist"),
    ("DELETE", "/api/ioc/watchlist/{entry_id}"),
    ("POST", "/api/cves/{cve_id}/risk"),
    ("GET", "/api/cves/{cve_id}/momentum"),
    ("GET", "/api/cves/{cve_id}/detection"),
    ("GET", "/api/cves/{cve_id}/correlation"),
    ("GET", "/api/cves/{cve_id}/greynoise-scans"),
    ("GET", "/api/cves/{cve_id}/correlation/suppressions"),
    ("POST", "/api/cves/{cve_id}/correlation/suppress"),
    ("DELETE", "/api/cves/{cve_id}/correlation/suppress"),
    ("GET", "/api/kev/deadlines"),
    ("GET", "/api/usage"),
    ("GET", "/api/usage/ioc"),
    ("GET", "/api/ai/summary"),
    ("POST", "/api/ai/summary"),
    ("POST", "/api/investigation/summary"),
    ("GET", "/api/config/risk"),
    # Forge MVP (V1.3): coverage map + hunt packs, appended after the
    # pre-split snapshot — additive only, original order untouched.
    ("GET", "/api/forge/coverage"),
    ("POST", "/api/hunt-packs/generate"),
    ("GET", "/api/hunt-packs/{technique_id}"),
    ("GET", "/api/threat-model/scenarios"),
    ("POST", "/api/proof/run"),
    ("GET", "/api/detection-backlog"),
    ("POST", "/api/detection-backlog/{item_id}/dismiss"),
    # V1.3 Theme 1: morning brief (additive, appended after Forge routes).
    ("GET", "/api/brief"),
    # Correlation Phase 4: cluster list (additive, appended after brief routes).
    ("GET", "/api/correlation/clusters"),
    # Watchlist (V1.3): pin/snooze — additive, appended after brief routes.
    ("GET", "/api/watchlist"),
    ("POST", "/api/watchlist"),
    ("DELETE", "/api/watchlist/snoozes"),
    ("DELETE", "/api/watchlist/{cve_id}"),
    # Admin dashboard (V1.4): appended after watchlist routes.
    ("GET", "/api/admin/system"),
    ("GET", "/api/admin/correlation/status"),
    ("GET", "/api/admin/backups"),
    ("POST", "/api/admin/backups/verify/{filename}"),
    ("POST", "/api/admin/backups/run"),
    ("POST", "/api/admin/backups/upload"),
    ("GET", "/api/admin/storage"),
    ("GET", "/api/admin/destructive-actions"),
    ("POST", "/api/admin/storage/purge"),
    ("GET", "/api/admin/storage/export"),
    ("GET", "/api/admin/watchlist"),
    ("DELETE", "/api/admin/watchlist/{cve_id}"),
    ("POST", "/api/admin/watchlist/clear-snoozes"),
    ("GET", "/api/admin/hunt-packs"),
    ("DELETE", "/api/admin/hunt-packs/{pack_id}"),
    ("GET", "/api/admin/ioc-cache"),
    ("DELETE", "/api/admin/ioc-cache/{value}"),
    ("GET", "/api/admin/config"),
    ("POST", "/api/admin/config"),
    ("GET", "/api/admin/config/schema"),
    ("POST", "/api/admin/config/apply-all"),
    ("POST", "/api/admin/config/webhook-test"),
    ("GET", "/api/admin/webhooks/destinations"),
    ("PATCH", "/api/admin/webhooks/destinations/{destination_id}"),
    ("GET", "/api/admin/database"),
    ("POST", "/api/admin/database/test-connection"),
    ("POST", "/api/admin/database/migrate"),
    ("GET", "/api/admin/database/migrate/status"),
    ("GET", "/api/admin/scheduler"),
    ("POST", "/api/admin/scheduler/pause"),
    ("POST", "/api/admin/scheduler/resume"),
    ("POST", "/api/admin/scheduler/pause-all"),
    ("POST", "/api/admin/scheduler/resume-all"),
    ("GET", "/api/admin/scheduler/history"),
    ("POST", "/api/admin/scheduler/run"),
    ("POST", "/api/admin/feeds/{source_id}/reset-circuit"),
    ("POST", "/api/admin/incidents/refresh"),
    ("GET", "/api/admin/webhooks/log"),
    ("GET", "/api/admin/webhooks/delivery-log"),
    ("GET", "/api/admin/logs"),
    ("GET", "/api/admin/security"),
    ("POST", "/api/admin/restart"),
    ("GET", "/api/admin/audit-log"),
    ("POST", "/api/admin/diagnostics/smoke"),
    ("POST", "/api/admin/diagnostics/integrity"),
    ("GET", "/api/admin/diagnostics/support-pack"),
    ("GET", "/api/admin/onboarding"),
    ("POST", "/api/admin/onboarding/dismiss"),
    # Rate-limit admin page: appended after diagnostics routes.
    ("GET", "/api/admin/ratelimit"),
    # V1.4 Theme 4: read-only wallboard (additive, after admin routes).
    ("GET", "/api/wallboard"),
    # Built-in app login (decision 2026-06-11): appended after wallboard
    # routes — additive only.
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/refresh"),
    ("GET", "/api/auth/me"),
    # First-run setup flow (decision 2026-06-22): appended after the
    # original auth routes — additive only.
    ("GET", "/api/auth/setup-required"),
    ("POST", "/api/auth/setup"),
    # Session management (admin sessions page): appended after setup routes.
    ("GET", "/api/auth/sessions"),
    ("DELETE", "/api/auth/sessions/{session_id}"),
    # Per-user stack profile (Wave 2 PR 3): appended after auth routes.
    ("GET", "/api/me/stack"),
    ("PUT", "/api/me/stack"),
    ("GET", "/api/me/preferences"),
    ("PATCH", "/api/me/preferences"),
]


def _openapi_route_list() -> list[tuple[str, str]]:
    spec = app.openapi()
    return [
        (method.upper(), path)
        for path, methods in spec["paths"].items()
        for method in methods
    ]


def _iter_route_contexts(routes: list[Any]) -> Iterator[Any]:
    """Flatten FastAPI 0.137+ nested included-router trees for introspection."""
    for route in routes:
        effective_route_contexts = getattr(route, "effective_route_contexts", None)
        if callable(effective_route_contexts):
            yield from effective_route_contexts()
        elif isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "endpoint"):
            yield route


def _routes_by_path() -> dict[str, str]:
    return {
        ctx.path: ctx.endpoint.__module__
        for ctx in _iter_route_contexts(app.routes)
        if hasattr(ctx, "endpoint")
    }


def _get_paths() -> list[str]:
    return [
        ctx.path
        for ctx in _iter_route_contexts(app.routes)
        if "GET" in getattr(ctx, "methods", set())
    ]


def test_route_list_identical_to_pre_split_snapshot():
    assert _openapi_route_list() == EXPECTED_ROUTES


def test_moved_endpoints_live_in_routers():
    """All endpoint handlers come from routers/, none remain in main."""
    by_path = _routes_by_path()
    assert by_path["/api/health"] == "routers.health"
    assert by_path["/api/health/live"] == "routers.health"
    assert by_path["/api/atlas/techniques"] == "routers.atlas"
    assert by_path["/api/case-studies/feed"] == "routers.atlas"
    assert by_path["/api/atlas/casestudies"] == "routers.atlas"
    assert by_path["/api/case-studies/news"] == "routers.atlas"
    assert by_path["/api/ioc/lookup"] == "routers.ioc"
    assert by_path["/api/otx/pulses/{pulse_id}/iocs"] == "routers.ioc"
    # Phase 3: cves + meta groups
    assert by_path["/api/changes"] == "routers.cves"
    assert by_path["/api/cves"] == "routers.cves"
    assert by_path["/api/cves/export"] == "routers.cves"
    assert by_path["/api/cves/{cve_id}"] == "routers.cves"
    assert by_path["/api/cves/{cve_id}/detection"] == "routers.cves"
    assert by_path["/api/kev/deadlines"] == "routers.cves"
    assert by_path["/api/version"] == "routers.meta"
    assert by_path["/api/time"] == "routers.meta"
    assert by_path["/api/usage"] == "routers.meta"
    assert by_path["/api/investigation/summary"] == "routers.meta"
    assert by_path["/api/refresh"] == "routers.refresh"
    assert by_path["/api/config/risk"] == "routers.config"
    assert by_path["/api/brief"] == "routers.brief"
    assert by_path["/api/threat-model/scenarios"] == "routers.threat_model"
    assert by_path["/api/proof/run"] == "routers.proof"
    assert by_path["/api/detection-backlog"] == "routers.detection_backlog"
    assert by_path["/api/ioc/watchlist"] == "routers.ioc"
    assert by_path["/api/watchlist"] == "routers.watchlist"
    assert by_path["/api/admin/system"] == "routers.admin"
    # main.py owns only app wiring now (V1.2 exit criterion: <300 lines)
    assert not any(module == "main" for module in by_path.values())


def test_cve_path_param_route_registered_after_literal_siblings():
    """/api/cves/{cve_id} must not shadow GET /api/cves/export."""
    get_paths = _get_paths()
    assert get_paths.index("/api/cves/export") < get_paths.index(
        "/api/cves/{cve_id}"
    )
