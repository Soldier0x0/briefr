"""CPE-based stack matching for alerts (no description LIKE)."""

from matching.stack_assets import assets_to_terms, cve_matches_assets, profile_to_assets, terms_to_assets


def test_blank_version_matches_any_cpe_version():
    assets = [{"product": "nginx", "vendor": "", "version": ""}]
    cpes = [{"vendor": "f5", "product": "nginx", "version": "1.25.0"}]
    assert cve_matches_assets(cpes, [], assets) is True


def test_set_version_respects_cpe_range():
    assets = [{"product": "nginx", "vendor": "f5", "version": "1.24.0"}]
    in_range = [{
        "vendor": "f5",
        "product": "nginx",
        "version": "*",
        "version_end_excluding": "1.25.0",
    }]
    out_of_range = [{
        "vendor": "f5",
        "product": "nginx",
        "version": "*",
        "version_end_excluding": "1.20.0",
    }]
    assert cve_matches_assets(in_range, [], assets) is True
    assert cve_matches_assets(out_of_range, [], assets) is False


def test_does_not_match_description_text():
    assets = [{"product": "nginx", "vendor": "", "version": ""}]
    assert cve_matches_assets([], [], assets) is False
    assert cve_matches_assets(
        [],
        ["apache:httpd"],
        assets,
    ) is False


def test_affected_products_structured_match():
    assets = [{"product": "nginx", "vendor": "", "version": ""}]
    assert cve_matches_assets([], ["f5:nginx"], assets) is True


def test_profile_and_terms_to_assets():
    profile = {
        "operatingSystems": [{"product": "linux", "vendor": "", "version": "6.1"}],
        "applications": [{"product": "nginx", "vendor": "f5", "version": ""}],
    }
    assets = profile_to_assets(profile)
    assert len(assets) == 2
    assert terms_to_assets("apache, python") == [
        {"product": "apache", "vendor": "", "version": ""},
        {"product": "python", "vendor": "", "version": ""},
    ]
    assert assets_to_terms(assets) == ["linux", "nginx"]
