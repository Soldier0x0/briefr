"""Validate DNS hostnames for IOC domain lookups (ASCII + IDN/punycode)."""

import re
from urllib.parse import urlparse

# DNS label: 1-63 chars, alphanumeric + hyphen, no leading/trailing hyphen.
_LABEL = r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
_DOMAIN_ASCII_RE = re.compile(rf"^(?:{_LABEL}\.)+{_LABEL}$")
_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def is_valid_domain(host: str) -> bool:
    """Return True when host is a plausible DNS hostname (FQDN with 2+ labels)."""
    if not host:
        return False

    host = host.rstrip(".").lower()
    if ":" in host and not host.startswith("["):
        try:
            parsed = urlparse(f"http://{host}")
            if parsed.hostname:
                host = parsed.hostname
        except ValueError:
            host = host.split(":", 1)[0]
    if not host or len(host) > 253:
        return False

    try:
        ascii_host = host.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        return False

    if len(ascii_host) > 253 or not _DOMAIN_ASCII_RE.match(ascii_host):
        return False

    if _IPV4_RE.match(ascii_host):
        octets = ascii_host.split(".")
        if all(part.isdigit() and 0 <= int(part) <= 255 for part in octets):
            return False

    return True
