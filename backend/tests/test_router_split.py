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
    ("GET", "/api/changes"),
    ("GET", "/api/version"),
    ("GET", "/api/time"),
    ("GET", "/api/stats"),
    ("GET", "/api/stats/timeline"),
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
    ("GET", "/api/cves/{cve_id}/momentum"),
    ("GET", "/api/cves/{cve_id}/detection"),
    ("GET", "/api/cves/{cve_id}/correlation"),
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
    # main.py owns only app wiring now (V1.2 exit criterion: <300 lines)
    assert not any(module == "main" for module in by_path.values())


def test_cve_path_param_route_registered_after_literal_siblings():
    """/api/cves/{cve_id} must not shadow GET /api/cves/export."""
    get_paths = _get_paths()
    assert get_paths.index("/api/cves/export") < get_paths.index(
        "/api/cves/{cve_id}"
    )
