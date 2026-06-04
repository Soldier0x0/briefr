"""BRIEFR Risk Score v1.1a — five weighted components (no momentum)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

WEIGHT_ASSET = 0.37
WEIGHT_KEV = 0.26
WEIGHT_EPSS = 0.16
WEIGHT_EXPLOIT = 0.11
WEIGHT_CVSS = 0.10

DEFAULT_ASSET_UNKNOWN = 0.5


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _days_since(value: Optional[str]) -> Optional[int]:
    d = _parse_date(value)
    if not d:
        return None
    return (date.today() - d).days


def _normalize_products(cve: dict) -> list[str]:
    products = cve.get("affected_products") or []
    if isinstance(products, str):
        return [products.lower()]
    return [str(p).lower() for p in products if p]


def _asset_tokens(user_assets: Optional[list]) -> list[str]:
    if not user_assets:
        return []
    tokens: list[str] = []
    for item in user_assets:
        if isinstance(item, str):
            text = item.strip()
            if text:
                tokens.append(text.lower())
        elif isinstance(item, dict):
            for key in ("product", "vendor", "name", "stack"):
                val = (item.get(key) or "").strip()
                if val:
                    tokens.append(val.lower())
    return tokens


def asset_component_score(cve: dict, user_assets: Optional[list]) -> float:
    """Graduated asset match: direct product > vendor > partial > none; unknown = 0.5."""
    tokens = _asset_tokens(user_assets)
    if not tokens:
        return DEFAULT_ASSET_UNKNOWN

    products = _normalize_products(cve)
    desc = (cve.get("description") or "").lower()
    summary = (cve.get("summary") or "").lower()
    blob = " ".join(products) + " " + desc + " " + summary

    best = 0.0
    for token in tokens:
        if not token:
            continue
        for product in products:
            pl = product.lower()
            if token in pl or pl in token:
                if ":" in pl and token in pl.split(":")[-1]:
                    best = max(best, 1.0)
                elif pl.startswith(token + ":") or pl.split(":")[0].strip() == token:
                    best = max(best, 0.85)
                else:
                    best = max(best, 1.0)
        if token in blob:
            best = max(best, 0.55)
        for product in products:
            vendor = product.split(":")[0].strip().lower() if ":" in product else ""
            if vendor and (token in vendor or vendor in token):
                best = max(best, 0.75)

    return min(1.0, best)


def kev_component_score(
    is_kev: bool,
    date_added: Optional[str] = None,
    due_date: Optional[str] = None,
) -> float:
    """KEV base score with recency weighting for date_added and urgency from due_date."""
    if not is_kev:
        return 0.0

    score = 0.82
    added_days = _days_since(date_added)
    if added_days is not None:
        if added_days <= 7:
            score += 0.18
        elif added_days <= 30:
            score += 0.12
        elif added_days <= 90:
            score += 0.06
        else:
            score += 0.02

    due_parsed = _parse_date(due_date)
    if due_parsed is not None:
        days_until = (due_parsed - date.today()).days
        if days_until is not None:
            if days_until < 0:
                score = min(1.0, score + 0.12)
            elif days_until <= 14:
                score = min(1.0, score + 0.08)
            elif days_until <= 30:
                score = min(1.0, score + 0.04)

    return min(1.0, score)


def _exploit_tier(exploits: list, has_poc: bool) -> float:
    """Exploit graduation: Metasploit > weaponised > PoC > none."""
    if not exploits and not has_poc:
        return 0.0

    types = []
    blobs = []
    for ex in exploits or []:
        t = (ex.get("type") or "").lower()
        types.append(t)
        blobs.append(
            f"{ex.get('title', '')} {ex.get('source', '')} {ex.get('url', '')}".lower()
        )
    blob = " ".join(blobs)

    if any(t == "metasploit" for t in types) or "metasploit" in blob:
        return 1.0
    if any(t in ("weaponised", "weaponized") for t in types):
        return 0.88
    weaponised_hints = ("metasploit", "weaponized", "weaponised", "in-the-wild")
    if any(h in blob for h in weaponised_hints):
        return 0.85
    if any(t == "poc" for t in types) or has_poc:
        return 0.55 if any(t == "poc" for t in types) else 0.35
    return 0.0


def epss_component_score(epss: Optional[float]) -> float:
    if epss is None:
        return 0.25
    try:
        value = float(epss)
    except (TypeError, ValueError):
        return 0.25
    return max(0.0, min(1.0, value))


def cvss_component_score(cvss: Optional[float], severity: Optional[str]) -> float:
    sev = (severity or "").upper()
    if cvss is not None:
        try:
            return max(0.0, min(1.0, float(cvss) / 10.0))
        except (TypeError, ValueError):
            pass
    if sev == "CRITICAL":
        return 0.95
    if sev == "HIGH":
        return 0.75
    if sev == "MEDIUM":
        return 0.45
    if sev == "LOW":
        return 0.2
    return 0.15


def component_sentences(
    cve: dict,
    user_assets: Optional[list],
    components: dict[str, float],
) -> dict[str, str]:
    asset = components["asset"]
    if not user_assets:
        asset_text = (
            "Asset exposure is unknown — no profile loaded; using neutral weighting."
        )
    elif asset >= 0.85:
        asset_text = "Strong match to assets in your profile; prioritize for your environment."
    elif asset >= 0.55:
        asset_text = "Partial overlap with your asset profile; review affected products."
    else:
        asset_text = "Low overlap with your stated assets; lower priority unless internet-facing."

    kev = components["kev"]
    if kev <= 0:
        kev_text = "Not on CISA KEV; no confirmed federal catalogue exploitation signal."
    elif kev >= 0.95:
        kev_text = "CISA KEV with recent catalogue activity; treat as immediate priority."
    else:
        kev_text = "Listed on CISA KEV; elevated priority with recency-weighted urgency."

    epss = components["epss"]
    epss_val = cve.get("epss_score")
    if epss_val is not None:
        pct = round(float(epss_val) * 100, 1)
        epss_text = f"EPSS {pct}% contributes {epss:.0%} normalized likelihood to the score."
    else:
        epss_text = "EPSS data missing; neutral exploit-likelihood weight applied."

    exploit = components["exploit"]
    if exploit >= 0.95:
        exploit_text = "Public Metasploit or weaponised tooling sharply increases practical risk."
    elif exploit >= 0.5:
        exploit_text = "Proof-of-concept or weaponised references raise attacker accessibility."
    elif exploit > 0:
        exploit_text = "Limited public exploit material; moderate uplift to score."
    else:
        exploit_text = "No public exploits identified; exploit component does not add uplift."

    cvss = components["cvss"]
    cvss_val = cve.get("cvss_score")
    sev = cve.get("severity") or "unknown"
    if cvss_val is not None:
        cvss_text = f"CVSS {cvss_val} ({sev}) maps to {cvss:.0%} of the technical severity band."
    else:
        cvss_text = f"Severity {sev} used where CVSS is unavailable."

    return {
        "asset": asset_text,
        "kev": kev_text,
        "epss": epss_text,
        "exploit": exploit_text,
        "cvss": cvss_text,
    }


def calculate_risk_score(
    cve: dict,
    user_assets: Optional[list] = None,
    exploits: Optional[list] = None,
) -> dict[str, Any]:
    """
    Return BRIEFR Risk Score 0.0–100.0 and per-component breakdown.
    user_assets None or [] → asset component uses 0.5 (unknown).
    """
    is_kev = bool(cve.get("is_kev"))
    has_poc = bool(cve.get("has_poc"))
    exploit_list = exploits if exploits is not None else cve.get("public_exploits") or []

    components = {
        "asset": asset_component_score(cve, user_assets if user_assets else None),
        "kev": kev_component_score(
            is_kev,
            cve.get("kev_date_added"),
            cve.get("kev_due_date"),
        ),
        "epss": epss_component_score(cve.get("epss_score")),
        "exploit": _exploit_tier(exploit_list, has_poc),
        "cvss": cvss_component_score(cve.get("cvss_score"), cve.get("severity")),
    }

    if not user_assets:
        components["asset"] = DEFAULT_ASSET_UNKNOWN

    weighted = (
        components["asset"] * WEIGHT_ASSET
        + components["kev"] * WEIGHT_KEV
        + components["epss"] * WEIGHT_EPSS
        + components["exploit"] * WEIGHT_EXPLOIT
        + components["cvss"] * WEIGHT_CVSS
    )
    score = round(max(0.0, min(100.0, weighted * 100.0)), 1)

    sentences = component_sentences(cve, user_assets, components)
    labels = {
        "asset": "Asset exposure",
        "kev": "CISA KEV",
        "epss": "EPSS likelihood",
        "exploit": "Public exploits",
        "cvss": "CVSS severity",
    }
    weights = {
        "asset": WEIGHT_ASSET,
        "kev": WEIGHT_KEV,
        "epss": WEIGHT_EPSS,
        "exploit": WEIGHT_EXPLOIT,
        "cvss": WEIGHT_CVSS,
    }

    breakdown = []
    for key in ("asset", "kev", "epss", "exploit", "cvss"):
        value = components[key]
        points = round(value * weights[key] * 100.0, 1)
        breakdown.append(
            {
                "id": key,
                "label": labels[key],
                "weight": weights[key],
                "value": round(value, 4),
                "points": points,
                "sentence": sentences[key],
            }
        )

    return {
        "score": score,
        "components": components,
        "breakdown": breakdown,
    }
