"""Hub CVE and mega-campaign suppression (v2 Phase 1)."""

from __future__ import annotations

from correlation.config import get_hub_cve_pulse_cap, get_max_campaign_members


def is_hub_cve(pulse_count: int, cap: int | None = None) -> bool:
    limit = cap if cap is not None else get_hub_cve_pulse_cap()
    return pulse_count > limit


def apply_member_cap(members: list[str], max_members: int | None = None) -> list[str]:
    """Stable cap: sort CVE IDs ascending, keep self + closest peers."""
    limit = max_members if max_members is not None else get_max_campaign_members()
    if len(members) <= limit:
        return sorted(members)
    return sorted(members)[:limit]


def filter_campaign_members(
    cve_id: str,
    members: list[str],
    pulse_count_by_cve: dict[str, int],
    hub_cap: int | None = None,
    max_members: int | None = None,
) -> list[str]:
    """
    Remove hub CVE peers from expansion when the anchor CVE is not a hub.
    Always include cve_id; cap total size.
    """
    anchor = cve_id.upper()
    unique = sorted({m.upper() for m in members if m})
    if anchor not in unique:
        unique.append(anchor)
    unique.sort()

    cap = hub_cap if hub_cap is not None else get_hub_cve_pulse_cap()
    anchor_is_hub = is_hub_cve(pulse_count_by_cve.get(anchor, 0), cap)

    if anchor_is_hub:
        # Hub CVE: only return direct co-members, heavily capped.
        filtered = [anchor] + [m for m in unique if m != anchor][: max(1, (max_members or get_max_campaign_members()) - 1)]
        return apply_member_cap(filtered, max_members)

    filtered = [anchor]
    for peer in unique:
        if peer == anchor:
            continue
        peer_pulses = pulse_count_by_cve.get(peer, 0)
        if is_hub_cve(peer_pulses, cap):
            continue
        filtered.append(peer)

    return apply_member_cap(filtered, max_members)
