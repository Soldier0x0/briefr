import pytest

from enrichment.domain_validation import is_valid_domain


@pytest.mark.parametrize(
    "host",
    [
        "example.com",
        "www.skuniversity.ac.in",
        "api.github-status.com",
        "v2.api.example.com",
        "3com.com",
        "a.b.c.example.co.uk",
        "xn--bcher-kva.example",
        "example.xn--p1ai",
        "münchen.de",
        "sub-domain.example.org",
    ],
)
def test_accepts_valid_domains(host):
    assert is_valid_domain(host) is True


@pytest.mark.parametrize(
    "host",
    [
        "",
        "localhost",
        "not-a-domain",
        "-bad.com",
        "bad-.com",
        "1.2.3.4",
        "foo_bar.com",
        "a" * 64 + ".com",
    ],
)
def test_rejects_invalid_domains(host):
    assert is_valid_domain(host) is False
