export const CATCHUP_DESCRIPTION =
  'Catch-up uses more of this machine’s CPU, disk, and network to clear backlog while still respecting each provider’s rate limits. Interactive use may feel slower until Catch-up ends.'

export const durationPresets = [
  { hours: 2 },
  { hours: 6, default: true },
  { hours: 8 },
]

export function formatCatchupEndsIn(endsAtIso, nowMs = Date.now()) {
  if (!endsAtIso) return '—'
  const endMs = Date.parse(endsAtIso)
  if (!Number.isFinite(endMs)) return '—'
  const remainingMinutes = Math.max(0, Math.ceil((endMs - nowMs) / 60000))
  if (remainingMinutes === 0) return 'ending now'
  const hours = Math.floor(remainingMinutes / 60)
  const minutes = remainingMinutes % 60
  if (hours === 0) return `${minutes}m`
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}
