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

export function openCvesLabel(memberCount) {
  const n = Number(memberCount) || 0
  return n === 1 ? 'OPEN CVE' : 'OPEN CVEs'
}
