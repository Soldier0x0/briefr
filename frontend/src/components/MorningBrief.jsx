import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { fetchBrief } from '../api.js'
import { notifyApiError } from './Toast.jsx'
import { ingestLogUrl } from '../utils/adminLinks.js'
import CveDescriptionClamp from './CveDescriptionClamp.jsx'
import {
  daysUntilDue,
  kevAccentBarClass,
  kevDueLabel,
  kevDueDateInWindow,
  kevBucketFilterLabel,
} from '../utils/kevDeadline.js'
import './MorningBrief.css'

const REASON_LABELS = {
  epss_mover: 'EPSS mover',
  new_kev: 'New KEV',
  kev_due_soon: 'KEV due soon',
  stack_match: 'Stack match',
}

const REASON_TOOLTIPS = {
  epss_mover: 'EPSS probability rose materially in this window.',
  new_kev: 'Newly added to CISA KEV catalog.',
  kev_due_soon: 'CISA federal remediation deadline is approaching.',
  stack_match: 'Mentions products in your stack filter or My Stack.',
}

const REASON_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'kev_due_soon', label: 'KEV due soon' },
  { id: 'epss_mover', label: 'EPSS movers' },
  { id: 'new_kev', label: 'New KEV' },
  { id: 'stack_match', label: 'Stack match' },
]

const EMPTY_HINTS = {
  all: 'No prioritized CVEs in the last 24 hours — check back after the next ingest.',
  kev_due_soon: 'No KEV remediation deadlines in the next window.',
  epss_mover: 'No material EPSS increases tracked in this window.',
  new_kev: 'No new CISA KEV catalogue entries in this window.',
  stack_match: 'No recent CVE activity matching your stack terms.',
}

function inlineMetric(item) {
  if (item.kev_due_date && (item.reasons || []).includes('kev_due_soon')) {
    const label = kevDueLabel(daysUntilDue(item.kev_due_date))
    if (label) return label
  }
  if (item.kev_due_date && item.is_kev) {
    const label = kevDueLabel(daysUntilDue(item.kev_due_date))
    if (label) return label
  }
  if (item.epss_delta != null && item.epss_delta > 0) {
    return `+${(item.epss_delta * 100).toFixed(1)}% EPSS`
  }
  return null
}

function reasonChipClass(reason) {
  if (reason === 'kev_due_soon' || reason === 'new_kev') return 'morning-brief-reason-chip--kev'
  if (reason === 'epss_mover') return 'morning-brief-reason-chip--epss'
  if (reason === 'stack_match') return 'morning-brief-reason-chip--stack'
  return ''
}

function metricClass(item, metric) {
  if (!metric) return ''
  if (metric.includes('EPSS')) {
    const delta = item.epss_delta ?? 0
    if (delta >= 0.2) return 'morning-brief-row-metric--epss-high'
    if (delta >= 0.05) return 'morning-brief-row-metric--epss'
    return 'morning-brief-row-metric--epss-low'
  }
  if (metric === 'Overdue') return 'morning-brief-row-metric--overdue'
  if (metric.startsWith('Due')) return 'morning-brief-row-metric--due'
  return ''
}

function rowAccentClass(item) {
  if (item.is_kev && item.kev_due_date) {
    return kevAccentBarClass(daysUntilDue(item.kev_due_date))
  }
  return 'accent-neutral'
}

function filterQueue(queue, reasonFilter, dueWindow, stack) {
  let rows = queue
  if (reasonFilter && reasonFilter !== 'all') {
    rows = rows.filter(item => (item.reasons || []).includes(reasonFilter))
  }
  if (dueWindow) {
    rows = rows.filter(item => kevDueDateInWindow(item.kev_due_date, dueWindow))
  }
  if (reasonFilter === 'stack_match' && !stack?.trim()) {
    return []
  }
  return rows
}

