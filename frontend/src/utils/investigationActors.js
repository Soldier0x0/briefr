/** Extract threat-actor-like tags from IOC enrichment tags (VT, etc.). */
const ACTOR_HINTS = [
  /^apt[-_]?\d+/i,
  /\bapt\b/i,
  /lazarus|kimsuky|sandworm|fancy bear|cozy bear|volt typhoon|scattered spider/i,
  /ransomware|botnet|c2/i,
]

export function extractActorTags(tags) {
  if (!Array.isArray(tags)) return []
  const seen = new Set()
  const out = []
  for (const raw of tags) {
    const t = String(raw || '').trim()
    if (!t || seen.has(t.toLowerCase())) continue
    const isActor = ACTOR_HINTS.some(re => re.test(t))
      || (t.length > 2 && /actor|group|gang|crew/i.test(t))
    if (isActor) {
      seen.add(t.toLowerCase())
      out.push(t)
    }
  }
  return out.slice(0, 8)
}
