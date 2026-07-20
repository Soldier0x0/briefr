export function outboundJobsPath(limit = 50) {
  const parsed = Number(limit)
  const n = Math.max(1, Math.min(200, Number.isFinite(parsed) ? parsed : 50))
  return `/api/admin/jobs/outbound?limit=${n}`
}
