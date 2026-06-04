"""Template-based humanized intelligence sentences (no AI API)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional


def severity_sentence(severity: str, cvss: float) -> str:
    sev = (severity or "").upper()
    score = float(cvss) if cvss is not None else 0.0
    if sev == "CRITICAL" or score >= 9.0:
        return (
            f"This vulnerability carries a CVSS score of {score} and is rated"
            f" CRITICAL, representing an immediate risk requiring emergency"
            f" response. Do not delay remediation."
        )
    if sev == "HIGH" or score >= 7.0:
        return (
            f"Rated HIGH with a CVSS score of {score}, this vulnerability"
            f" represents a serious risk and should be addressed within"
            f" your next patch cycle or sooner if internet-facing."
        )
    if sev == "MEDIUM" or score >= 4.0:
        return (
            f"This MEDIUM severity vulnerability scores {score} on CVSS."
            f" Address it in your next scheduled patch cycle."
        )
    return (
        f"A LOW severity vulnerability with CVSS {score}."
        f" Address as time and resources permit."
    )


def epss_sentence(score: float, kev: bool) -> str:
    pct = round(score * 100, 1)
    if pct >= 90:
        tier = "top 1% of all CVEs by exploit likelihood"
    elif pct >= 70:
        tier = "top 5% of all CVEs by exploit likelihood"
    elif pct >= 50:
        tier = "top 15% of all CVEs by exploit likelihood"
    elif pct >= 30:
        tier = "above average exploit likelihood"
    else:
        tier = "below average exploit likelihood"
    base = (
        f"This vulnerability has a {pct}% probability of exploitation"
        f" in the next 30 days, placing it in the {tier}."
    )
    if kev:
        return base + " CISA has confirmed active exploitation in the wild."
    if pct >= 70:
        return base + " Exploitation is considered highly likely in the near term."
    if pct >= 30:
        return base + " Exploitation is plausible given public technical details."
    return base + " Active exploitation remains unlikely at this time."


def kev_sentence(
    kev: bool,
    due_date: Optional[str],
    date_added: Optional[str] = None,
) -> str:
    if not kev:
        return (
            "This vulnerability is not currently listed on the CISA"
            " Known Exploited Vulnerabilities catalogue."
        )
    base = (
        "CISA has confirmed active exploitation and added this to the KEV catalogue."
    )
    if due_date:
        return (
            base
            + f" Federal agencies are required to remediate by {due_date}."
            + " Treat this as highest priority."
        )
    if date_added:
        return base + f" Added to the catalogue on {date_added}. Treat as highest priority."
    return base + " Treat as highest priority for remediation."


def exploit_sentence(exploits: list) -> str:
    if not exploits:
        return "No public exploits have been identified for this vulnerability."
    weaponised = [e for e in exploits if e.get("type") == "weaponised"]
    metasploit = [e for e in exploits if e.get("type") == "metasploit"]
    poc = [e for e in exploits if e.get("type") == "poc"]
    if metasploit:
        return (
            "A Metasploit module is publicly available, meaning any attacker"
            " with basic skills can exploit this vulnerability with minimal effort."
        )
    if weaponised:
        return (
            f"{len(weaponised)} weaponised exploit(s) are publicly available,"
            " significantly lowering the barrier for exploitation."
        )
    return (
        f"{len(poc)} proof-of-concept exploit(s) exist publicly. Skilled"
        " attackers can adapt these for active exploitation."
    )


_PATCH_IMPERATIVE_PREFIXES = (
    "apply ", "install ", "update ", "upgrade ", "deploy ",
    "implement ", "migrate ", "remove ", "disable ",
)


def _patch_action_clause(fix: str) -> str:
    text = fix.strip()
    if not text:
        return ""
    if text[-1] not in ".!?":
        text += "."
    lower = text.lower()
    if any(lower.startswith(prefix) for prefix in _PATCH_IMPERATIVE_PREFIXES):
        return text
    return f"Apply {text}"


def patch_sentence(available: bool, fix: Optional[str]) -> str:
    if available and fix:
        action = _patch_action_clause(fix)
        return (
            f"A patch is available. {action} "
            "Remediate this vulnerability as soon as possible."
        )
    if available:
        return "A patch is available from the vendor. Apply as soon as possible."
    return (
        "No official patch is currently available. Apply vendor mitigations"
        " and monitor for patch release."
    )


WEAPONISED_URL_HINTS = (
    "metasploit",
    "weaponized",
    "weaponised",
    "in-the-wild",
)


def exploits_from_cve(has_poc: bool, source_urls: list | None) -> list[dict]:
    """Build exploit list for exploit_sentence from stored CVE fields."""
    exploits: list[dict] = []
    urls = source_urls or []
    for url in urls:
        lower = (url or "").lower()
        if "metasploit" in lower:
            exploits.append({"type": "metasploit", "url": url})
        elif any(hint in lower for hint in WEAPONISED_URL_HINTS):
            exploits.append({"type": "weaponised", "url": url})
    if has_poc and not exploits:
        exploits.append({"type": "poc"})
    elif has_poc:
        exploits.append({"type": "poc"})
    return exploits


def epss_sentence_or_fallback(score: float | None, kev: bool) -> str:
    if score is None:
        base = (
            "Exploit probability scoring (EPSS) is not yet available "
            "for this vulnerability."
        )
        if kev:
            return base + " CISA has confirmed active exploitation in the wild."
        return base
    return epss_sentence(float(score), kev)


def greynoise_sentence(gn: dict | None) -> str:
    if not gn:
        return (
            "GreyNoise scanning intelligence is not available for this address."
        )
    classification = (gn.get("classification") or "unknown").lower()
    name = (gn.get("name") or "").strip()
    ip = gn.get("ip") or "this address"
    if classification == "malicious":
        detail = f" ({name})" if name else ""
        return (
            f"GreyNoise classifies {ip} as malicious internet scanning activity"
            f"{detail}. Treat associated traffic as hostile."
        )
    if classification == "benign":
        detail = f" — {name}" if name else ""
        return (
            f"GreyNoise classifies {ip} as benign or common business traffic"
            f"{detail}. Noise is unlikely to reflect targeted attack activity."
        )
    if not gn.get("noise"):
        return (
            f"GreyNoise has not observed widespread scanning from {ip}. "
            "It has not appeared in their internet noise feed."
        )
    return (
        f"GreyNoise has seen scanning activity from {ip} but cannot firmly "
        "classify it as benign or malicious."
    )


def malwarebazaar_sentence(mb: dict | None) -> str:
    if not mb or not (mb.get("malware_family") or mb.get("tags")):
        return (
            "MalwareBazaar has no malware sample metadata linked to this hash."
        )
    family = (mb.get("malware_family") or "unknown family").strip()
    first = (mb.get("first_seen") or "").strip()
    tags = mb.get("tags") or []
    tag_str = ", ".join(tags[:5]) if tags else "no tags"
    when = f", first seen {first}" if first else ""
    return (
        f"MalwareBazaar associates this hash with {family}{when}. "
        f"Community tags: {tag_str}."
    )


def urlhaus_sentence(uh: dict | None) -> str:
    if not uh or not uh.get("threat_type"):
        return "URLhaus has no active malware distribution record for this indicator."
    threat = uh.get("threat_type") or "malware"
    tags = uh.get("tags") or []
    reporter = (uh.get("reporter") or "").strip()
    tag_str = ", ".join(tags[:5]) if tags else "none listed"
    rep = f" Reported by {reporter}." if reporter else ""
    return (
        f"URLhaus lists this indicator as {threat} distribution. "
        f"Tags: {tag_str}.{rep}"
    )
