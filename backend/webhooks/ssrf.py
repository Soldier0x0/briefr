"""SSRF protections for outbound webhook HTTP (V1.4 Theme 2).

Validates destination hostnames/IPs before connect, pins resolved IPs on the
wire (Host header preserved), allows https only, disables redirects, and
never attaches internal API secrets to outbound headers.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from resilient_client import record_source_failure, record_source_success

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 10.0
WEBHOOK_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.5
RETRYABLE_STATUS = {500, 502, 503, 504}

BLOCKED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
)

FORBIDDEN_OUTBOUND_HEADERS = frozenset(
    {
        "authorization",
        "x-briefr-admin-key",
        "x-api-key",
        "x-virustotal-api-key",
        "x-nvd-api-key",
        "x-github-token",
        "x-groq-api-key",
        "x-abuseipdb-api-key",
        "x-greynoise-api-key",
        "x-circl-api-key",
    }
)

_webhook_client: httpx.AsyncClient | None = None


class SSRFError(ValueError):
    """Raised when a webhook destination fails SSRF validation."""


def is_blocked_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if addr.is_private or addr.is_loopback or addr.is_link_local:
        return True
    if addr.is_unspecified:
        return True
    if isinstance(addr, ipaddress.IPv6Address) and addr.is_site_local:
        return True
    return any(addr in net for net in BLOCKED_NETWORKS)


def validate_resolved_ips(ips: list[str]) -> list[str]:
    if not ips:
        raise SSRFError("hostname did not resolve")
    validated: list[str] = []
    for raw in ips:
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise SSRFError(f"invalid resolved address: {raw}") from exc
        if is_blocked_ip(addr):
            raise SSRFError(f"blocked address: {raw}")
        validated.append(raw)
    return validated


def resolve_hostname(hostname: str) -> list[str]:
    """Resolve hostname synchronously and validate every returned address."""
    if not hostname:
        raise SSRFError("missing hostname")
    try:
        infos = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise SSRFError(f"DNS resolution failed for {hostname}") from exc
    ips = sorted({info[4][0] for info in infos})
    return validate_resolved_ips(ips)


async def async_resolve_hostname(hostname: str) -> list[str]:
    return await asyncio.to_thread(resolve_hostname, hostname)


def parse_https_url(url: str) -> tuple[str, int, str, str]:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        raise SSRFError("only https webhook URLs are allowed")
    host = parsed.hostname
    if not host:
        raise SSRFError("missing hostname")
    port = parsed.port or 443
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return host, port, path, parsed.netloc


def build_pinned_url(host: str, port: int, path: str, pinned_ip: str) -> str:
    bracketed = f"[{pinned_ip}]" if ":" in pinned_ip else pinned_ip
    if port == 443:
        return f"https://{bracketed}{path}"
    return f"https://{bracketed}:{port}{path}"


def sanitize_outbound_headers(headers: dict[str, str] | None) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in (headers or {}).items():
        lower = key.lower()
        if lower in FORBIDDEN_OUTBOUND_HEADERS:
            continue
        if lower.startswith("x-briefr-"):
            continue
        safe[key] = value
    return safe


def _get_webhook_client() -> httpx.AsyncClient:
    global _webhook_client
    if _webhook_client is None or _webhook_client.is_closed:
        _webhook_client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=WEBHOOK_TIMEOUT,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            headers={"User-Agent": "BRIEFR/1.0 (+https://github.com/Soldier0x0/briefr)"},
        )
    return _webhook_client


async def close_webhook_client() -> None:
    global _webhook_client
    if _webhook_client is not None and not _webhook_client.is_closed:
        await _webhook_client.aclose()
    _webhook_client = None


async def safe_webhook_request(
    source: str,
    method: str,
    url: str,
    *,
    json: Any = None,
    data: Any = None,
    headers: dict[str, str] | None = None,
    retries: int = WEBHOOK_RETRIES,
    resolve: Any | None = None,
) -> httpx.Response:
    """Perform an SSRF-safe webhook HTTP request with health recording."""
    host, port, path, _netloc = parse_https_url(url)
    resolver = resolve or async_resolve_hostname
    pinned_ips = validate_resolved_ips(await resolver(host))
    pinned_ip = pinned_ips[0]
    pinned_url = build_pinned_url(host, port, path, pinned_ip)

    outbound_headers = sanitize_outbound_headers(headers)
    outbound_headers["Host"] = host

    client = _get_webhook_client()
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = await client.request(
                method,
                pinned_url,
                json=json,
                data=data,
                headers=outbound_headers,
                # Connecting to the pinned IP literal means httpx's default TLS
                # verification would check the cert against that IP string —
                # which fails for virtually every host (Discord, Slack, etc.
                # sit behind shared/CDN certs valid only for the hostname).
                # sni_hostname tells httpcore to send the original hostname as
                # SNI and verify the cert against it, while the TCP connection
                # itself still goes to the validated, pinned IP.
                extensions={"sni_hostname": host},
            )
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
                continue
            record_source_failure(source, f"{type(exc).__name__}: {exc}")
            raise

        if response.status_code in RETRYABLE_STATUS or response.status_code == 429:
            last_exc = httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )
            if attempt < retries:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
                continue
            record_source_failure(source, f"HTTP {response.status_code}")
            response.raise_for_status()

        if response.is_redirect:
            record_source_failure(source, f"redirect blocked: HTTP {response.status_code}")
            raise SSRFError(
                f"redirect responses are not followed (HTTP {response.status_code})"
            )

        if response.is_server_error:
            record_source_failure(source, f"HTTP {response.status_code}")
            response.raise_for_status()

        if response.is_client_error:
            record_source_failure(source, f"HTTP {response.status_code}")
            response.raise_for_status()

        record_source_success(source)
        return response

    raise last_exc if last_exc else RuntimeError(f"webhook request failed for {source}")


def webhook_json_payload(message: str, *, event_type: str, dedupe_key: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "text": message,
        "event_type": event_type,
        "source": "briefr",
    }
    if dedupe_key:
        body["dedupe_key"] = dedupe_key
    return body
