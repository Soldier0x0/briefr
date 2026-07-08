"""Tests for deterministic Nuclei YAML parser (Sprint D4)."""

from pathlib import Path

from detection.nuclei_parser import parse_nuclei_template_yaml

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "nuclei_template_sample.yaml"


def test_parse_nuclei_template_sample_fixture():
    artifacts = parse_nuclei_template_yaml(FIXTURE.read_text())
    assert len(artifacts) >= 2

    login_art = artifacts[0]
    assert "/api/login" in login_art["paths"]
    assert "/admin/login.php" in login_art["paths"]
    assert login_art["method"] == "POST"
    assert "syntax error" in login_art["keywords"]

    search_art = artifacts[1]
    assert "/search" in search_art["paths"]
    assert search_art["method"] == "GET"
    assert "q" in search_art["params"]


def test_parse_nuclei_template_empty_and_invalid():
    assert parse_nuclei_template_yaml("") == []
    assert parse_nuclei_template_yaml("not: [valid") == []
    assert parse_nuclei_template_yaml("info:\n  name: no-http") == []
