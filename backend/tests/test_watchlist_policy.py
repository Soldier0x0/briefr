"""Watchlist default policy: quiet triggers, rare overrides, digest when all-on."""

from watchlist.policy import (
    DEFAULT_TRIGGERS,
    TRIGGER_EPSS,
    TRIGGER_KEV,
    TRIGGER_PATCH,
    TRIGGER_POC,
    TRIGGER_WITHDRAWN,
    delivery_mode,
    sanitize_policy,
    trigger_enabled,
)


def test_quiet_defaults_enable_actionable_triggers_not_patch():
    policy = sanitize_policy(None)
    assert policy["triggers"] == DEFAULT_TRIGGERS
    assert policy["triggers"][TRIGGER_KEV] is True
    assert policy["triggers"][TRIGGER_EPSS] is True
    assert policy["triggers"][TRIGGER_POC] is True
    assert policy["triggers"][TRIGGER_WITHDRAWN] is True
    assert policy["triggers"][TRIGGER_PATCH] is False
    assert policy["delivery"] == "immediate"
    assert policy["overrides"] == {}


def test_unknown_keys_dropped_and_missing_triggers_filled():
    policy = sanitize_policy({"triggers": {"kev": False, "nope": True}, "extra": 1})
    assert policy["triggers"][TRIGGER_KEV] is False
    assert policy["triggers"][TRIGGER_EPSS] is True
    assert "nope" not in policy["triggers"]
    assert "extra" not in policy


def test_override_disables_one_cve_trigger():
    policy = sanitize_policy(
        {
            "overrides": {
                "cve-2024-1": {"triggers": {"epss": False}},
            }
        }
    )
    assert trigger_enabled(policy, "CVE-2024-1", TRIGGER_EPSS) is False
    assert trigger_enabled(policy, "CVE-2024-1", TRIGGER_KEV) is True
    assert trigger_enabled(policy, "CVE-2024-2", TRIGGER_EPSS) is True


def test_all_triggers_on_forces_digest_delivery():
    policy = sanitize_policy(
        {
            "triggers": {
                TRIGGER_KEV: True,
                TRIGGER_EPSS: True,
                TRIGGER_POC: True,
                TRIGGER_PATCH: True,
                TRIGGER_WITHDRAWN: True,
            },
            "delivery": "immediate",
        }
    )
    assert delivery_mode(policy) == "digest"


def test_explicit_digest_even_when_quiet():
    policy = sanitize_policy({"delivery": "digest"})
    assert delivery_mode(policy) == "digest"
    assert policy["triggers"][TRIGGER_PATCH] is False