export default function MorningBrief({
  stack = '',
  sinceHours = 24,
  onSelectCVE,
  onOpenFullFeed,
  reasonFilter = 'all',
  onReasonFilterChange,
  dueWindow = null,
  onDueWindowClear,
  fetchEnabled = true,
}) {
  const [brief, setBrief] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const seqRef = useRef(0)

  const loadBrief = useCallback(() => {
    const seq = ++seqRef.current
    setLoading(true)
    setError(null)
    setErrorRequestId(null)

    fetchBrief({ stack, sinceHours, limit: 10 })
      .then(data => {
        if (seq !== seqRef.current) return
        setBrief(data)
      })
      .catch(err => {
        if (seq !== seqRef.current) return
        setBrief(null)
        setError(err?.message || 'Could not load morning brief.')
        setErrorRequestId(err?.requestId || null)
        notifyApiError(err)
      })
      .finally(() => {
        if (seq !== seqRef.current) return
        setLoading(false)
      })
  }, [stack, sinceHours])

  useEffect(() => {
    if (!fetchEnabled) return undefined
    loadBrief()
    return () => { seqRef.current += 1 }
  }, [loadBrief, fetchEnabled])

  useEffect(() => {
    if (reasonFilter === 'stack_match' && !stack?.trim()) {
      onReasonFilterChange?.('all')
    }
  }, [reasonFilter, stack, onReasonFilterChange])

  const queue = brief?.action_queue || []
  const visibleFilters = useMemo(
    () => REASON_FILTERS.filter(f => f.id !== 'stack_match' || stack?.trim()),
    [stack]
  )

  const filteredQueue = useMemo(
    () => filterQueue(queue, reasonFilter, dueWindow, stack),
    [queue, reasonFilter, dueWindow, stack]
  )

  const emptyHint = EMPTY_HINTS[reasonFilter] || EMPTY_HINTS.all

  return (
    <section className="morning-brief" aria-label="Morning brief action queue">
      <div className="morning-brief-header">
        <div>
          <h2 className="morning-brief-heading mono">// MORNING BRIEF</h2>
          <p className="morning-brief-sub">
            Prioritized CVEs from the last
            {brief?.meta?.since_hours ? ` ${brief.meta.since_hours}` : ' 24'}
            {brief?.meta?.since_hours ? ' hours' : ' hours'}, based on KEV deadlines, EPSS movement, and stack overlap.
          </p>
        </div>
        {onOpenFullFeed && (
          <button
            type="button"
            className="morning-brief-feed-link mono"
            onClick={onOpenFullFeed}
          >
            Open full feed →
          </button>
        )}
      </div>

      {loading && (
        <div className="morning-brief-loading" aria-live="polite">
          <div className="morning-brief-skeleton" aria-hidden="true" />
          <div className="morning-brief-skeleton" aria-hidden="true" />
        </div>
      )}

      {error && !loading && (
        <div className="morning-brief-error mono" role="alert">
          <span>
            {error}
            {errorRequestId && (
              <>
                {' '}
                (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                  ref: {errorRequestId}
                </a>)
              </>
            )}
          </span>
          <button type="button" className="morning-brief-retry-btn" onClick={loadBrief}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && brief && (
        <>
          <div
            className="morning-brief-filters"
            role="toolbar"
            aria-label="Filter action queue"
          >
            {visibleFilters.map(f => (
              <button
                key={f.id}
                type="button"
                className={`morning-brief-filter-chip mono${reasonFilter === f.id ? ' morning-brief-filter-chip--active' : ''}`}
                onClick={() => onReasonFilterChange?.(f.id)}
                aria-pressed={reasonFilter === f.id}
              >
                {f.label}
              </button>
            ))}
            {dueWindow?.bucket && (
              <button
                type="button"
                className="morning-brief-filter-chip morning-brief-filter-chip--due mono"
                onClick={() => onDueWindowClear?.()}
                aria-label={`Clear due-date filter ${kevBucketFilterLabel(dueWindow.bucket)}`}
              >
                Due {kevBucketFilterLabel(dueWindow.bucket)} ×
              </button>
            )}
          </div>

          {filteredQueue.length === 0 ? (
            <p className="morning-brief-empty mono">{emptyHint}</p>
          ) : (
            <ul className="morning-brief-list" aria-label="Ranked action queue">
              {filteredQueue.map(item => {
                const metric = inlineMetric(item)
                const description = item.description || item.summary || ''
                return (
                  <li key={item.cve_id} className={`morning-brief-row ${rowAccentClass(item)}`}>
                    <button
                      type="button"
                      className="morning-brief-row-btn"
                      onClick={() => onSelectCVE?.(item)}
                      aria-label={`CVE ${item.cve_id}. Click to view details.`}
                    >
                      <div className="morning-brief-row-head">
                        <span className="morning-brief-row-id mono">{item.cve_id}</span>
                        <div className="morning-brief-row-chips" aria-label="Brief reasons">
                          {(item.reasons || []).map(reason => {
                            const label = REASON_LABELS[reason] || reason
                            return (
                              <span
                                key={label}
                                className={`morning-brief-reason-chip mono ${reasonChipClass(reason)}`}
                                title={REASON_TOOLTIPS[reason] || undefined}
                              >
                                {label}
                              </span>
                            )
                          })}
                        </div>
                        {metric && (
                          <span className={`morning-brief-row-metric mono ${metricClass(item, metric)}`}>
                            {metric}
                          </span>
                        )}
                      </div>
                      {description ? (
                        <CveDescriptionClamp
                          text={description}
                          maxLines={2}
                          className="morning-brief-row-desc morning-brief-row-desc--highlight"
                        />
                      ) : (
                        <p className="morning-brief-row-desc-fallback mono">No description available.</p>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </>
      )}
    </section>
  )
}
