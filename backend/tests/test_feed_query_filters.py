"""Feed query filter params: severity_list OR and exclude_vendors."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routers.cves.list import _build_cve_filters, _parse_severity_values


def test_parse_severity_values_or_list():
    assert _parse_severity_values(None, "CRITICAL,HIGH") == ["CRITICAL", "HIGH"]


def test_build_cve_filters_severity_list_sql():
    conditions, params, _ = _build_cve_filters(
        None,
        False,
        False,
        False,
        False,
        None,
        None,
        None,
        None,
        severity_list="CRITICAL,HIGH",
    )
    assert "c.severity IN (?, ?)" in conditions
    assert params[:2] == ["CRITICAL", "HIGH"]


def test_build_cve_filters_exclude_vendors_sql():
    conditions, params, _ = _build_cve_filters(
        None,
        False,
        False,
        False,
        False,
        None,
        None,
        None,
        None,
        exclude_vendors="microsoft,linux",
    )
    assert sum(1 for c in conditions if "NOT LIKE" in c) == 2
    assert "%microsoft%" in params
    assert "%linux%" in params


def test_build_cve_filters_search_includes_products():
    conditions, params, _ = _build_cve_filters(
        None,
        False,
        False,
        False,
        False,
        None,
        "apache",
        None,
        None,
    )
    assert any("affected_products" in c for c in conditions)
    assert "%apache%" in params
