"""CPE version range matching for asset profile scoring."""

from matching.cpe import (
    product_keys_match,
    score_asset_against_cpe,
    score_cve_for_assets,
    version_in_range,
)


def test_version_in_range_end_excluding():
    assert version_in_range("2.14.1", end_excluding="2.15.0") is True
    assert version_in_range("2.15.0", end_excluding="2.15.0") is False
    assert version_in_range("2.16.0", end_excluding="2.15.0") is False


def test_version_in_range_start_including():
    assert version_in_range("9.0", start_including="9.0", end_excluding="10.0") is True
    assert version_in_range("8.9", start_including="9.0") is False


def test_version_in_range_ignores_wildcard_bounds():
    assert version_in_range("2.14.1", end_excluding="*") is True
    assert version_in_range("2.14.1", end_excluding="-") is True
    assert version_in_range("2.14.1", start_including="*") is True
    assert version_in_range("2.14.1", end_including="  *  ") is True


def test_product_keys_match_vendor_product():
    assert product_keys_match("http_server", "apache", "apache", "http_server")
    assert product_keys_match("nginx", None, "nginx", "nginx")
    assert not product_keys_match("mysql", "oracle", "postgresql", "postgresql")


def test_product_keys_match_rejects_vendor_mismatch_substring():
    assert not product_keys_match("sql", "microsoft", "oracle", "mysql")
    assert not product_keys_match("ab", "vendor", "vendor", "xabcd")


def test_product_keys_match_allows_substring_with_min_length():
    assert product_keys_match("tomcat", "apache", "apache", "apache_tomcat")


def test_score_asset_exact_version_match():
    asset = {"product": "http_server", "version": "2.4.52", "vendor": "apache"}
    cpe = {
        "vendor": "apache",
        "product": "http_server",
        "version_start_including": "2.4.0",
        "version_end_excluding": "2.4.53",
    }
    assert score_asset_against_cpe(asset, cpe) == 100


def test_score_asset_rejects_mismatched_cpe_version():
    asset = {"product": "nginx", "version": "1.21.0", "vendor": "nginx"}
    cpe = {"vendor": "nginx", "product": "nginx", "version": "1.20.0"}
    assert score_asset_against_cpe(asset, cpe) is None


def test_score_asset_matches_specific_cpe_version():
    asset = {"product": "nginx", "version": "1.20.0", "vendor": "nginx"}
    cpe = {"vendor": "nginx", "product": "nginx", "version": "1.20.0"}
    assert score_asset_against_cpe(asset, cpe) == 100


def test_score_asset_without_version_partial():
    asset = {"product": "nginx", "version": "", "vendor": "nginx"}
    cpe = {"vendor": "nginx", "product": "nginx"}
    assert score_asset_against_cpe(asset, cpe) == 55


def test_score_cve_for_assets_best_score():
    assets = [{"product": "nginx", "version": "1.20.0", "vendor": "nginx"}]
    cpe_matches = [
        {
            "vendor": "nginx",
            "product": "nginx",
            "version_start_including": "1.0",
            "version_end_excluding": "1.21.0",
        },
        {
            "vendor": "apache",
            "product": "http_server",
            "version_start_including": "2.4.0",
        },
    ]
    assert score_cve_for_assets(cpe_matches, assets) == 100
