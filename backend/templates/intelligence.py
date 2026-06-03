"""Template-based humanized intelligence sentences (no AI API)."""

from __future__ import annotations


def epss_sentence(score: float, kev: bool) -> str:
    pct = round(score * 100, 1)
    if pct >= 90:
        tier = 'top 1% of all CVEs by exploit likelihood'
    elif pct >= 70:
        tier = 'top 5% of all CVEs by exploit likelihood'
    elif pct >= 50:
        tier = 'top 15% of all CVEs by exploit likelihood'
    elif pct >= 30:
        tier = 'above average exploit likelihood'
    else:
        tier = 'below average exploit likelihood'
    base = (f'This vulnerability has a {pct}% probability of'
            f' exploitation in the next 30 days, placing it in'
            f' the {tier}.')
    if kev:
        return base + (' CISA has confirmed active exploitation'
                       ' in the wild.')
    elif pct >= 70:
        return base + ' Exploitation is considered highly likely.'
    elif pct >= 30:
        return base + (' Exploitation is plausible given public'
                       ' technical details.')
    else:
        return base + ' Active exploitation remains unlikely.'


def exploit_sentence(exploits: list) -> str:
    if not exploits:
        return ('No public exploits have been identified for'
                ' this vulnerability at this time.')
    weaponised = [e for e in exploits
                  if e.get('type') == 'weaponised']
    poc = [e for e in exploits
           if e.get('type') == 'poc']
    if weaponised:
        return (f'{len(weaponised)} weaponised exploit(s) are'
                f' publicly available, significantly lowering'
                f' the barrier for exploitation.')
    return (f'{len(poc)} proof-of-concept exploit(s) exist'
            f' publicly. Skilled attackers can adapt these'
            f' for active exploitation.')


def patch_sentence(available: bool, fix: str) -> str:
    if available and fix:
        return (f'A patch is available. Apply {fix} immediately'
                f' to remediate this vulnerability.')
    elif available:
        return ('A patch is available from the vendor.'
                ' Apply it as soon as possible.')
    else:
        return ('No official patch is currently available.'
                ' Apply vendor mitigations and monitor for'
                ' patch release.')


def kev_sentence(kev: bool, due_date: str) -> str:
    if not kev:
        return ('This vulnerability is not currently listed'
                ' on the CISA Known Exploited Vulnerabilities'
                ' catalogue.')
    if due_date:
        return (f'CISA has added this to the Known Exploited'
                f' Vulnerabilities catalogue with a remediation'
                f' deadline of {due_date}. Federal agencies are'
                f' required to patch by this date.')
    return ('CISA has confirmed active exploitation and added'
            ' this to the KEV catalogue. Treat as highest'
            ' priority for remediation.')


def severity_sentence(severity: str | None, cvss: float | None) -> str:
    sev = (severity or '').upper()
    score = cvss if cvss is not None else 0.0

    if sev == 'CRITICAL' or score >= 9.0:
        return (
            'This is a critical-severity vulnerability representing an '
            'immediate risk to affected systems and requiring emergency '
            'response and remediation.'
        )
    if sev == 'HIGH' or score >= 7.0:
        return (
            'This is a high-severity vulnerability posing serious risk '
            'to affected systems; prioritize remediation promptly.'
        )
    if sev == 'MEDIUM' or score >= 4.0:
        return (
            'This is a moderate-severity vulnerability; plan remediation '
            'in your next regular patch cycle.'
        )
    if sev == 'LOW' or score > 0:
        return (
            'This is a low-severity vulnerability; address when time '
            'and resources permit.'
        )
    return (
        'Severity could not be fully assessed; review the technical '
        'description and vendor guidance before prioritizing remediation.'
    )


WEAPONISED_URL_HINTS = (
    'metasploit',
    'weaponized',
    'weaponised',
    'in-the-wild',
)


def exploits_from_cve(has_poc: bool, source_urls: list | None) -> list[dict]:
    """Build exploit list for exploit_sentence from stored CVE fields."""
    exploits: list[dict] = []
    urls = source_urls or []
    for url in urls:
        lower = (url or '').lower()
        if any(hint in lower for hint in WEAPONISED_URL_HINTS):
            exploits.append({'type': 'weaponised', 'url': url})
    if has_poc:
        exploits.append({'type': 'poc'})
    return exploits


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


def epss_sentence_or_fallback(score: float | None, kev: bool) -> str:
    if score is None:
        base = (
            'Exploit probability scoring (EPSS) is not yet available '
            'for this vulnerability.'
        )
        if kev:
            return base + ' CISA has confirmed active exploitation in the wild.'
        return base
    return epss_sentence(float(score), kev)
