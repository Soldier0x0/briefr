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
