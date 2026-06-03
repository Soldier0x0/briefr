"""Investigation executive summary — Groq LLM or template fallback."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


def _template_summary(items: list[dict], duration_min: int) -> str:
    cves = [i for i in items if i.get("type") == "cve"]
    iocs = [i for i in items if i.get("type") == "ioc"]
    actors = [i for i in items if i.get("type") == "actor"]
    techniques = [i for i in items if i.get("type") == "technique"]

    parts = [
        f"This investigation tracked {len(items)} pivot(s) over approximately {duration_min} minute(s).",
        f"Vulnerability focus: {', '.join(c['id'] for c in cves[:5]) or 'none recorded'}."
        if cves
        else "No CVE records were captured in this thread.",
        f"Indicators examined: {', '.join(i['id'] for i in iocs[:5]) or 'none'}."
        if iocs
        else "",
        f"Threat context: {', '.join(a['id'] for a in actors) or 'no actor tags'}; "
        f"{len(techniques)} ATLAS technique reference(s)."
        if actors or techniques
        else "No dedicated threat-actor or ATLAS technique pivots were recorded.",
    ]
    return " ".join(p for p in parts if p)


async def generate_investigation_summary(items: list[dict], duration_min: int) -> dict:
    """Return { summary, source } where source is 'groq' or 'template'."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key or not items:
        return {
            "summary": _template_summary(items, duration_min),
            "source": "template",
        }

    lines = []
    for i, item in enumerate(items, 1):
        pivot = ""
        if item.get("pivot_from"):
            pf = item["pivot_from"]
            pivot = f" (from {pf.get('type')} {pf.get('id')})"
        lines.append(
            f"{i}. [{item.get('type')}] {item.get('id')}: {item.get('description', '')[:200]}{pivot}"
        )

    prompt = (
        "You are a security analyst assistant. Write exactly 4 concise sentences summarising "
        "this investigation thread for a PDF executive summary. Be factual, no markdown, no bullet points.\n\n"
        f"Duration: ~{duration_min} minutes\n"
        f"Thread:\n" + "\n".join(lines)
    )

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You write clear, professional security investigation summaries.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 320,
                    "temperature": 0.3,
                },
            )
        if response.status_code != 200:
            logger.warning("Groq API error %s: %s", response.status_code, response.text[:200])
            return {
                "summary": _template_summary(items, duration_min),
                "source": "template",
            }
        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            raise ValueError("empty Groq response")
        return {"summary": content, "source": "groq"}
    except Exception as exc:
        logger.error("Groq investigation summary failed: %s", exc)
        return {
            "summary": _template_summary(items, duration_min),
            "source": "template",
        }
