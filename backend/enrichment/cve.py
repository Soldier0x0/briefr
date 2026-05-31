"""Derive display fields from NVD/KEV/OSV source data (no LLM)."""
from __future__ import annotations

import re

MITRE_TECHNIQUE_RE = re.compile(
    r"attack\.mitre\.org/techniques/(T\d{4})(?:/(\d{3}))?",
    re.IGNORECASE,
)

EXPLOIT_REFERENCE_TAGS = frozenset(
    {
        "exploit",
        "exploit code",
        "proof of concept",
        "poc",
    }
)

EXPLOIT_URL_HINTS = (
    "exploit-db.com",
    "exploitdb.com",
    "packetstormsecurity.com",
    "metasploit.com",
    "0day.today",
)


def extract_mitre_from_urls(urls: list[str]) -> str | None:
    return extract_mitre_technique([{"url": u, "tags": []} for u in urls if u])


def extract_mitre_technique(references: list) -> str | None:
    for ref in references:
        url = ref.get("url", "")
        match = MITRE_TECHNIQUE_RE.search(url)
        if not match:
            continue
        technique = match.group(1).upper()
        sub = match.group(2)
        if sub:
            return f"{technique}.{sub}"
        return technique
    return None


def has_public_poc(references: list) -> bool:
    for ref in references:
        tags = {str(t).lower() for t in ref.get("tags", [])}
        if tags & EXPLOIT_REFERENCE_TAGS:
            return True
        url = ref.get("url", "").lower()
        if any(hint in url for hint in EXPLOIT_URL_HINTS):
            return True
        if "github.com" in url and ("poc" in url or "exploit" in url):
            return True
    return False


def simplify_description(description: str, max_len: int = 240) -> str | None:
    if not description or not description.strip():
        return None
    text = " ".join(description.split())
    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary = sentences[0] if sentences else text
    if len(summary) > max_len:
        cut = summary[:max_len].rsplit(" ", 1)[0]
        summary = f"{cut}…" if cut else summary[:max_len]
    return summary


def build_plain_summary(
    description: str,
    *,
    kev_short: str | None = None,
    osv_summary: str | None = None,
) -> str | None:
    if kev_short and kev_short.strip():
        return kev_short.strip()
    if osv_summary and osv_summary.strip():
        return osv_summary.strip()
    return simplify_description(description)
