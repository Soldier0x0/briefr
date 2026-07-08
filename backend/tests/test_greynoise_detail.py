"""GreyNoise on-demand CVE detail (Track E8)."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_cve_detail_does_not_auto_fetch_greynoise(client, monkeypatch):
    monkeypatch.setenv("GREYNOISE_API_KEY", "test-gn-key")
    with patch(
        "routers.cves.greynoise_scans_for_cve",
        new_callable=AsyncMock,
    ) as mock_gn:
        resp = client.get("/api/cves/CVE-2024-0001")
    if resp.status_code == 404:
        pytest.skip("CVE not in test database")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("greynoise_configured") is True
    assert body.get("greynoise_scans") == []
    mock_gn.assert_not_called()


def test_greynoise_scans_endpoint_not_configured(client, monkeypatch):
    monkeypatch.delenv("GREYNOISE_API_KEY", raising=False)
    resp = client.get("/api/cves/CVE-2024-0001/greynoise-scans")
    if resp.status_code == 404:
        pytest.skip("CVE not in test database")
    assert resp.status_code == 200
    assert resp.json() == {"configured": False, "scans": []}
