"""Backward-compatible wrapper for investigation PDF summaries."""

from ai.summary import generate_executive_summary


async def generate_investigation_summary(items: list[dict], duration_min: int) -> dict:
    """Return { summary, source } for legacy /api/investigation/summary clients."""
    cves: list[dict] = []
    iocs: list[dict] = []
    actors: list[dict] = []

    for item in items:
        t = item.get("type")
        if t == "cve":
            cves.append({"cve_id": item.get("id"), "description": item.get("description", "")})
        elif t == "ioc":
            iocs.append({"value": item.get("id"), "description": item.get("description", "")})
        elif t == "actor":
            actors.append({"name": item.get("id"), "description": item.get("description", "")})

    result = await generate_executive_summary(
        cves=cves,
        iocs=iocs,
        actors=actors,
        investigation_duration=duration_min,
    )
    return {
        "summary": result["executive_summary"],
        "source": result["source"],
        "key_findings": result.get("key_findings", []),
        "confidence": result.get("confidence", "low"),
    }
