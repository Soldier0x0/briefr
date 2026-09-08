export function dailyBriefDeliveryCopy({ loading, error, labels }) {
  if (loading) {
    return { kind: 'loading', text: 'Loading destinations…' }
  }
  if (error) {
    return { kind: 'error', text: 'Could not load destinations.' }
  }
  const names = Array.isArray(labels) ? labels.filter(Boolean) : []
  if (!names.length) {
    return {
      kind: 'empty',
      text: 'No destinations subscribe to Daily brief. Tick Daily brief (EOD / standup) on Webhooks — that is not real-time KEV or watchlist.',
    }
  }
  return {
    kind: 'ok',
    text: `Sends to ${names.join(', ')} (Daily brief subscribed)`,
  }
}
