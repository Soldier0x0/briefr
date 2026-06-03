"""
Executive summary for PDF reports — Groq primary, Anthropic fallback, template last.
Called only when an analyst explicitly exports a PDF (via API from the client).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

from templates.intelligence import kev_sentence, severity_sentence

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = (
    "You are a senior threat intelligence analyst writing an executive summary "
    "for a security investigation report. Respond with valid JSON only (no markdown fences)."
)

USER_PROMPT_TEMPLATE = """You are a senior threat intelligence analyst writing an
executive summary for a security investigation report.
Write exactly 4 sentences in the executive_summary field (one paragraph).
Sentence 1: What triggered the investigation and severity.
Sentence 2: Key threat intelligence findings (exploitation,
            actor attribution if any).
Sentence 3: Business risk and affected systems.
Sentence 4: Most critical recommended action.
Be specific, use the CVE IDs and data provided.
Do not use jargon unexplained. Write for a CISO audience.
Do not mention BRIEFR by name in the summary.

Also provide key_findings: 3-5 short bullet strings (specific facts from the data).
Set confidence to "high", "medium", or "low" based on data completeness.

Respond with JSON only:
{{"executive_summary": "...", "key_findings": ["...", "..."], "confidence": "high|medium|low"}}

Investigation duration: ~{duration} minutes

CVE records:
{cves_block}

IOC records:
{iocs_block}

