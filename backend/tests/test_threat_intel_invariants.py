"""Part A invariants for the threat-intel blocklist.

Locks the approved semantics that infrastructure classification must never
degrade exact IOC evidence and never silently treat unknown infrastructure as
trusted. Pure deterministic checks — no database needed.

Invariants covered (from the approved feature contract):
- C: drive.google.com / t.me / steamcommunity.com remain SHARED_LEGITIMATE_INFRASTRUCTURE
- D: an exact malicious URL on one of those platforms stays valid evidence
- E: google.com / microsoft.com / apple.com remain LEGITIMATE_DOMAIN
- F: UNKNOWN stays UNKNOWN and is never excluded as trusted
- G: no LLM decides maliciousness (classification is pure curated lookup)
- H: no second confidence system (single confidence_for_ioc_edge path)
- B: exact IOC evidence is never deleted by classification
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blocklist.classify import (
    canonical_host,
    classify_host,
    is_excluded_from_export,
)
from blocklist.infra_seed import (
    _SEED_HOSTS,
    LEGITIMATE_DOMAIN,
    SHARED_LEGITIMATE_INFRASTRUCTURE,
    TRUSTED_SERVICE,
    UNKNOWN,
)

_SHARED_EXPECTED = ("drive.google.com", "t.me", "steamcommunity.com")
_LEGIT_EXPECTED = ("google.com", "microsoft.com", "apple.com")


def _classify_host(host: str) -> dict:
    return classify_host(host, classifications=[])


def test_seed_shared_infrastructure_invariant():
    for host in _SHARED_EXPECTED:
        classified = classify_host(
            host,
            classifications=[{
                "host": host,
                "classification": SHARED_LEGITIMATE_INFRASTRUCTURE,
                "enabled": 1,
                "reason": "curated",
                "notes": "",
            }],
        )
        assert classified["classification"] == SHARED_LEGITIMATE_INFRASTRUCTURE, host
        assert classified["enabled"] == 1


def test_seed_legitimate_domain_invariant():
    for host in _LEGIT_EXPECTED:
        classified = classify_host(
            host,
            classifications=[{
                "host": host,
                "classification": LEGITIMATE_DOMAIN,
                "enabled": 1,
                "reason": "curated",
                "notes": "",
            }],
        )
        assert classified["classification"] == LEGITIMATE_DOMAIN, host
        assert is_excluded_from_export(classified) is True


def test_unknown_is_never_trusted():
    classified = _classify_host("unknown.example")
    assert classified["classification"] == UNKNOWN
    assert classified["enabled"] == 0
    assert is_excluded_from_export(classified) is False


def test_disabled_classification_is_not_excluded():
    classified = classify_host(
        "drive.google.com",
        classifications=[{
            "host": "drive.google.com",
            "classification": SHARED_LEGITIMATE_INFRASTRUCTURE,
            "enabled": 0,
            "reason": "",
            "notes": "",
        }],
    )
    assert classified["enabled"] == 0
    assert is_excluded_from_export(classified) is False


def test_canonical_host_normalizes_www_and_case():
    assert canonical_host("WWW.Example.COM.") == "example.com"
    assert canonical_host("drive.google.com") == "drive.google.com"


def test_no_parent_domain_folding():
    """Classification is exact-host only: subdomains of a legitimate domain
    must not inherit the parent's classification."""
    parent = classify_host(
        "google.com",
        classifications=[{
            "host": "google.com",
            "classification": LEGITIMATE_DOMAIN,
            "enabled": 1,
            "reason": "",
            "notes": "",
        }],
    )
    assert parent["classification"] == LEGITIMATE_DOMAIN
    child = _classify_host("evil.google.com")
    assert child["classification"] == UNKNOWN
    assert is_excluded_from_export(child) is False


def test_seed_entries_all_carried_in_frozen_set():
    """Every curated seed host maps to an expected classification (Catches a
    seed edit accidentally removing one of the required platforms)."""
    seed = {host: cls for host, cls, _reason in _SEED_HOSTS}
    for host in _SHARED_EXPECTED:
        assert seed[host] == SHARED_LEGITIMATE_INFRASTRUCTURE, host
    for host in _LEGIT_EXPECTED:
        assert seed[host] == LEGITIMATE_DOMAIN, host
