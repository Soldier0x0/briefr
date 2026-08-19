import pytest

from investigations.resolve import parse_investigation_query


def test_parse_cve():
    ref = parse_investigation_query("cve-2024-1234")
    assert ref.entity_type == "cve"
    assert ref.entity_id == "CVE-2024-1234"


def test_parse_sha256():
    q = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ref = parse_investigation_query(q)
    assert ref.entity_type == "ioc"
    assert ref.entity_id.startswith("hash:")


def test_parse_rejects_empty():
    with pytest.raises(ValueError):
        parse_investigation_query("  ")


def test_parse_campaign_id_and_prefix():
    ref = parse_investigation_query("camp_ab12cd34ef56")
    assert ref.entity_type == "campaign"
    assert ref.entity_id == "camp_ab12cd34ef56"
    prefixed = parse_investigation_query("campaign:camp_ab12cd34ef56")
    assert prefixed.entity_type == "campaign"
    assert prefixed.entity_id == "camp_ab12cd34ef56"
