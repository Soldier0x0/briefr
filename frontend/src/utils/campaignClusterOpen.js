/** Prefer stack → pin → any campaign member (API returns full `members`). */
export function clusterOpenTarget(cluster) {
  if (!cluster) return null
  return (
    cluster.members_on_stack?.[0]
    || cluster.watchlisted_members?.[0]
    || cluster.members?.[0]
    || null
  )
}

/** Ordered member inventory for campaign rows (stack → pins → remainder). */
export function clusterMemberInventory(cluster) {
  if (!cluster) return []
  const seen = new Set()
  const out = []
  for (const id of [
    ...(cluster.members_on_stack || []),
    ...(cluster.watchlisted_members || []),
    ...(cluster.members || []),
  ]) {
    if (!id || seen.has(id)) continue
    seen.add(id)
    out.push(id)
  }
  return out
}

/** Singular-honest label when a single-CVE CTA is still needed. */
export function openCvesLabel(memberCount) {
  const n = Number(memberCount) || 0
  return n === 1 ? 'Open CVE' : 'Open CVEs'
}
