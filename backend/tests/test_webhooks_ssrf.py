"""SSRF protections for outbound webhooks."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from resilient_client import reset_feed_health
from webhooks.ssrf import (
    SSRFError,
    async_resolve_hostname,
    build_pinned_url,
    is_blocked_ip,
    parse_https_url,
    resolve_hostname,
    safe_webhook_request,
    sanitize_outbound_headers,
    validate_resolved_ips,
)


@pytest.fixture(autouse=True)
def _clean():
    reset_feed_health()
    yield
    reset_feed_health()


@pytest.mark.parametrize(
    "addr",
    [
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "127.0.0.1",
        "127.255.255.255",
        "169.254.169.254",
        "0.0.0.0",
        "::1",
        "fc00::1",
        "fd12:3456:789a::1",
    ],
)
def test_blocks_reserved_address_classes(addr):
    import ipaddress

    assert is_blocked_ip(ipaddress.ip_address(addr)) is True


@pytest.mark.parametrize(
    "addr",
    [
        "8.8.8.8",
        "1.1.1.1",
        "93.184.216.34",
        "2001:4860:4860::8888",
    ],
)
def test_allows_public_addresses(addr):
    import ipaddress

    assert is_blocked_ip(ipaddress.ip_address(addr)) is False


@pytest.mark.parametrize(
    "addr",
    [
        "10.0.0.5",
        "172.31.255.255",
        "192.168.0.10",
        "127.0.0.2",
        "169.254.1.1",
        "0.0.0.1",
        "::1",
        "fc11::9",
    ],
)
def test_validate_resolved_ips_rejects_blocked(addr):
    with pytest.raises(SSRFError, match="blocked"):
        validate_resolved_ips([addr])


def test_parse_https_url_rejects_http():
    with pytest.raises(SSRFError, match="only https"):
        parse_https_url("http://example.com/hook")


def test_parse_https_url_rejects_missing_host():
    with pytest.raises(SSRFError, match="missing hostname"):
        parse_https_url("https:///hook")


def test_build_pinned_url_ipv6_brackets():
    url = build_pinned_url("example.com", 443, "/hook", "2001:db8::1")
    assert url == "https://[2001:db8::1]/hook"


def test_sanitize_outbound_headers_strips_internal_secrets():
    headers = sanitize_outbound_headers(
        {
            "Content-Type": "application/json",
            "Authorization": "Bearer secret",
            "X-BRIEFR-Admin-Key": "admin",
            "X-NVD-API-KEY": "nvd",
            "X-Custom": "allowed",
        }
    )
    assert headers == {"Content-Type": "application/json", "X-Custom": "allowed"}


def test_dns_rebinding_connects_to_validated_ip(monkeypatch):
    calls = []

    async def fake_resolve(_host):
        return ["93.184.216.34"]

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((str(request.url), request.headers.get("Host"), request.extensions.get("sni_hostname")))
        return httpx.Response(204)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("webhooks.ssrf._webhook_client", client)

    asyncio.run(
        safe_webhook_request(
            "webhook.test",
            "POST",
            "https://example.com/hook",
            json={"ok": True},
            resolve=fake_resolve,
        )
    )

    assert calls
    assert calls[0][0].startswith("https://93.184.216.34/hook")
    assert calls[0][1] == "example.com"
    # TLS must still be verified against the original hostname, not the
    # pinned IP literal — Discord/Slack/etc. sit behind shared certs that
    # are only valid for the hostname (regression: certificate verify
    # failed, IP address mismatch, observed against a real Discord webhook).
    assert calls[0][2] == "example.com"


def test_sni_hostname_omitted_for_ip_literal_destination(monkeypatch):
    """RFC 6066 forbids IP literals in SNI — destination URLs that are
    themselves an IP (no hostname to verify against) must not set it."""
    calls = []

    async def fake_resolve(_host):
        return ["93.184.216.34"]

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.extensions.get("sni_hostname"))
        return httpx.Response(204)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("webhooks.ssrf._webhook_client", client)

    asyncio.run(
        safe_webhook_request(
            "webhook.test",
            "POST",
            "https://93.184.216.34/hook",
            json={"ok": True},
            resolve=fake_resolve,
        )
    )

    assert calls == [None]


def test_redirect_is_not_followed(monkeypatch):
    async def fake_resolve(_host):
        return ["93.184.216.34"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://127.0.0.1/internal"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("webhooks.ssrf._webhook_client", client)

    with pytest.raises(SSRFError, match="redirect"):
        asyncio.run(
            safe_webhook_request(
                "webhook.test",
                "POST",
                "https://example.com/hook",
                json={"ok": True},
                resolve=fake_resolve,
            )
        )


@pytest.mark.parametrize(
    "blocked_ip",
    [
        "10.0.0.1",
        "172.16.0.1",
        "192.168.0.1",
        "127.0.0.1",
        "169.254.169.254",
        "0.0.0.0",
        "::1",
        "fc00::1",
    ],
)
def test_safe_request_blocks_each_address_class(monkeypatch, blocked_ip):
    async def fake_resolve(_host):
        return [blocked_ip]

    with pytest.raises(SSRFError, match="blocked"):
        asyncio.run(
            safe_webhook_request(
                "webhook.test",
                "POST",
                "https://example.com/hook",
                json={"ok": True},
                resolve=fake_resolve,
            )
        )


def test_resolve_hostname_blocks_private(monkeypatch):
    def fake_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return [(2, 1, 6, "", ("127.0.0.1", 0))]

    with patch("webhooks.ssrf.socket.getaddrinfo", fake_getaddrinfo):
        with pytest.raises(SSRFError, match="blocked"):
            resolve_hostname("evil.example")


def test_async_resolve_hostname_blocks_private(monkeypatch):
    def fake_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return [(2, 1, 6, "", ("10.0.0.5", 0))]

    with patch("webhooks.ssrf.socket.getaddrinfo", fake_getaddrinfo):
        with pytest.raises(SSRFError, match="blocked"):
            asyncio.run(async_resolve_hostname("internal.example"))
