import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  applyQueueSnapshotAge,
  buildQueueRows,
  formatSourceLabel,
  formatWaitDetail,
  groupQueueRows,
  handleApiQueueDropdownKeyDown,
  highestQueueState,
  indicatorTone,
  remainingRetrySeconds,
  summarizeQueue,
  getLiveQueueSummary,
} from './apiQueuePresentation.js'

describe('apiQueuePresentation', () => {
  it('formatWaitDetail maps active and rate-limited copy', () => {
    assert.match(formatWaitDetail(null, 'active', null, 3.4), /Running 3\.4s/)
    assert.equal(formatWaitDetail('GitHub rate limit', 'rate_limited', 42, null), 'Retry in 42s')
    assert.equal(formatWaitDetail('Provider pacing', 'waiting', null, 3.2), 'Provider pacing · 3.2s')
    assert.equal(formatWaitDetail(null, 'queued', null, null), 'Waiting for provider slot')
  })

  it('formatWaitDetail caps absurd retry durations (misparsed epoch)', () => {
    assert.equal(
      formatWaitDetail('token_quota', 'rate_limited', 1_782_728_841_352, null),
      'Retry in 60m',
    )
  })

  it('formatWaitDetail rounds near minute boundaries without 60s remainder', () => {
    assert.equal(formatWaitDetail(null, 'rate_limited', 119.6, null), 'Retry in 2m')
  })

  it('remainingRetrySeconds subtracts snapshot age from backend retry_in_seconds', () => {
    assert.equal(remainingRetrySeconds(120, 30_000), 90)
    assert.equal(remainingRetrySeconds(10, 15_000), 0)
    assert.equal(remainingRetrySeconds(null, 1000), null)
  })

  it('remainingRetrySeconds caps at 3600 like formatElapsed', () => {
    assert.equal(remainingRetrySeconds(5000, 0), 3600)
  })

  it('applyQueueSnapshotAge updates rate-limited detail as age increases', () => {
    const queue = {
      has_pending: true,
      total_queued: 0,
      total_active: 1,
      requests: [
        {
          request_id: 'a1',
          source: 'openrouter',
          operation: 'detection_context',
          display_label: 'Extracting detection context',
          context_id: 'detection_context',
          state: 'rate_limited',
          wait_reason: 'Provider rate limit',
          retry_in_seconds: 90,
          elapsed_seconds: 0,
        },
      ],
      sources: {},
    }
    const fresh = applyQueueSnapshotAge(queue, 0)
    assert.match(fresh.rows[0].detail, /Retry in 1m 30s/)
    const aged = applyQueueSnapshotAge(queue, 30_000)
    assert.match(aged.rows[0].detail, /Retry in 1m/)
  })

  it('getLiveQueueSummary ages rate-limited retry between snapshot and now', () => {
    const queue = {
      has_pending: true,
      total_queued: 0,
      total_active: 1,
      requests: [
        {
          request_id: 'a1',
          source: 'openrouter',
          state: 'rate_limited',
          retry_in_seconds: 90,
          elapsed_seconds: 0,
        },
      ],
      sources: {},
    }
    const summary = getLiveQueueSummary(queue, 31_000, 1_000)
    assert.match(summary.rows[0].detail, /Retry in 1m/)
  })

  it('highestQueueState prioritizes rate limited over active', () => {
    const state = highestQueueState(
      [
        { state: 'active' },
        { state: 'rate_limited' },
        { state: 'queued' },
      ],
      {},
    )
    assert.equal(state, 'rate_limited')
  })

  it('indicatorTone maps operational semantics', () => {
    assert.equal(indicatorTone('active'), 'active')
    assert.equal(indicatorTone('queued'), 'pending')
    assert.equal(indicatorTone('rate_limited'), 'throttled')
  })

  it('buildQueueRows renders active task-level request', () => {
    const rows = buildQueueRows({
      requests: [
        {
          request_id: 'abc',
          source: 'github',
          operation: 'exploit_search',
          display_label: 'Searching public exploit references',
          context_id: 'CVE-2026-48282',
          state: 'active',
          elapsed_seconds: 3.4,
          wait_reason: null,
        },
      ],
    })
    assert.equal(rows.length, 1)
    assert.equal(rows[0].source, 'GitHub API')
    assert.equal(rows[0].stateLabel, 'ACTIVE')
    assert.equal(rows[0].contextId, 'CVE-2026-48282')
    assert.match(rows[0].detail, /Running/)
  })

  it('buildQueueRows renders queued request with wait copy', () => {
    const rows = buildQueueRows({
      requests: [
        {
          request_id: 'q1',
          source: 'virustotal',
          display_label: 'Enriching observable',
          context_id: '185.1.2.3',
          state: 'queued',
          wait_reason: 'Waiting for provider slot',
        },
      ],
    })
    assert.equal(rows[0].stateLabel, 'QUEUED')
    assert.equal(rows[0].contextId, '185.1.2.3')
    assert.equal(rows[0].detail, 'Waiting for provider slot')
  })

  it('buildQueueRows renders rate-limited request', () => {
    const rows = buildQueueRows({
      requests: [
        {
          request_id: 'r3',
          source: 'github',
          display_label: 'Searching public exploit references',
          context_id: 'CVE-2026-48282',
          state: 'rate_limited',
          wait_reason: 'GitHub rate limit',
          retry_in_seconds: 42,
        },
      ],
    })
    assert.equal(rows[0].stateLabel, 'RATE LIMITED')
    assert.equal(rows[0].detail, 'Retry in 42s')
  })

  it('buildQueueRows falls back to aggregate sources', () => {
    const rows = buildQueueRows({
      total_queued: 1,
      total_active: 0,
      sources: {
        virustotal: { queued: 1, active: 0, paused_for_seconds: 0 },
      },
    })
    assert.equal(rows.length, 1)
    assert.equal(rows[0].fallback, true)
    assert.equal(rows[0].stateLabel, 'QUEUED')
  })

  it('formatSourceLabel uses catalog labels for known providers', () => {
    assert.equal(formatSourceLabel('poc_github'), 'PoC-in-GitHub')
    assert.equal(formatSourceLabel('github'), 'GitHub API')
    assert.equal(formatSourceLabel('rss:darkreading'), 'RSS · darkreading')
  })

  it('groupQueueRows clusters rows by provider', () => {
    const rows = buildQueueRows({
      requests: [
        { request_id: '1', source: 'github', state: 'queued', display_label: 'A' },
        { request_id: '2', source: 'github', state: 'waiting', display_label: 'B' },
        { request_id: '3', source: 'virustotal', state: 'active', display_label: 'C' },
      ],
    })
    const groups = groupQueueRows(rows)
    assert.equal(groups.length, 2)
    assert.equal(groups[0].rows.length, 2)
    assert.equal(groups[1].sourceLabel, 'VirusTotal')
  })

  it('summarizeQueue separates waiting and queued counts', () => {
    const summary = summarizeQueue({
      total_queued: 2,
      total_active: 0,
      requests: [
        { request_id: '1', source: 'github', state: 'queued' },
        { request_id: '2', source: 'github', state: 'waiting' },
      ],
    })
    assert.equal(summary.waitingCount, 1)
    assert.equal(summary.queuedCount, 1)
    assert.match(summary.ariaLabel, /1 API request waiting/)
    assert.match(summary.ariaLabel, /1 API request queued/)
    assert.equal(summary.summaryStats.length, 2)
  })

  it('summarizeQueue builds accessible aria label', () => {
    const summary = summarizeQueue({
      total_queued: 1,
      total_active: 1,
      requests: [
        { request_id: '1', source: 'github', state: 'active' },
        { request_id: '2', source: 'virustotal', state: 'queued' },
      ],
    })
    assert.match(summary.ariaLabel, /1 API request active/)
    assert.match(summary.ariaLabel, /1 API request queued/)
    assert.equal(summary.count, 2)
    assert.equal(summary.tone, 'pending')
  })

  it('summarizeQueue uses active tone when only active requests', () => {
    const summary = summarizeQueue({
      total_queued: 0,
      total_active: 1,
      requests: [{ request_id: '1', source: 'github', state: 'active' }],
    })
    assert.equal(summary.tone, 'active')
    assert.equal(summary.ariaLabel, '1 API request active')
  })

  it('highestQueueState tolerates null requests and sources', () => {
    assert.equal(highestQueueState(null, null), null)
    assert.equal(highestQueueState(null, { github: { active: 1, queued: 0, paused_for_seconds: 0 } }), 'active')
  })

  it('handleApiQueueDropdownKeyDown closes on Escape', () => {
    let open = true
    handleApiQueueDropdownKeyDown({ key: 'Escape' }, v => { open = v })
    assert.equal(open, false)
    let stillOpen = true
    handleApiQueueDropdownKeyDown({ key: 'Tab' }, v => { stillOpen = v })
    assert.equal(stillOpen, true)
  })
})
