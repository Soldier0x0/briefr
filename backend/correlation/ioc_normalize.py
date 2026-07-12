"""Canonical IOC normalization for correlation ingest (v2 Phase 1)."""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

_DEFANG_REPLACEMENTS = (
    (re.compile(r"hxxps?://", re.I), "http://"),
    (re.compile(r"\[\.\]"), "."),
    (re.compile(r"\[:\]"), ":"),
    (re.compile(r"\[@\]"), "@"),
)

_IP_TYPES = frozenset({"ip", "ipv4", "ipv6"})

# CORR-PR-3 / D2: a small literal set of well-known public DNS resolvers —
# these appear as "shared infrastructure" across huge numbers of unrelated
# CVEs simply because malware and legitimate tools alike resolve through
# them, not because the CVEs are actually related. A curated CDN/cloud-IP
# denylist feed was explicitly rejected (spec §19, maintenance burden) —
# the degree penalty (confidence.py) handles popular IOCs generally; this
# is just the handful of always-known-noise addresses worth hardcoding.
_PUBLIC_RESOLVER_IPS = frozenset({
    "8.8.8.8", "8.8.4.4",          # Google
    "1.1.1.1", "1.0.0.1",          # Cloudflare
    "9.9.9.9", "149.112.112.112",  # Quad9
    "208.67.222.222", "208.67.220.220",  # OpenDNS
    "4.2.2.1", "4.2.2.2",          # Level3 legacy
    "64.6.64.6", "64.6.65.6",      # Verisign
})


def refang(value: str) -> str:
    out = (value or "").strip()
    for pattern, repl in _DEFANG_REPLACEMENTS:
        out = pattern.sub(repl, out)
    return out


def normalize_ioc_type(ioc_type: str) -> str:
    t = (ioc_type or "").strip().upper()
    if t in ("IP", "IPV4", "IPV6"):
        return "IP"
    if t in ("DOMAIN", "HOSTNAME"):
        return "DOMAIN"
    if t in ("URL", "URI"):
        return "URL"
    if t in ("FILE", "HASH", "MD5", "SHA1", "SHA256", "SHA512"):
        return "HASH"
    return t or "UNKNOWN"


def _normalize_hash(value: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", value).lower()


def _normalize_domain(value: str) -> str:
    host = value.strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def _normalize_url(value: str) -> str:
    v = refang(value).strip()
    if "://" not in v:
        v = f"http://{v}"
    parsed = urlparse(v)
    scheme = (parsed.scheme or "http").lower()
    netloc = parsed.netloc.lower() if parsed.netloc else ""
    return urlunparse(
        (scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )


def is_noise_ip(value: str) -> bool:
    """RFC1918, loopback, link-local, or a well-known public resolver —
    downrank, do not delete."""
    stripped = value.strip()
    if stripped in _PUBLIC_RESOLVER_IPS:
        return True
    try:
        addr = ipaddress.ip_address(stripped)
    except ValueError:
        return False
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
    )


def normalize_ioc(
    ioc_type: str, ioc_value: str
) -> tuple[str, str, dict[str, Any]] | None:
    """
    Return (canonical_type, canonical_value, meta) or None when empty.
    meta may include raw_value and is_noise_ip.
    """
    raw = (ioc_value or "").strip()
    if not raw:
        return None

    canon_type = normalize_ioc_type(ioc_type)
    refanged = refang(raw)
    meta: dict[str, Any] = {"raw_value": raw}

    if canon_type == "IP":
        try:
            addr = ipaddress.ip_address(refanged)
        except ValueError:
            return None
        canon_value = str(addr)
        meta["is_noise_ip"] = is_noise_ip(canon_value)
        return canon_type, canon_value, meta

    if canon_type == "DOMAIN":
        canon_value = _normalize_domain(refanged)
        if not canon_value or "." not in canon_value:
            return None
        return canon_type, canon_value, meta

    if canon_type == "URL":
        canon_value = _normalize_url(refanged)
        if len(canon_value) < 8:
            return None
        return canon_type, canon_value, meta

    if canon_type == "HASH":
        canon_value = _normalize_hash(refanged)
        if len(canon_value) < 32:
            return None
        return canon_type, canon_value, meta

    return canon_type, refanged, meta


def normalize_ioc_row(row: dict) -> dict | None:
    """Normalize an OTX IOC dict in place; returns None to skip."""
    normalized = normalize_ioc(row.get("ioc_type") or "", row.get("ioc_value") or "")
    if normalized is None:
        return None
    canon_type, canon_value, meta = normalized
    out = dict(row)
    out["ioc_type"] = canon_type
    out["ioc_value"] = canon_value
    out["ioc_meta"] = meta
    return out
