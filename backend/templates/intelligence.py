"""Template-based humanized intelligence sentences (no AI API)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional
from urllib.parse import unquote

PACKETSTORM_FILE_RE = re.compile(r"/files/(\d+)/([^/?#]+)", re.I)
MAX_REFERENCE_EXPLOIT_CARDS = 12
MAX_PACKETSTORM_CARDS = 6


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



def normalize_exploit_reference_url(url: str) -> str:
    """Canonicalize exploit reference URLs for browser links."""
    normalized = url.strip()
    if "packetstorm" in normalized.lower():
        normalized = re.sub(
            r"^https?://(?:www\.)?packetstorm(?:security)?\.(?:com|news)",
            "https://packetstorm.news",
            normalized,
            flags=re.I,
        )
    return normalized


def title_from_packetstorm_url(url: str) -> str:
    match = PACKETSTORM_FILE_RE.search(url)
    if not match:
        return "Packet Storm entry"
    slug = unquote(match.group(2))
    if slug.lower().endswith(".html"):
        slug = slug[:-5]
    title = slug.replace("-", " ").replace("_", " ").strip()
    return title or "Packet Storm entry"


def packetstorm_file_id(url: str) -> str | None:
    match = PACKETSTORM_FILE_RE.search(url)
    return match.group(1) if match else None


def _reference_card_priority(lower_url: str) -> int:
    if "metasploit" in lower_url:
        return 0
    if "exploit-db" in lower_url or "exploitdb" in lower_url:
        return 1
    if "github.com" in lower_url:
        return 2
    if "packetstorm" in lower_url:
        return 4
    return 3


def refs_to_exploit_cards(has_poc: bool, source_urls: list | None) -> list[dict]:
    """Build Intel-tab exploit cards from NVD reference URLs when Sploitus has no hits."""
    candidates: list[tuple[int, dict]] = []
    seen_urls: set[str] = set()
    seen_packetstorm_ids: set[str] = set()

    for url in source_urls or []:
        if not isinstance(url, str) or not url.strip():
            continue
        normalized_url = normalize_exploit_reference_url(url)
        lower = normalized_url.lower().strip()
        if lower in seen_urls:
            continue
        seen_urls.add(lower)

        exploit_type = "poc"
        source = "Reference"
        title = "Vendor or advisory reference"
        requires_terms = False

        if "metasploit" in lower:
            exploit_type = "metasploit"
            source = "Metasploit"
            title = "Metasploit module"
        elif "exploit-db" in lower or "exploitdb" in lower:
            exploit_type = "weaponised"
            source = "Exploit-DB"
            title = "Exploit-DB entry"
        elif "github.com" in lower and any(
            k in lower for k in ("poc", "exploit", "cve-", "log4j", "payload")
        ):
            source = "GitHub"
            title = "GitHub PoC / exploit code"
        elif any(h in lower for h in WEAPONISED_URL_HINTS):
            exploit_type = "weaponised"
            source = "Advisory"
            title = "Weaponised exploit reference"
        elif "packetstorm" in lower:
            file_id = packetstorm_file_id(normalized_url)
            if file_id:
                if file_id in seen_packetstorm_ids:
                    continue
                seen_packetstorm_ids.add(file_id)
            source = "Packet Storm"
            title = title_from_packetstorm_url(normalized_url)
            requires_terms = True
        elif not any(
            k in lower
            for k in ("exploit", "poc", "github", "metasploit", "packetstorm", "weapon")
        ):
            continue

        card = {
            "title": title,
            "type": exploit_type,
            "source": source,
            "url": normalized_url,
            "published_date": "",
            "from_reference": True,
        }
        if requires_terms:
            card["requires_terms_acceptance"] = True
        candidates.append((_reference_card_priority(lower), card))

    candidates.sort(key=lambda item: item[0])
    cards = [card for _, card in candidates]

    packetstorm_cards = [card for card in cards if card.get("source") == "Packet Storm"]
    other_cards = [card for card in cards if card.get("source") != "Packet Storm"]
    cards = other_cards + packetstorm_cards[:MAX_PACKETSTORM_CARDS]
    cards = cards[:MAX_REFERENCE_EXPLOIT_CARDS]

    if has_poc and not any(c.get("type") == "poc" for c in cards):
        cards.append(
            {
                "title": "Proof-of-concept published",
                "type": "poc",
                "source": "NVD",
                "url": "",
                "published_date": "",
                "from_reference": True,
            }
        )
    return cards


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


def otx_sentence(otx: dict | None) -> str:
    if not otx or not otx.get("pulse_count"):
        return (
            "AlienVault OTX has no community pulses referencing this indicator."
        )
    count = int(otx.get("pulse_count") or 0)
    adversary = (otx.get("adversary") or "").strip()
    families = otx.get("malware_families") or []
    cves = otx.get("related_cves") or []
    parts = [f"{count} community pulse{'s' if count != 1 else ''} reference this indicator"]
    if adversary:
        parts.append(f"most recent adversary attribution: {adversary}")
    if families:
        fam_str = ", ".join(families[:4])
        parts.append(f"associated malware families: {fam_str}")
    if cves:
        parts.append(f"linked CVEs: {', '.join(cves[:5])}")
    return ". ".join(parts) + "."


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
