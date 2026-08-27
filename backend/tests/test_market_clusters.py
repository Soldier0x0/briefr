"""Product clusters for daily brief MARKET (no DB)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reports.market_clusters import (
    cluster_published,
    cluster_weight,
    format_market_section,
    primary_product,
)


def test_primary_product_prefers_first_cpe_product():
    assert primary_product(
        [{"vendor": "f5", "product": "nginx", "version": "1.25"}],
        '["apache:httpd"]',
    ) == "nginx"


def test_primary_product_falls_back_to_affected_products():
    assert primary_product("", '["python:python"]') == "python"
    assert primary_product("[]", '["nginx"]') == "nginx"


def test_primary_product_unanalyzed_when_empty():
    assert primary_product("", "") == "unanalyzed"
    assert primary_product("[]", "[]") == "unanalyzed"


def test_cluster_one_cve_one_bucket_and_merges_same_product():
    rows = [
        {"severity": "CRITICAL", "cpe_matches": '[{"product":"nginx"}]', "affected_products": ""},
        {"severity": "HIGH", "cpe_matches": '[{"vendor":"f5","product":"nginx"}]', "affected_products": ""},
        {"severity": "MEDIUM", "cpe_matches": "", "affected_products": '["oracle:oracle_database"]'},
        {"severity": "LOW", "cpe_matches": "", "affected_products": ""},
    ]
    market = cluster_published(rows)
    assert market["published"] == 4
    assert market["critical"] == 1
    assert market["high"] == 1
    assert market["medium"] == 1
    assert market["low"] == 1
    by_label = {p["label"]: p for p in market["products"]}
    assert by_label["nginx"]["total"] == 2
    assert by_label["nginx"]["critical"] == 1
    assert by_label["nginx"]["high"] == 1
    assert by_label["oracle database"]["total"] == 1
    assert by_label["unanalyzed"]["total"] == 1


def test_weighted_rank_puts_openssl_above_medium_volume():
    rows = []
    for _ in range(40):
        rows.append({"severity": "MEDIUM", "cpe_matches": '[{"product":"windows"}]', "affected_products": ""})
    for _ in range(3):
        rows.append({"severity": "CRITICAL", "cpe_matches": '[{"product":"openssl"}]', "affected_products": ""})
    market = cluster_published(rows)
    assert market["products"][0]["label"] == "openssl"
    assert cluster_weight(3, 0, 0, 0) > cluster_weight(0, 0, 40, 0)


def test_top_eight_and_omitted_count():
    rows = []
    for i in range(12):
        rows.append({
            "severity": "HIGH",
            "cpe_matches": f'[{{"product":"p{i:02d}"}}]',
            "affected_products": "",
        })
    market = cluster_published(rows)
    assert len(market["products"]) == 8
    assert market["omitted_products"] == 4
    assert market["published"] == 12


def test_format_market_section_grammar():
    market = cluster_published([
        {"severity": "CRITICAL", "cpe_matches": '[{"product":"nginx"}]', "affected_products": ""},
    ])
    lines = format_market_section(market)
    assert lines[0] == "// MARKET"
    assert lines[1].startswith("Published: 1")
    assert "• nginx  1  (C 1 · H 0 · M 0 · L 0)" in lines
    assert not any(line.startswith("+") for line in lines)


def test_format_omits_section_when_empty():
    assert format_market_section(cluster_published([])) == []
