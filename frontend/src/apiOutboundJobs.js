export function outboundJobsPath(limit = 50) {
  const parsed = Number(limit)
  const n = Math.max(1, Math.min(200, Number.isFinite(parsed) ? parsed : 50))
  return `/jobs/outbound?limit=${n}`
}

export function outboundJobsPingPath() {
  return '/jobs/outbound/ping'
}