Threat actors:
{actors_block}
"""


def _cve_label(cve: dict) -> str:
    return str(cve.get("cve_id") or cve.get("id") or "unknown")


def _format_cves_block(cves: list[dict]) -> str:
    if not cves:
        return "(none)"
    lines = []
    for c in cves[:12]:
        cid = _cve_label(c)
        sev = c.get("severity") or "unknown"
        cvss = c.get("cvss_score")
        cvss_s = f"{float(cvss):.1f}" if cvss is not None else "n/a"
        epss = c.get("epss_score")
        epss_s = f"{float(epss) * 100:.1f}%" if epss is not None else "n/a"
        kev = "KEV" if c.get("is_kev") else "not KEV"
        poc = "public PoC" if c.get("has_poc") else "no public PoC"
        products = c.get("affected_products") or []
        if isinstance(products, str):
            products = [products]
        prod_s = ", ".join(str(p) for p in products[:4]) or "unknown products"
        summary = (c.get("summary") or c.get("description") or "")[:240]
        lines.append(
            f"- {cid}: {sev} CVSS {cvss_s}, EPSS {epss_s}, {kev}, {poc}. "
            f"Affects: {prod_s}. {summary}"
        )
    return "\n".join(lines)


def _format_iocs_block(iocs: list[dict]) -> str:
    if not iocs:
        return "(none)"
    lines = []
    for i in iocs[:10]:
        val = i.get("value") or i.get("id") or i.get("title") or "unknown"
        desc = (i.get("description") or "")[:120]
        lines.append(f"- {val}: {desc or 'indicator lookup'}")
    return "\n".join(lines)


def _format_actors_block(actors: list[dict]) -> str:
    if not actors:
        return "(none)"
    lines = []
    for a in actors[:8]:
        name = a.get("name") or a.get("id") or a.get("title") or "unknown"
        desc = (a.get("description") or "")[:120]
        lines.append(f"- {name}: {desc or 'threat actor context'}")
    return "\n".join(lines)


def _template_key_findings(cves: list[dict], iocs: list[dict], actors: list[dict]) -> list[str]:
    findings: list[str] = []
    for c in cves[:4]:
        cid = _cve_label(c)
        findings.append(f"{cid}: {severity_sentence(c.get('severity'), c.get('cvss_score'))}")
        if c.get("is_kev"):
            findings.append(f"{cid}: {kev_sentence(True, c.get('due_date') or '')}")
    for i in iocs[:3]:
        val = i.get("value") or i.get("id") or i.get("title")
        if val:
            findings.append(f"Indicator {val} was reviewed in this investigation.")
    for a in actors[:2]:
        name = a.get("name") or a.get("id") or a.get("title")
        if name:
            findings.append(f"Threat actor context: {name}.")
    if not findings:
        findings.append("Review collected intelligence and validate exposure for listed assets.")
    return findings[:6]


def _template_executive_summary(
    cves: list[dict],
    iocs: list[dict],
    actors: list[dict],
    duration_min: int,
) -> str:
    cve_ids = [_cve_label(c) for c in cves[:6]]
    id_str = ", ".join(cve_ids) if cve_ids else "no CVE identifiers in scope"
    top = cves[0] if cves else {}
    sev_line = severity_sentence(top.get("severity"), top.get("cvss_score"))
    kev_line = kev_sentence(bool(top.get("is_kev")), top.get("due_date") or "") if top else ""

    s1 = (
        f"This report covers a {duration_min}-minute investigation focused on "
        f"{id_str}, reflecting {sev_line.split('.')[0].lower()}."
    )
    exploit_bits = []
    if top.get("has_poc"):
        exploit_bits.append("public exploit material is available")
    if top.get("is_kev"):
        exploit_bits.append("CISA has catalogued active exploitation")
    if top.get("epss_score") is not None and float(top["epss_score"]) >= 0.5:
        exploit_bits.append(
            f"EPSS estimates {float(top['epss_score']) * 100:.0f}% exploitation probability"
        )
    s2 = (
        "Key intelligence: " + (", ".join(exploit_bits) if exploit_bits else "no confirmed exploitation signals in the supplied data") + "."
    )
    if actors:
        s2 += f" Activity is associated with {actors[0].get('name') or actors[0].get('id') or 'documented threat actors'}."
    products = top.get("affected_products") or []
    if isinstance(products, str):
        products = [products]
    prod_names = ", ".join(str(p).split(":")[-1] for p in products[:3]) or "systems in your environment"
    s3 = f"Business risk concentrates on {prod_names}; unauthorized access could disrupt operations or expose sensitive data."
    if top.get("patch_available"):
        s4 = f"Prioritize patching { _cve_label(top) } and verify compensating controls until deployment is complete."
    elif top.get("is_kev"):
        s4 = f"Treat { _cve_label(top) } as an emergency remediation per CISA KEV guidance and hunt for related IOCs."
    elif iocs:
        s4 = "Correlate the listed indicators with internal logs and block or isolate matches while remediation is planned."
    else:
        s4 = "Validate exposure, apply vendor mitigations, and monitor for exploitation attempts over the next 30 days."

    if kev_line and top.get("is_kev"):
        s2 = kev_line + " " + s2

    return " ".join([s1, s2, s3, s4])


def _parse_ai_payload(content: str) -> dict[str, Any] | None:
    text = (content or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {
        "executive_summary": text,
        "key_findings": [],
        "confidence": "medium",
    }


def _normalize_result(
    raw: dict[str, Any],
    source: str,
    cves: list[dict],
    iocs: list[dict],
    actors: list[dict],
) -> dict[str, Any]:
    summary = (raw.get("executive_summary") or raw.get("summary") or "").strip()
    if not summary:
        summary = _template_executive_summary(cves, iocs, actors, 1)

    findings = raw.get("key_findings")
    if not isinstance(findings, list) or not findings:
        findings = _template_key_findings(cves, iocs, actors)
    else:
        findings = [str(f).strip() for f in findings if str(f).strip()][:8]

    confidence = str(raw.get("confidence") or "medium").lower()
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"

    return {
        "executive_summary": summary,
        "key_findings": findings,
        "confidence": confidence,
        "source": source,
    }


def _build_user_prompt(
    cves: list[dict],
    iocs: list[dict],
    actors: list[dict],
    duration_min: int,
) -> str:
    return USER_PROMPT_TEMPLATE.format(
        duration=duration_min,
        cves_block=_format_cves_block(cves),
        iocs_block=_format_iocs_block(iocs),
        actors_block=_format_actors_block(actors),
    )


async def _call_groq(prompt: str, api_key: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=50.0) as client:
            response = await client.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 600,
                    "temperature": 0.25,
                },
            )
        if response.status_code != 200:
            logger.warning("Groq summary error %s: %s", response.status_code, response.text[:300])
            return None
        content = (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return content.strip() or None
    except Exception as exc:
        logger.error("Groq summary request failed: %s", exc)
        return None


async def _call_anthropic(prompt: str, api_key: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                ANTHROPIC_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": ANTHROPIC_MODEL,
                    "max_tokens": 600,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        if response.status_code != 200:
            logger.warning(
                "Anthropic summary error %s: %s",
                response.status_code,
                response.text[:300],
            )
            return None
        blocks = response.json().get("content") or []
        parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        text = "".join(parts).strip()
        return text or None
    except Exception as exc:
        logger.error("Anthropic summary request failed: %s", exc)
        return None


async def generate_executive_summary(
    cves: list[dict] | None = None,
    iocs: list[dict] | None = None,
    actors: list[dict] | None = None,
    investigation_duration: int = 1,
) -> dict[str, Any]:
    """
    Return executive_summary, key_findings, confidence, and source (groq|anthropic|template).
    Never raises — always returns a usable summary.
    """
    cve_list = list(cves or [])
    ioc_list = list(iocs or [])
    actor_list = list(actors or [])
    duration = max(1, int(investigation_duration or 1))

    template_result = {
        "executive_summary": _template_executive_summary(
            cve_list, ioc_list, actor_list, duration
        ),
        "key_findings": _template_key_findings(cve_list, ioc_list, actor_list),
        "confidence": "low",
        "source": "template",
    }

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not groq_key and not anthropic_key:
        return template_result

    prompt = _build_user_prompt(cve_list, ioc_list, actor_list, duration)

    if groq_key:
        content = await _call_groq(prompt, groq_key)
        if content:
            parsed = _parse_ai_payload(content)
            if parsed:
                result = _normalize_result(parsed, "groq", cve_list, ioc_list, actor_list)
                result["confidence"] = result.get("confidence") or "high"
                return result

    if anthropic_key:
        content = await _call_anthropic(prompt, anthropic_key)
        if content:
            parsed = _parse_ai_payload(content)
            if parsed:
                result = _normalize_result(parsed, "anthropic", cve_list, ioc_list, actor_list)
                if result.get("confidence") == "medium":
                    result["confidence"] = "medium"
                return result

    return template_result
