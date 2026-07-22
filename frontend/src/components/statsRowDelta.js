export function deltaToneClass(delta, polarity = 'worse-up') {
  if (delta == null || delta === 0) return null
  const upIsBad = polarity !== 'better-up'
  const isUp = delta > 0
  const bad = upIsBad ? isUp : !isUp
  return bad ? 'stat-delta--up' : 'stat-delta--down'
}
