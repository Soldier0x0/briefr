"""Tests for POST /api/proof/run."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "proof.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_proof_run_requires_input(client):
    resp = client.post("/api/proof/run", json={"lines": ["test line"]})
    assert resp.status_code == 400


def test_proof_run_matches_sigma_keywords(client):
    lines = (FIXTURES / "proof_traversal_sample.log").read_text(encoding="utf-8").splitlines()
    sigma_yaml = """
title: Test traversal
detection:
  keywords:
    - ../
    - /etc/passwd
  condition: keywords
falsepositives:
  - Vulnerability scanners
"""
    resp = client.post(
        "/api/proof/run",
        json={"lines": lines, "sigma_yaml": sigma_yaml, "max_samples": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["hit_count"] == 1
    assert data["total_lines"] == 3
    assert data["sample_hits"]
    assert "../" in data["sample_hits"][0]["matched_patterns"][0] or "/etc/passwd" in str(
        data["sample_hits"][0]["matched_patterns"]
    )
    assert "Vulnerability scanners" in data["false_positive_hints"]


def test_proof_run_explicit_patterns(client):
    resp = client.post(
        "/api/proof/run",
        json={"lines": ["error whoami failed", "ok"], "patterns": ["whoami"]},
    )
    assert resp.status_code == 200
    assert resp.json()["hit_count"] == 1
