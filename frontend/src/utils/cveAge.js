/** Published-age styling — green for fresh CVEs, amber for recent, muted for older. */
export function publishedAgeClass(isoString) {
  if (!isoString) return 'age-old'
  const hours = (Date.now() - new Date(isoString).getTime()) / 3600000
  if (hours < 24) return 'age-fresh'
  if (hours < 72) return 'age-recent'
  return 'age-old'
}
