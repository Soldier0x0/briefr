/** Operator-facing labels for circuit-breaker / cooldown state (UI only). */

export const CIRCUIT_UI = {
  statusBar: 'API health',
  statusBarOk: 'OK',
  statusBarPaused: (count) => `${count} paused`,
  providersInCooldown: 'Providers in cooldown',
  nonePaused: 'None paused',
  oneOrMorePaused: 'One or more providers paused',
  pausedProvider: 'Paused (cooldown)',
  unstable: 'Unstable',
  resetPause: 'Resume retries',
  resetPauseProgress: 'Resuming…',
  resetPauseTitle:
    'Clear the cooldown pause and last error so this source can be called again',
  skippedCooldown: 'skipped — cooling down',
  feedTripped: 'PAUSED',
  feedTrippedOperator: 'PAUSED',
  overviewTripped: 'SOURCES PAUSED',
  legendTag: 'PAUSED',
  legendDesc:
    'Upstream source hit repeated failures — calls are paused briefly, then retried automatically.',
  webhookPausedTitle: (label) =>
    `${label}: paused after recent delivery failures — retries resume automatically`,
  intelIssue: (label, failures) =>
    `${label} — paused after ${failures} consecutive failure${failures === 1 ? '' : 's'}`,
  needsAttentionDetail: (failures) =>
    `Paused after ${failures} consecutive failure${failures === 1 ? '' : 's'}. BRIEFR will retry automatically.`,
}

export const LLM_ERROR_LABELS = {
  empty: 'no content returned',
  rate_limit: 'rate limited',
  circuit_open: CIRCUIT_UI.skippedCooldown,
  timeout: 'timeout',
  auth: 'auth error',
  model_not_found: 'model not found',
  unknown: 'unknown error',
}
