"""V1.2 §5.2 router split: the OpenAPI route list (method, path, order)
must be byte-identical to the pre-split monolithic main.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
]


def _openapi_route_list() -> list[tuple[str, str]]:
    spec = app.openapi()
    return [
        (method.upper(), path)
        for path, methods in spec["paths"].items()
        for method in methods
    ]


def test_route_list_identical_to_pre_split_snapshot():
    assert _openapi_route_list() == EXPECTED_ROUTES


def test_moved_endpoints_live_in_routers():
    """Health, ATLAS, and IOC handlers come from routers/, not main."""
    by_path = {
        route.path: route.endpoint.__module__
        for route in app.routes
        if hasattr(route, "endpoint")
    }
    assert by_path["/api/health"] == "routers.health"
    assert by_path["/api/atlas/techniques"] == "routers.atlas"
    assert by_path["/api/case-studies/feed"] == "routers.atlas"
    assert by_path["/api/atlas/casestudies"] == "routers.atlas"
    assert by_path["/api/case-studies/news"] == "routers.atlas"
    assert by_path["/api/ioc/lookup"] == "routers.ioc"
    assert by_path["/api/otx/pulses/{pulse_id}/iocs"] == "routers.ioc"
